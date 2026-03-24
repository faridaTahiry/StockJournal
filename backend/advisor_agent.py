from __future__ import annotations

import json
from datetime import datetime
from typing import Dict, List

import anthropic

from config import ANTHROPIC_API_KEY


client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def build_daytrader_advice(movers: List[Dict], news: List[Dict]) -> Dict:
    prompt = (
        "You are a day-trading assistant. Combine top movers and latest important news to suggest stocks to watch.\n"
        "Focus on intraday setups, catalysts, execution levels, and risk discipline.\n"
        "Output should be practical and trustworthy for a day trader: specific, concise, and risk-aware.\n"
        "Do NOT provide financial advice guarantees.\n\n"
        "Return JSON only with schema:\n"
        "{\n"
        '  "summary": "short market summary",\n'
        '  "suggestions": [\n'
        "    {\n"
        '      "symbol": "AAPL",\n'
        '      "setup": "breakout|mean_reversion|momentum|news_reaction",\n'
        '      "confidence": 0-1,\n'
        '      "bias": "long|short|neutral",\n'
        '      "reason": "one sentence: move + volume + catalyst context",\n'
        '      "levels": { "entry_zone": "...", "support": "...", "resistance": "..." },\n'
        '      "plan": "short actionable watch plan",\n'
        '      "risk_note": "risk and invalidation",\n'
        '      "catalysts": ["..."],\n'
        '      "metrics": { "relative_volume": 0.0, "dollar_volume": "high|medium|low", "spread": "tight|normal|wide" }\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        f"Movers:\n{json.dumps(movers, ensure_ascii=False)}\n\n"
        f"News:\n{json.dumps(news, ensure_ascii=False)}\n"
    )
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1300,
        temperature=0.2,
        system="Return strict JSON only.",
        messages=[{"role": "user", "content": prompt}],
    )
    raw = (resp.content[0].text or "").strip()
    start = raw.find("{")
    end = raw.rfind("}")
    candidate = raw[start : end + 1] if start != -1 and end != -1 and end > start else raw
    return json.loads(candidate)


def fallback_daytrader_advice(movers: List[Dict], news: List[Dict]) -> Dict:
    top = movers[: min(5, len(movers))]
    suggestions = []
    for m in top:
        symbol = m.get("symbol", "")
        if not symbol:
            continue
        chg = float(m.get("change_pct") or 0.0)
        setup = "momentum" if abs(chg) >= 3 else "news_reaction"
        bias = "long" if chg > 0 else ("short" if chg < 0 else "neutral")
        related_news = [n for n in news if symbol in (n.get("title", "") + " " + str(n.get("url", "")))]
        catalyst_titles = [n.get("title", "") for n in related_news[:2]]
        suggestions.append(
            {
                "symbol": symbol,
                "setup": setup,
                "confidence": min(0.8, 0.45 + min(0.3, abs(chg) / 20.0)),
                "bias": bias,
                "reason": f"{'Up' if chg >= 0 else 'Down'} {abs(chg):.2f}% on elevated activity; monitor for continuation vs fade.",
                "levels": {
                    "entry_zone": "Break above intraday high on volume confirmation",
                    "support": "Near VWAP / prior pullback low",
                    "resistance": "Near recent high extension",
                },
                "plan": "Watch first pullback/continuation level and confirm with volume before entry.",
                "risk_note": "Use tight stop based on intraday invalidation; avoid chasing extended candles.",
                "catalysts": catalyst_titles,
                "metrics": {
                    "relative_volume": round(max(1.0, abs(chg) / 3.0), 2),
                    "dollar_volume": "high" if (m.get("volume") or 0) > 5_000_000 else "medium",
                    "spread": "normal",
                },
            }
        )

    return {
        "summary": "Fallback advisor generated from mover strength and recent headline context.",
        "suggestions": suggestions,
    }

