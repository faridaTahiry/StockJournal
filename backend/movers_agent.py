from __future__ import annotations

import json
import re
from typing import Dict, List
from urllib.parse import parse_qs, urlparse

import anthropic
import requests
from bs4 import BeautifulSoup

from config import ANTHROPIC_API_KEY


client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def _to_float(value):
    try:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        cleaned = str(value).replace("%", "").replace(",", "").strip()
        return float(cleaned)
    except Exception:
        return None


def fetch_yahoo_predefined(scr_id: str, count: int = 50) -> List[Dict]:
    url = f"https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved?count={count}&scrIds={scr_id}"
    try:
        res = requests.get(url, timeout=12, headers={"User-Agent": "stock-journal/1.0"})
        res.raise_for_status()
        data = res.json()
        quotes = data.get("finance", {}).get("result", [{}])[0].get("quotes", [])
    except Exception:
        return []

    out = []
    for q in quotes:
        sym = (q.get("symbol") or "").upper().strip()
        if not sym:
            continue
        out.append(
            {
                "symbol": sym,
                "price": _to_float(q.get("regularMarketPrice")),
                "change_pct": _to_float(q.get("regularMarketChangePercent")),
                "volume": _to_float(q.get("regularMarketVolume")),
                "source": f"yahoo:{scr_id}",
            }
        )
    return out


def fetch_finviz_top_gainers(limit: int = 80) -> List[Dict]:
    """
    Finviz source: extract symbols from top gainers screener page.
    We intentionally keep this parser lightweight to tolerate page changes.
    """
    url = "https://finviz.com/screener.ashx?v=111&s=ta_topgainers"
    try:
        res = requests.get(url, timeout=12, headers={"User-Agent": "stock-journal/1.0", "Referer": "https://finviz.com/"})
        res.raise_for_status()
    except Exception:
        return []

    soup = BeautifulSoup(res.text, "html.parser")
    out: List[Dict] = []
    seen = set()
    for a in soup.select('a[href*="quote.ashx?t="]'):
        href = a.get("href", "")
        parsed = urlparse(href if href.startswith("http") else f"https://finviz.com/{href.lstrip('/')}")
        ticker = parse_qs(parsed.query).get("t", [""])[0].upper().strip()
        ticker = ticker.replace(".", "-")
        if not ticker or ticker in seen:
            continue
        seen.add(ticker)
        out.append({"symbol": ticker, "price": None, "change_pct": None, "volume": None, "source": "finviz:top_gainers"})
        if len(out) >= limit:
            break
    return out


def merge_mover_candidates(items: List[Dict]) -> List[Dict]:
    by_symbol: Dict[str, Dict] = {}
    for it in items:
        sym = it["symbol"]
        cur = by_symbol.get(sym)
        if not cur:
            by_symbol[sym] = {
                "symbol": sym,
                "price": it.get("price"),
                "change_pct": it.get("change_pct"),
                "volume": it.get("volume"),
                "sources": [it.get("source")] if it.get("source") else [],
            }
            continue

        # Prefer non-null data from newest observed source.
        for key in ("price", "change_pct", "volume"):
            if cur.get(key) is None and it.get(key) is not None:
                cur[key] = it.get(key)
        src = it.get("source")
        if src and src not in cur["sources"]:
            cur["sources"].append(src)

    return list(by_symbol.values())


def rank_movers_with_llm(items: List[Dict], limit: int = 30) -> List[Dict]:
    prompt = (
        "Rank these stock mover candidates for intraday watch priority.\n"
        "Use strongest weight for large/credible move + multi-source confirmation + volume context.\n"
        "Return JSON only:\n"
        '{ "items": [ { "symbol": "...", "priority_score": 0-100, "why": "short reason" } ] }\n\n'
        f"Candidates:\n{json.dumps(items, ensure_ascii=False)}"
    )
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        system="You are a day-trading mover ranking agent. Return valid JSON only.",
        messages=[{"role": "user", "content": prompt}],
    )
    raw = (resp.content[0].text or "").strip()
    start = raw.find("{")
    end = raw.rfind("}")
    candidate = raw[start : end + 1] if start != -1 and end != -1 and end > start else raw
    parsed = json.loads(candidate)
    rows = parsed.get("items", [])
    rows = [r for r in rows if r.get("symbol")]
    return rows[: max(1, limit)]


def fallback_rank_movers(items: List[Dict], limit: int = 30) -> List[Dict]:
    scored = []
    for it in items:
        chg = abs(float(it["change_pct"])) if it.get("change_pct") is not None else 0.0
        src_bonus = min(10.0, 2.5 * len(it.get("sources", [])))
        vol_bonus = 5.0 if (it.get("volume") or 0) and (it.get("volume") or 0) > 1_000_000 else 0.0
        priority = min(100.0, chg * 4.0 + src_bonus + vol_bonus)
        scored.append(
            {
                "symbol": it["symbol"],
                "priority_score": round(priority, 2),
                "why": "Fallback rank using move magnitude, source overlap, and volume.",
            }
        )
    scored.sort(key=lambda x: x["priority_score"], reverse=True)
    return scored[: max(1, limit)]

