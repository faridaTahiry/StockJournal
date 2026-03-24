from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import List, Dict

import anthropic

from config import ANTHROPIC_API_KEY


client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def rank_news_items_with_llm(items: List[Dict]) -> List[Dict]:
    prompt = (
        "Rank these market news items by PRIORITY where priority heavily weights:\n"
        "1) importance to broad markets and liquid US stocks\n"
        "2) recency, where a very important event in last 5 hours should outrank older 24h items.\n"
        "3) cross-domain catalysts even when impact is indirect.\n\n"
        "Cross-domain catalysts to consider as HIGH impact when relevant:\n"
        "- new political policy, fiscal policy, tariffs/sanctions, elections, central-bank communication\n"
        "- regulation/legal actions (DOJ/FTC/SEC), antitrust, export controls\n"
        "- geopolitics/war/conflict escalation, energy shocks\n"
        "- cyber incidents/outages affecting major firms/infrastructure\n"
        "- climate/disaster/supply-chain disruptions\n"
        "- public health events that can affect labor/consumption/travel\n\n"
        "For each item, infer likely market transmission path (rates, growth, inflation, energy, specific sectors).\n"
        "Return JSON only with schema:\n"
        "{ \"items\": [ { \"url\": \"...\", \"importance_score\": 0-100, \"recency_score\": 0-100, \"priority_score\": 0-100, \"why\": \"short reason\" } ] }\n\n"
        f"NewsItems:\n{json.dumps(items, ensure_ascii=False)}"
    )
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1400,
        system="You are a financial news ranking agent. Return valid JSON only.",
        messages=[{"role": "user", "content": prompt}],
    )
    raw = (resp.content[0].text or "").strip()
    start = raw.find("{")
    end = raw.rfind("}")
    candidate = raw[start : end + 1] if start != -1 and end != -1 and end > start else raw
    parsed = json.loads(candidate)
    return parsed.get("items", [])


def fallback_rank_news(items: List[Dict]) -> List[Dict]:
    now = datetime.now(timezone.utc)
    ranked = []
    for it in items:
        published = datetime.fromisoformat(it["published_at"])
        age_h = max(0.0, (now - published).total_seconds() / 3600.0)
        recency = max(0.0, 100.0 - min(24.0, age_h) * (100.0 / 24.0))
        title = (it.get("title") or "").lower()
        # lightweight keyword-based importance heuristic
        importance = 40.0
        for kw, boost in [
            ("fed", 20),
            ("fomc", 20),
            ("cpi", 20),
            ("inflation", 15),
            ("jobs", 10),
            ("earnings", 15),
            ("guidance", 15),
            ("merger", 15),
            ("acquisition", 15),
            ("sec", 8),
            ("downgrade", 10),
            ("upgrade", 10),
            ("oil", 10),
            ("rates", 12),
            ("tariff", 18),
            ("sanction", 18),
            ("policy", 14),
            ("election", 12),
            ("regulation", 14),
            ("antitrust", 14),
            ("doj", 12),
            ("ftc", 12),
            ("export control", 14),
            ("war", 16),
            ("conflict", 14),
            ("cyber", 14),
            ("outage", 12),
            ("supply chain", 14),
            ("earthquake", 12),
            ("hurricane", 12),
            ("pandemic", 16),
        ]:
            if kw in title:
                importance += boost
        importance = min(100.0, importance)
        priority = round((importance * 0.6) + (recency * 0.4), 2)
        ranked.append(
            {
                "url": it["url"],
                "importance_score": round(importance, 2),
                "recency_score": round(recency, 2),
                "priority_score": priority,
                "why": "Fallback rank using keyword importance + recency weighting.",
            }
        )

    ranked.sort(key=lambda x: x["priority_score"], reverse=True)
    return ranked

