from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import re
from typing import Iterable, List, Optional


_URL_RE = re.compile(r"https?://\\S+")
_CASH_TAG_RE = re.compile(r"\\$([A-Z]{1,5})\\b")


@dataclass(frozen=True)
class ParsedSocialPost:
    source: str
    author: Optional[str]
    external_id: Optional[str]
    content: str
    url: Optional[str]
    created_at: datetime  # UTC


def extract_symbols_from_post(text: str, known_symbols: Iterable[str]) -> List[str]:
    """
    Prefer $CASH tags, then fall back to known-universe symbol matching.
    """
    if not text:
        return []

    upper = _URL_RE.sub(" ", text.upper())
    hits = {m.group(1) for m in _CASH_TAG_RE.finditer(upper)}

    known = {s.upper() for s in known_symbols if s}
    for sym in known:
        if re.search(rf"\\b{re.escape(sym)}\\b", upper):
            hits.add(sym)

    return sorted(hits)


def filter_recent(posts: List[ParsedSocialPost], *, max_age_hours: int = 6) -> tuple[List[ParsedSocialPost], int]:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=max_age_hours)
    recent: List[ParsedSocialPost] = []
    stale = 0
    for p in posts:
        if p.created_at < cutoff:
            stale += 1
            continue
        recent.append(p)
    return recent, stale

