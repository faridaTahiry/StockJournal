from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Literal, Optional

import yfinance as yf


ScanWindow = Literal["5m", "15m", "1h", "1d"]


@dataclass(frozen=True)
class Mover:
    symbol: str
    last_price: Optional[float]
    change_abs: Optional[float]
    change_pct: Optional[float]
    score: Optional[float]


def _window_to_period_interval(window: ScanWindow) -> tuple[str, str, int]:
    """
    Returns (period, interval, lookback_bars).
    lookback_bars is how many bars back we compare for the window.
    """
    if window == "5m":
        return ("1d", "5m", 1)
    if window == "15m":
        return ("1d", "5m", 3)
    if window == "1h":
        return ("5d", "15m", 4)
    return ("1mo", "1d", 1)  # "1d" window uses 1d bars (yesterday close vs today)


def compute_movers(
    symbols: Iterable[str],
    *,
    window: ScanWindow = "15m",
    min_price: float = 20.0,
    limit: int = 50,
) -> list[Mover]:
    """
    Best-effort movers scan using yfinance. Designed for small-to-medium universes.
    """
    period, interval, lookback_bars = _window_to_period_interval(window)

    movers: list[Mover] = []

    # yfinance.download supports batching; it returns a multi-index frame for multiple tickers.
    symbols_list = [s.strip().upper() for s in symbols if s and s.strip()]
    if not symbols_list:
        return []

    df = yf.download(
        tickers=" ".join(symbols_list),
        period=period,
        interval=interval,
        group_by="ticker",
        threads=True,
        progress=False,
        auto_adjust=False,
        prepost=True,
    )

    # Pre-market / off-hours often yields empty intraday data. We'll best-effort fall back to
    # fast_info (last_price vs previous_close) so the scanner still produces candidates.
    if df is None or getattr(df, "empty", False):
        movers = []
        for sym in symbols_list:
            try:
                t = yf.Ticker(sym)
                info = t.fast_info
                last = getattr(info, "last_price", None)
                prev = getattr(info, "previous_close", None)
                if last is None or prev is None:
                    continue
                last = float(last)
                prev = float(prev)
                if last < min_price:
                    continue
                change_abs = last - prev
                change_pct = (change_abs / prev) * 100.0 if prev else None
                score = abs(change_pct) if change_pct is not None else None
                movers.append(
                    Mover(
                        symbol=sym,
                        last_price=last,
                        change_abs=round(change_abs, 4),
                        change_pct=round(change_pct, 4) if change_pct is not None else None,
                        score=round(score, 4) if score is not None else None,
                    )
                )
            except Exception:
                continue
        movers.sort(key=lambda m: (m.score is not None, m.score), reverse=True)
        return movers[: max(1, limit)]

    # Normalize access: for single ticker, columns aren't multi-indexed.
    is_multi = hasattr(df.columns, "levels") and len(getattr(df.columns, "levels", [])) > 1

    for sym in symbols_list:
        try:
            if is_multi:
                sub = df[sym].dropna()
                close = sub["Close"]
            else:
                sub = df.dropna()
                close = sub["Close"]

            # If the intraday series is empty/sparse (common pre-market), fall back to fast_info.
            if close.empty or len(close) <= lookback_bars:
                t = yf.Ticker(sym)
                info = t.fast_info
                last = getattr(info, "last_price", None)
                prev = getattr(info, "previous_close", None)
                if last is None or prev is None:
                    continue
                last = float(last)
                prev = float(prev)
                if last < min_price:
                    continue
                change_abs = last - prev
                change_pct = (change_abs / prev) * 100.0 if prev else None
                score = abs(change_pct) if change_pct is not None else None
                movers.append(
                    Mover(
                        symbol=sym,
                        last_price=last,
                        change_abs=round(change_abs, 4),
                        change_pct=round(change_pct, 4) if change_pct is not None else None,
                        score=round(score, 4) if score is not None else None,
                    )
                )
                continue

            last = float(close.iloc[-1])
            if last < min_price:
                continue

            prev = float(close.iloc[-(lookback_bars + 1)])
            change_abs = last - prev
            change_pct = (change_abs / prev) * 100.0 if prev else None

            # Simple score for now: absolute percent move.
            score = abs(change_pct) if change_pct is not None else None

            movers.append(
                Mover(
                    symbol=sym,
                    last_price=last,
                    change_abs=round(change_abs, 4),
                    change_pct=round(change_pct, 4) if change_pct is not None else None,
                    score=round(score, 4) if score is not None else None,
                )
            )
        except Exception:
            continue

    movers.sort(key=lambda m: (m.score is not None, m.score), reverse=True)
    return movers[: max(1, limit)]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)

