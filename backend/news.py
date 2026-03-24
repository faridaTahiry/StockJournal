from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import re
from typing import Iterable, Optional, List, Tuple

import feedparser
import requests


DEFAULT_RSS_FEEDS: list[tuple[str, str]] = [
    ("SEC", "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&output=atom"),
    ("MarketWatch", "https://feeds.marketwatch.com/marketwatch/topstories/"),
    ("ReutersBusiness", "https://feeds.reuters.com/reuters/businessNews"),
]


_URL_RE = re.compile(r"https?://\S+")


@dataclass(frozen=True)
class ParsedNewsItem:
    source: str
    title: str
    url: str
    published_at: datetime
    summary: Optional[str]


def _to_utc(dt_struct) -> Optional[datetime]:
    if not dt_struct:
        return None
    try:
        return datetime(*dt_struct[:6], tzinfo=timezone.utc)
    except Exception:
        return None


def fetch_rss_items(
    feeds: Optional[List[Tuple[str, str]]] = None,
    *,
    timeout_s: int = 10,
) -> list[ParsedNewsItem]:
    feeds = feeds or DEFAULT_RSS_FEEDS
    out: list[ParsedNewsItem] = []

    for source, url in feeds:
        try:
            resp = requests.get(url, timeout=timeout_s, headers={"User-Agent": "stock-journal/1.0"})
            resp.raise_for_status()
            parsed = feedparser.parse(resp.text)

            for e in parsed.entries:
                title = (getattr(e, "title", "") or "").strip()
                link = (getattr(e, "link", "") or "").strip()
                summary = (getattr(e, "summary", None) or None)
                if summary:
                    summary = summary.strip()

                published = _to_utc(getattr(e, "published_parsed", None)) or _to_utc(getattr(e, "updated_parsed", None))
                if not (title and link and published):
                    continue

                out.append(
                    ParsedNewsItem(
                        source=source,
                        title=title,
                        url=link,
                        published_at=published,
                        summary=summary,
                    )
                )
        except Exception:
            continue

    return out


def extract_symbols(text: str, known_symbols: Iterable[str]) -> list[str]:
    """
    Extract symbols by intersecting known universe symbols with the text.
    This avoids most false positives from naive ALLCAPS tokenization.
    """
    if not text:
        return []

    cleaned = _URL_RE.sub(" ", text.upper())
    known = {s.upper() for s in known_symbols if s}

    hits: set[str] = set()
    for sym in known:
        if len(sym) < 1:
            continue
        # Word boundary match to avoid substrings.
        if re.search(rf"\\b{re.escape(sym)}\\b", cleaned):
            hits.add(sym)
        if re.search(rf"\\${re.escape(sym)}\\b", cleaned):
            hits.add(sym)

    return sorted(hits)


def filter_recent(items: list[ParsedNewsItem], *, max_age_hours: int = 24) -> tuple[list[ParsedNewsItem], int]:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=max_age_hours)
    recent: list[ParsedNewsItem] = []
    stale = 0
    for it in items:
        if it.published_at < cutoff:
            stale += 1
            continue
        recent.append(it)
    return recent, stale

