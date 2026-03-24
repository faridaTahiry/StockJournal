from fastapi import FastAPI, Depends, HTTPException   # FastAPI core — like [ApiController] in C#
from starlette.middleware.cors import CORSMiddleware   # handles cross-origin requests (frontend talking to backend)
from sqlalchemy.orm import Session                    # DB session type hint
from typing import List, Optional                               # like List<T> in C#
from pydantic import BaseModel                        # for ChatRequest schema
from zoneinfo import ZoneInfo
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

import models, schemas                               # our models and schemas
from database import engine, get_db                  # DB engine and session dependency
from agent import chat_with_agent                    # our agent function
from stock import get_stock_price, validate_symbol, get_stock_history
from scanner import compute_movers
from news import fetch_rss_items, extract_symbols, filter_recent
from social import extract_symbols_from_post, filter_recent as filter_recent_social, ParsedSocialPost
from datetime import timezone
from signals import generate_signals_json
from datetime import datetime, timedelta
import smtplib
from email.message import EmailMessage
from config import (
    ALERT_EMAIL_ALWAYS_TO,
    ALERT_EMAIL_FROM,
    ALERT_EMAIL_TO,
    ALERT_SMTP_HOST,
    ALERT_SMTP_PORT,
    ALERT_SMTP_USER,
    ALERT_SMTP_PASS,
)
import yfinance as yf
from news_agent import rank_news_items_with_llm, fallback_rank_news
from movers_agent import (
    fetch_yahoo_predefined,
    fetch_finviz_top_gainers,
    merge_mover_candidates,
    rank_movers_with_llm,
    fallback_rank_movers,
)
from advisor_agent import build_daytrader_advice, fallback_daytrader_advice


models.Base.metadata.create_all(bind= engine)

app = FastAPI()

ET = ZoneInfo("America/New_York")
_scheduler: Optional[BackgroundScheduler] = None

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],          # only allow requests from our frontend
    allow_methods=["*"],                             # allow all HTTP methods (GET, POST, etc.)
    allow_headers=["*"],                             # allow all headers
)

def _run_scan(db: Session, *, window: str, triggered_by: str) -> int:
    universe = (
        db.query(models.UniverseSymbol)
        .filter(models.UniverseSymbol.active == True)  # noqa: E712
        .all()
    )
    symbols = [u.symbol for u in universe]
    movers = compute_movers(symbols, window=window, min_price=20.0, limit=200)

    snapshot = models.ScanSnapshot(
        triggered_by=triggered_by,
        window=window,
        universe_size=len(symbols),
        candidate_count=len(movers),
    )
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)

    for m in movers:
        db.add(
            models.ScanResult(
                snapshot_id=snapshot.id,
                symbol=m.symbol,
                last_price=m.last_price,
                change_abs=m.change_abs,
                change_pct=m.change_pct,
                score=m.score,
            )
        )
    db.commit()
    return snapshot.id


def _run_scan_in_new_session(*, window: str, triggered_by: str) -> None:
    # Import lazily to avoid circular import issues.
    from database import SessionLocal

    db = SessionLocal()
    try:
        _run_scan(db, window=window, triggered_by=triggered_by)
    finally:
        db.close()


def _alert_email_recipients() -> List[str]:
    """Primary `ALERT_EMAIL_TO` plus `ALERT_EMAIL_ALWAYS_TO`, deduped (case-insensitive)."""
    seen: set[str] = set()
    out: List[str] = []
    for addr in (ALERT_EMAIL_TO, ALERT_EMAIL_ALWAYS_TO):
        a = (addr or "").strip()
        if not a:
            continue
        k = a.casefold()
        if k in seen:
            continue
        seen.add(k)
        out.append(a)
    return out


def _send_email_alert(subject: str, body: str) -> bool:
    recipients = _alert_email_recipients()
    if not (ALERT_EMAIL_FROM and recipients and ALERT_SMTP_USER and ALERT_SMTP_PASS):
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = ALERT_EMAIL_FROM
    msg["To"] = ", ".join(recipients)
    msg.set_content(body)

    with smtplib.SMTP(ALERT_SMTP_HOST, ALERT_SMTP_PORT, timeout=15) as server:
        server.starttls()
        server.login(ALERT_SMTP_USER, ALERT_SMTP_PASS)
        server.send_message(msg, from_addr=ALERT_EMAIL_FROM, to_addrs=recipients)
    return True


@app.on_event("startup")
def start_scheduler():
    global _scheduler
    if _scheduler is not None:
        return

    sched = BackgroundScheduler(timezone=ET)
    trigger = CronTrigger(hour=8, minute=30, timezone=ET)
    sched.add_job(lambda: _run_scan_in_new_session(window="15m", triggered_by="schedule"), trigger=trigger)
    sched.start()
    _scheduler = sched


@app.on_event("shutdown")
def shutdown_scheduler():
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None


@app.post("/watchlist", response_model=schemas.WatchlistItemResponse)
def add_to_watchlist(item : schemas.WatchlistItemCreate, db: Session = Depends(get_db)):
    if not validate_symbol(item.symbol):                                 # reject invalid tickers
        raise HTTPException(status_code=400, detail="Invalid stock symbol")
    
    db_item = models.WatchlistItem(symbol=item.symbol.upper())          # create new DB model instance
    db.add(db_item)                                                      # add to session — like .Add() in EF
    db.commit()                                                          # save to database — like .SaveChanges()
    db.refresh(db_item)                                                  # refresh with DB-generated values (id, timestamp)
    return db_item

@app.get("/watchlist", response_model=List[schemas.WatchlistItemResponse])  # like [HttpGet]
def get_watchlist(db: Session = Depends(get_db)):
    return db.query(models.WatchlistItem).all()                         # like dbContext.Watchlist.ToList()

@app.delete("/watchlist/{symbol}")                                       # like [HttpDelete("{symbol}")]
def remove_from_watchlist(symbol: str, db: Session = Depends(get_db)):
    item = db.query(models.WatchlistItem).filter(                       # like .Where() in LINQ
        models.WatchlistItem.symbol == symbol.upper()
    ).first()                                                            # like .FirstOrDefault()
    if not item:
        raise HTTPException(status_code=404, detail="Symbol not found")
    db.delete(item)                                                      # like .Remove() in EF
    db.commit()
    return {"message": f"Removed {symbol} from watchlist"}              # f"" is like $"" in C#

# --- Stock Price Endpoint ---

@app.get("/stock/{symbol}", response_model=schemas.StockResponse)       # like [HttpGet("{symbol}")]
def get_price(symbol: str):
    return get_stock_price(symbol)                                       # calls our yfinance function

# --- Trade Endpoints ---

@app.post("/trades", response_model=schemas.TradeResponse)
def log_trade(trade: schemas.TradeCreate, db: Session = Depends(get_db)):
    db_trade = models.Trade(**trade.model_dump())                        # ** unpacks dict into keyword args
    db.add(db_trade)
    db.commit()
    db.refresh(db_trade)
    return db_trade

@app.get("/trades", response_model=List[schemas.TradeResponse])
def get_trades(db: Session = Depends(get_db)):
    return db.query(models.Trade).all()

@app.delete("/trades/{trade_id}")
def delete_trade(trade_id: int, db: Session = Depends(get_db)):
    trade = db.query(models.Trade).filter(models.Trade.id == trade_id).first()
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    db.delete(trade)
    db.commit()
    return {"message": f"Trade {trade_id} deleted"}

# --- Agent Endpoint ---

class ChatRequest(BaseModel):                                            # simple schema for chat request
    message: str                                                         # the user's message
    focused_symbol: Optional[str] = None                                    # optional focused symbol from drag and drop

@app.post("/agent/chat")                                                 # like [HttpPost] in C#
def chat(request: ChatRequest, db: Session = Depends(get_db)):
    watchlist = db.query(models.WatchlistItem).all()                     # fetch user's watchlist from DB
    response = chat_with_agent(request.message, watchlist, request.focused_symbol)  # send focused symbol to agent
    return {"response": response}   


@app.get("/stock/{symbol}/history")
def get_history(symbol: str, period: str = "3mo", interval: str = "1d"):
    return get_stock_history(symbol, period, interval)


# --- Universe endpoints ---

@app.post("/universe/import", response_model=List[schemas.UniverseSymbolResponse])
def import_universe(items: List[schemas.UniverseSymbolCreate], db: Session = Depends(get_db)):
    created: list[models.UniverseSymbol] = []
    for item in items:
        sym = item.symbol.strip().upper()
        if not sym:
            continue
        existing = db.query(models.UniverseSymbol).filter(models.UniverseSymbol.symbol == sym).first()
        if existing:
            existing.exchange = item.exchange
            existing.active = item.active
            created.append(existing)
            continue
        row = models.UniverseSymbol(symbol=sym, exchange=item.exchange, active=item.active)
        db.add(row)
        created.append(row)
    db.commit()
    for row in created:
        db.refresh(row)
    return created


@app.get("/universe", response_model=List[schemas.UniverseSymbolResponse])
def list_universe(db: Session = Depends(get_db)):
    return db.query(models.UniverseSymbol).order_by(models.UniverseSymbol.symbol.asc()).all()


# --- Scanner endpoints ---

@app.post("/scanner/run", response_model=schemas.RunScannerResponse)
def run_scanner(req: schemas.RunScannerRequest, db: Session = Depends(get_db)):
    window = req.window
    snapshot_id = _run_scan(db, window=window, triggered_by="on_demand")
    return schemas.RunScannerResponse(snapshot_id=snapshot_id, message="Scan completed")


@app.get("/scanner/latest", response_model=schemas.ScanSnapshotResponse)
def latest_scan(db: Session = Depends(get_db)):
    snap = db.query(models.ScanSnapshot).order_by(models.ScanSnapshot.run_at.desc()).first()
    if not snap:
        raise HTTPException(status_code=404, detail="No scans yet")
    return snap


@app.get("/scanner/movers", response_model=List[schemas.ScanResultResponse])
def latest_movers(limit: int = 50, db: Session = Depends(get_db)):
    snap = db.query(models.ScanSnapshot).order_by(models.ScanSnapshot.run_at.desc()).first()
    if not snap:
        return []
    rows = (
        db.query(models.ScanResult)
        .filter(models.ScanResult.snapshot_id == snap.id)
        .order_by(models.ScanResult.score.desc())
        .limit(limit)
        .all()
    )
    out: List[schemas.ScanResultResponse] = []
    for r in rows:
        volume = None
        avg_volume = None
        relative_volume = None
        try:
            info = yf.Ticker(r.symbol).fast_info
            volume = getattr(info, "last_volume", None)
            avg_volume = getattr(info, "ten_day_average_volume", None) or getattr(info, "three_month_average_volume", None)
            if volume is not None and avg_volume not in (None, 0):
                relative_volume = round(float(volume) / float(avg_volume), 2)
            if volume is not None:
                volume = float(volume)
            if avg_volume is not None:
                avg_volume = float(avg_volume)
        except Exception:
            pass

        out.append(
            schemas.ScanResultResponse(
                symbol=r.symbol,
                last_price=r.last_price,
                change_abs=r.change_abs,
                change_pct=r.change_pct,
                score=r.score,
                volume=volume,
                avg_volume=avg_volume,
                relative_volume=relative_volume,
            )
        )
    return out


@app.post("/news/ingest", response_model=schemas.IngestNewsResponse)
def ingest_news(db: Session = Depends(get_db)):
    # Build a known symbol set from universe + watchlist to improve matching precision.
    universe = db.query(models.UniverseSymbol.symbol).filter(models.UniverseSymbol.active == True).all()  # noqa: E712
    watchlist = db.query(models.WatchlistItem.symbol).all()
    known = [s[0] for s in universe] + [s[0] for s in watchlist]

    items = fetch_rss_items()
    items, skipped_stale = filter_recent(items, max_age_hours=24)

    ingested = 0
    skipped_duplicate = 0

    for it in items:
        exists = db.query(models.NewsItem).filter(models.NewsItem.url == it.url).first()
        if exists:
            skipped_duplicate += 1
            continue

        row = models.NewsItem(
            source=it.source,
            title=it.title,
            url=it.url,
            published_at=it.published_at.replace(tzinfo=None),
            summary=it.summary,
        )
        db.add(row)
        db.commit()
        db.refresh(row)

        symbols = extract_symbols(f"{it.title}\n{it.summary or ''}", known)
        for sym in symbols:
            db.add(models.NewsMention(news_item_id=row.id, symbol=sym))
        db.commit()

        ingested += 1

    return schemas.IngestNewsResponse(ingested=ingested, skipped_stale=skipped_stale, skipped_duplicate=skipped_duplicate)


@app.get("/news", response_model=List[schemas.NewsItemResponse])
def list_news(symbol: Optional[str] = None, limit: int = 50, db: Session = Depends(get_db)):
    q = db.query(models.NewsItem).order_by(models.NewsItem.published_at.desc())
    if symbol:
        sym = symbol.strip().upper()
        q = (
            q.join(models.NewsMention, models.NewsMention.news_item_id == models.NewsItem.id)
            .filter(models.NewsMention.symbol == sym)
        )
    items = q.limit(limit).all()

    out: list[schemas.NewsItemResponse] = []
    for item in items:
        symbols = [m.symbol for m in item.mentions] if getattr(item, "mentions", None) else []
        out.append(
            schemas.NewsItemResponse(
                id=item.id,
                source=item.source,
                title=item.title,
                url=item.url,
                published_at=item.published_at,
                summary=item.summary,
                symbols=sorted(set(symbols)),
            )
        )
    return out


@app.get("/news/agent/latest", response_model=List[schemas.AgentNewsItemResponse])
def latest_news_via_agent(limit: int = 20):
    """
    Pull latest internet news (RSS), keep last 24h, and rank by importance + recency.
    Most important recent events (e.g., last 5h) should rise above older 24h items.
    """
    raw_items = fetch_rss_items()
    recent_items, _ = filter_recent(raw_items, max_age_hours=24)
    normalized = [
        {
            "source": i.source,
            "title": i.title,
            "url": i.url,
            "published_at": i.published_at.isoformat(),
            "summary": i.summary,
        }
        for i in recent_items
    ]

    if not normalized:
        return []

    try:
        ranked = rank_news_items_with_llm(normalized)
    except Exception:
        ranked = fallback_rank_news(normalized)

    by_url = {n["url"]: n for n in normalized}
    merged: list[schemas.AgentNewsItemResponse] = []
    for r in ranked:
        url = r.get("url")
        base = by_url.get(url)
        if not base:
            continue
        merged.append(
            schemas.AgentNewsItemResponse(
                source=base["source"],
                title=base["title"],
                url=base["url"],
                published_at=datetime.fromisoformat(base["published_at"].replace("Z", "+00:00")).replace(tzinfo=None),
                importance_score=float(r.get("importance_score", 0)),
                recency_score=float(r.get("recency_score", 0)),
                priority_score=float(r.get("priority_score", 0)),
                why=str(r.get("why", "")),
            )
        )

    merged.sort(key=lambda x: x.priority_score, reverse=True)
    return merged[: max(1, limit)]


@app.get("/scanner/movers/agent/latest", response_model=List[schemas.AgentMoverResponse])
def latest_movers_via_agent(limit: int = 30):
    """
    Aggregate top movers from Finviz + Yahoo predefined screens and rank with AI agent.
    """
    candidates = []
    candidates.extend(fetch_finviz_top_gainers(limit=120))
    candidates.extend(fetch_yahoo_predefined("day_gainers", count=100))
    candidates.extend(fetch_yahoo_predefined("most_actives", count=100))
    merged = merge_mover_candidates(candidates)
    if not merged:
        return []

    # Respect app constraint: focus on stocks above $20 when price exists.
    filtered = [m for m in merged if m.get("price") is None or float(m.get("price")) > 20.0]

    try:
        ranked = rank_movers_with_llm(filtered, limit=limit)
    except Exception:
        ranked = fallback_rank_movers(filtered, limit=limit)

    by_symbol = {m["symbol"]: m for m in filtered}
    out: List[schemas.AgentMoverResponse] = []
    for r in ranked:
        sym = (r.get("symbol") or "").upper().strip()
        base = by_symbol.get(sym)
        if not base:
            continue
        out.append(
            schemas.AgentMoverResponse(
                symbol=sym,
                price=base.get("price"),
                change_pct=base.get("change_pct"),
                volume=base.get("volume"),
                sources=base.get("sources", []),
                priority_score=float(r.get("priority_score", 0)),
                why=str(r.get("why", "")),
            )
        )

    out.sort(key=lambda x: x.priority_score, reverse=True)
    return out[: max(1, limit)]


def _fetch_digest_data(
    limit_movers: int = 20,
    limit_news: int = 20,
) -> tuple[List[schemas.AgentNewsItemResponse], List[schemas.AgentMoverResponse], schemas.DayTraderAdviceResponse]:
    movers = latest_movers_via_agent(limit=limit_movers)
    news = latest_news_via_agent(limit=limit_news)

    movers_payload = [
        {
            "symbol": m.symbol,
            "price": m.price,
            "change_pct": m.change_pct,
            "volume": m.volume,
            "sources": m.sources,
            "priority_score": m.priority_score,
            "why": m.why,
        }
        for m in movers
    ]
    news_payload = [
        {
            "source": n.source,
            "title": n.title,
            "url": n.url,
            "published_at": str(n.published_at),
            "importance_score": n.importance_score,
            "recency_score": n.recency_score,
            "priority_score": n.priority_score,
            "why": n.why,
        }
        for n in news
    ]

    try:
        result = build_daytrader_advice(movers_payload, news_payload)
    except Exception:
        result = fallback_daytrader_advice(movers_payload, news_payload)

    suggestions = result.get("suggestions", [])
    normalized: List[schemas.DayTraderSuggestionResponse] = []
    for s in suggestions:
        sym = (s.get("symbol") or "").upper().strip()
        if not sym:
            continue
        normalized.append(
            schemas.DayTraderSuggestionResponse(
                symbol=sym,
                setup=str(s.get("setup") or "momentum"),
                confidence=float(s.get("confidence") or 0.0),
                bias=str(s.get("bias") or "neutral"),
                reason=str(s.get("reason") or ""),
                levels=dict(s.get("levels") or {}),
                plan=str(s.get("plan") or ""),
                risk_note=str(s.get("risk_note") or ""),
                catalysts=[str(c) for c in (s.get("catalysts") or [])],
                metrics=dict(s.get("metrics") or {}),
            )
        )

    advice = schemas.DayTraderAdviceResponse(
        generated_at=datetime.utcnow(),
        summary=str(result.get("summary") or ""),
        suggestions=normalized,
    )
    return news, movers, advice


def _format_digest_email_text(
    greeting: str,
    news: List[schemas.AgentNewsItemResponse],
    movers: List[schemas.AgentMoverResponse],
    advice: schemas.DayTraderAdviceResponse,
) -> str:
    lines: list[str] = []
    lines.append(greeting.strip())
    lines.append("")
    lines.append(f"Digest generated {advice.generated_at.strftime('%Y-%m-%d %H:%M UTC')}.")
    lines.append("")
    lines.append("=== Day trader advisor ===")
    lines.append(advice.summary.strip() or "(No summary.)")
    lines.append("")
    if not advice.suggestions:
        lines.append("(No symbol suggestions.)")
    else:
        for s in advice.suggestions:
            conf = s.confidence
            conf_s = f"{conf:.0%}" if 0 <= conf <= 1 else f"{conf:.2f}"
            lines.append(f"* {s.symbol} — {s.setup} ({s.bias}, confidence {conf_s})")
            if s.reason:
                lines.append(f"  Reason: {s.reason}")
            if s.plan:
                lines.append(f"  Plan: {s.plan}")
            if s.risk_note:
                lines.append(f"  Risk: {s.risk_note}")
            if s.levels:
                lines.append(f"  Levels: {s.levels}")
            if s.catalysts:
                lines.append(f"  Catalysts: {', '.join(s.catalysts)}")
            lines.append("")
    lines.append("---")
    lines.append(
        "That advice was generated from the following ranked news and market movers "
        "(same inputs the model saw):"
    )
    lines.append("")
    lines.append("=== Latest news ===")
    if not news:
        lines.append("(No recent news in the last 24 hours.)")
    else:
        for i, n in enumerate(news, 1):
            lines.append(f"{i}. [{n.source}] {n.title}")
            lines.append(f"   {n.url}")
            if n.why:
                lines.append(f"   Why ranked: {n.why}")
            lines.append("")
    lines.append("=== Top movers ===")
    if not movers:
        lines.append("(No movers returned from screens.)")
    else:
        for i, m in enumerate(movers, 1):
            price = f"${m.price:.2f}" if m.price is not None else "—"
            ch = f"{m.change_pct:+.2f}%" if m.change_pct is not None else "—"
            vol = f"{m.volume:,.0f}" if m.volume is not None else "—"
            lines.append(f"{i}. {m.symbol}  {price}  {ch}  vol {vol}")
            if m.why:
                lines.append(f"   Why ranked: {m.why}")
            lines.append("")
    lines.append("---")
    lines.append(
        "This message was sent automatically by Stock Journal. "
        "If you have a minute, please share feedback on this analysis—what was useful, "
        "what missed the mark, or ideas for what you'd like to see. We read replies and "
        "use them to improve our models."
    )
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


@app.get("/advisor/daytrader/latest", response_model=schemas.DayTraderAdviceResponse)
def daytrader_advice(limit_movers: int = 20, limit_news: int = 20):
    """
    Combine latest ranked movers + latest ranked news and produce day-trader suggestions.
    """
    _, _, response = _fetch_digest_data(limit_movers=limit_movers, limit_news=limit_news)
    return response


@app.post("/social/ingest", response_model=schemas.IngestSocialResponse)
def ingest_social(posts: List[schemas.SocialPostIngest], db: Session = Depends(get_db)):
    universe = db.query(models.UniverseSymbol.symbol).filter(models.UniverseSymbol.active == True).all()  # noqa: E712
    watchlist = db.query(models.WatchlistItem.symbol).all()
    known = [s[0] for s in universe] + [s[0] for s in watchlist]

    parsed = []
    for p in posts:
        # Normalize to UTC if tz-aware; if naive, treat as UTC.
        dt = p.created_at
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        parsed.append(
            ParsedSocialPost(
                source=p.source,
                author=p.author,
                external_id=p.external_id,
                content=p.content,
                url=p.url,
                created_at=dt,
            )
        )

    parsed, skipped_stale = filter_recent_social(parsed, max_age_hours=6)

    ingested = 0
    skipped_duplicate = 0

    for it in parsed:
        if it.external_id:
            exists = db.query(models.SocialPost).filter(models.SocialPost.external_id == it.external_id).first()
            if exists:
                skipped_duplicate += 1
                continue

        row = models.SocialPost(
            source=it.source,
            author=it.author,
            external_id=it.external_id,
            content=it.content,
            url=it.url,
            created_at=it.created_at.replace(tzinfo=None),
        )
        db.add(row)
        db.commit()
        db.refresh(row)

        symbols = extract_symbols_from_post(it.content, known)
        for sym in symbols:
            db.add(models.SocialMention(post_id=row.id, symbol=sym))
        db.commit()
        ingested += 1

    return schemas.IngestSocialResponse(ingested=ingested, skipped_stale=skipped_stale, skipped_duplicate=skipped_duplicate)


@app.get("/social", response_model=List[schemas.SocialPostResponse])
def list_social(symbol: Optional[str] = None, limit: int = 50, db: Session = Depends(get_db)):
    q = db.query(models.SocialPost).order_by(models.SocialPost.created_at.desc())
    if symbol:
        sym = symbol.strip().upper()
        q = (
            q.join(models.SocialMention, models.SocialMention.post_id == models.SocialPost.id)
            .filter(models.SocialMention.symbol == sym)
        )
    items = q.limit(limit).all()

    out: List[schemas.SocialPostResponse] = []
    for item in items:
        symbols = [m.symbol for m in item.mentions] if getattr(item, "mentions", None) else []
        out.append(
            schemas.SocialPostResponse(
                id=item.id,
                source=item.source,
                author=item.author,
                external_id=item.external_id,
                content=item.content,
                url=item.url,
                created_at=item.created_at,
                symbols=sorted(set(symbols)),
            )
        )
    return out


@app.post("/scanner/signals/generate", response_model=schemas.GenerateSignalsResponse)
def generate_signals(req: Optional[schemas.GenerateSignalsRequest] = None, db: Session = Depends(get_db)):
    if req is None:
        req = schemas.GenerateSignalsRequest()
    snap = db.query(models.ScanSnapshot).order_by(models.ScanSnapshot.run_at.desc()).first()
    if not snap:
        raise HTTPException(status_code=404, detail="No scans yet")

    movers_rows = (
        db.query(models.ScanResult)
        .filter(models.ScanResult.snapshot_id == snap.id)
        .order_by(models.ScanResult.score.desc())
        .limit(req.limit)
        .all()
    )
    movers = [
        {
            "symbol": r.symbol,
            "last_price": r.last_price,
            "change_pct": r.change_pct,
            "change_abs": r.change_abs,
            "score": r.score,
        }
        for r in movers_rows
    ]
    symbols = [m["symbol"] for m in movers]

    # Recent news/social for these symbols.
    news_by_symbol: dict = {s: [] for s in symbols}
    social_by_symbol: dict = {s: [] for s in symbols}

    for s in symbols:
        news_items = (
            db.query(models.NewsItem)
            .join(models.NewsMention, models.NewsMention.news_item_id == models.NewsItem.id)
            .filter(models.NewsMention.symbol == s)
            .order_by(models.NewsItem.published_at.desc())
            .limit(5)
            .all()
        )
        news_by_symbol[s] = [{"title": n.title, "url": n.url, "published_at": str(n.published_at), "source": n.source} for n in news_items]

        social_items = (
            db.query(models.SocialPost)
            .join(models.SocialMention, models.SocialMention.post_id == models.SocialPost.id)
            .filter(models.SocialMention.symbol == s)
            .order_by(models.SocialPost.created_at.desc())
            .limit(5)
            .all()
        )
        social_by_symbol[s] = [{"author": p.author, "content": p.content[:240], "url": p.url, "created_at": str(p.created_at), "source": p.source} for p in social_items]

    try:
        payload = generate_signals_json(movers=movers, news_by_symbol=news_by_symbol, social_by_symbol=social_by_symbol)
        signals_list = payload.get("signals", [])
    except Exception as e:
        # Make the failure explicit for Swagger/UI users.
        # Note: this surfaces the exception message to the client for debugging.
        raise HTTPException(
            status_code=503,
            detail={
                "error": "LLM failed",
                "exception_type": type(e).__name__,
                "exception_message": str(e),
            },
        )

    created = 0
    now = datetime.utcnow()
    for s in signals_list:
        sym = (s.get("symbol") or "").strip().upper()
        if not sym:
            continue
        row = models.Signal(
            snapshot_id=snap.id,
            symbol=sym,
            signal_type=s.get("signal_type") or "watch",
            confidence=s.get("confidence"),
            rationale=s.get("rationale") or "",
            key_levels=str(s.get("key_levels")) if s.get("key_levels") is not None else None,
            catalysts=str(s.get("catalysts")) if s.get("catalysts") is not None else None,
        )
        if not row.rationale:
            continue
        db.add(row)
        created += 1

        # Always create in-app alert for each signal.
        alert_title = f"{sym} {row.signal_type.replace('_', ' ').title()} signal"
        alert_body = row.rationale
        priority = "high" if (row.confidence or 0) >= 0.7 else "normal"
        db.add(
            models.Alert(
                symbol=sym,
                title=alert_title,
                body=alert_body,
                priority=priority,
                channel="in_app",
                sent=True,
            )
        )

        # Email throttle: at most one email per symbol each 30 minutes.
        should_email = priority == "high"
        if should_email:
            recent_email = (
                db.query(models.Alert)
                .filter(
                    models.Alert.symbol == sym,
                    models.Alert.channel == "email",
                    models.Alert.created_at >= (now - timedelta(minutes=30)),
                )
                .order_by(models.Alert.created_at.desc())
                .first()
            )
            if not recent_email:
                sent = False
                try:
                    sent = _send_email_alert(
                        subject=f"[Stock Journal] {alert_title}",
                        body=f"{alert_body}\n\nConfidence: {row.confidence}\n",
                    )
                except Exception:
                    sent = False
                db.add(
                    models.Alert(
                        symbol=sym,
                        title=alert_title,
                        body=alert_body,
                        priority=priority,
                        channel="email",
                        sent=sent,
                    )
                )
    db.commit()

    return schemas.GenerateSignalsResponse(created=created, message="Signals generated")


@app.get("/scanner/signals", response_model=List[schemas.SignalResponse])
def list_signals(limit: int = 50, db: Session = Depends(get_db)):
    rows = db.query(models.Signal).order_by(models.Signal.created_at.desc()).limit(limit).all()
    return rows


@app.get("/alerts", response_model=List[schemas.AlertResponse])
def list_alerts(unread_only: bool = False, limit: int = 100, db: Session = Depends(get_db)):
    q = db.query(models.Alert).order_by(models.Alert.created_at.desc())
    if unread_only:
        q = q.filter(models.Alert.read == False)  # noqa: E712
    return q.limit(limit).all()


@app.post("/alerts/{alert_id}/read", response_model=schemas.AlertResponse)
def mark_alert_read(alert_id: int, request: schemas.MarkAlertReadRequest, db: Session = Depends(get_db)):
    alert = db.query(models.Alert).filter(models.Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.read = request.read
    db.commit()
    db.refresh(alert)
    return alert


@app.post("/alerts/test-email")
def test_email(request: schemas.TestEmailRequest):
    news, movers, advice = _fetch_digest_data(
        limit_movers=max(1, request.limit_movers),
        limit_news=max(1, request.limit_news),
    )
    body = _format_digest_email_text(request.greeting, news, movers, advice)
    extra = (request.body or "").strip()
    # Swagger / OpenAPI UIs often pre-fill optional strings with the literal "string".
    if extra.casefold() == "string":
        extra = ""
    if extra:
        body = body.rstrip() + "\n\n---\n" + extra + "\n"
    sent = _send_email_alert(request.subject, body)
    return {"sent": sent}
