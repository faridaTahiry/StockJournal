from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import anthropic

from config import ANTHROPIC_API_KEY


client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def build_signal_prompt(
    *,
    movers: List[dict],
    news_by_symbol: Dict[str, List[dict]],
    social_by_symbol: Dict[str, List[dict]],
) -> str:
    return (
        "You are a day-trading scanner. Your job is to produce a short list of stocks to watch today.\n"
        "Use price/percent move (from movers) as primary evidence, and use catalysts (news/social) only if recent.\n"
        "Do NOT give financial advice. Be concise.\n\n"
        "Return ONLY valid JSON with this schema:\n"
        "{\n"
        '  "signals": [\n'
        "    {\n"
        '      "symbol": "TSLA",\n'
        '      "signal_type": "watch|breakout|mean_reversion|news_spike",\n'
        '      "confidence": 0.0,\n'
        '      "rationale": "1-3 sentences",\n'
        '      "key_levels": {"support": [..], "resistance": [..]},\n'
        '      "catalysts": {"news": [..], "social": [..]}\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        f"Movers:\n{json.dumps(movers, ensure_ascii=False)}\n\n"
        f"NewsBySymbol:\n{json.dumps(news_by_symbol, ensure_ascii=False)}\n\n"
        f"SocialBySymbol:\n{json.dumps(social_by_symbol, ensure_ascii=False)}\n"
    )


def generate_signals_json(
    *,
    movers: List[dict],
    news_by_symbol: Dict[str, List[dict]],
    social_by_symbol: Dict[str, List[dict]],
    model: str = "claude-sonnet-4-6",
    max_tokens: int = 1200,
) -> dict:
    prompt = build_signal_prompt(movers=movers, news_by_symbol=news_by_symbol, social_by_symbol=social_by_symbol)
    resp = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system="You output JSON only.",
        messages=[{"role": "user", "content": prompt}],
    )
    raw = (resp.content[0].text or "").strip()
    if not raw:
        raise ValueError("LLM returned empty response text")

    # Some model/proxy failures or safety wrappers can prepend/append text.
    # Best-effort: parse the first top-level JSON object in the response.
    start = raw.find("{")
    end = raw.rfind("}")
    candidate = raw[start : end + 1] if start != -1 and end != -1 and end > start else raw
    try:
        return json.loads(candidate)
    except json.JSONDecodeError as e:
        snippet = raw[:1000]
        raise ValueError(f"Failed to parse LLM JSON. Raw response (first 1000 chars): {snippet}") from e

