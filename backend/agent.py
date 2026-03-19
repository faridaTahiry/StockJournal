import anthropic
from typing import Optional
from stock import get_stock_price
from config import ANTHROPIC_API_KEY

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

def build_context(watchlist: list) -> str:
    if not watchlist:
        return "The user has no stocks in their watchlist."
    
    lines = []

    for item in watchlist:
        try:
            data = get_stock_price(item.symbol)
            lines.append(                        # .append() is like .Add() in C#
                f"{data['symbol']}: ${data['price']} "
                f"({'+' if data['change_pct'] > 0 else ''}{data['change_pct']}%)"  # format change with + or - sign
            )

        except:
            lines.append(f"{item.symbol}: price unavailable")
        
    return "User's current watchlist:\n" + "\n".join(lines) 


def chat_with_agent(message: str, watchlist: list, focused_symbol: Optional[str] = None) -> str:
    context = build_context(watchlist)

    # if a symbol was dragged into the chat, focus the analysis on it
    focus_note = f"\nThe user is currently focused on {focused_symbol}. Prioritize analysis of this stock." if focused_symbol else ""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=f"""You are a stock market assistant helping a day trader analyze their portfolio.
        Be concise, data-driven, and clear. Do not give financial advice — always remind the user
        to do their own research.

        {context}{focus_note}""",                               # inject focus note into system prompt
        messages=[
            {"role": "user", "content": message}
        ]
    )

    return response.content[0].text