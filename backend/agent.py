import anthropic  
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


def chat_with_agent(message: str, watchlist: list) -> str:
    context = build_context(watchlist)

    response = client.messages.create(                         # send request to Claude API
        model="claude-sonnet-4-6",                             # which Claude model to use
        max_tokens=1024,                                        # max length of response
        system=f"""You are a stock market assistant helping a day trader analyze their portfolio.
        Be concise, data-driven, and clear. Do not give financial advice — always remind the user 
        to do their own research.
        
        {context}""",                                           # system prompt gives Claude the watchlist context
        messages=[
            {"role": "user", "content": message}               # the user's actual question
        ]
    )

    return response.content[0].text 