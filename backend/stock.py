import yfinance as yf 

def get_stock_price(symbol: str) -> dict:
    ticker = yf.Ticker(symbol)
    data = ticker.fast_info

    return {
        "symbol": symbol.upper(),               # standardize to uppercase e.g. "aapl" -> "AAPL"
        "price": data.last_price,               # most recent price
        "previous_close": data.previous_close,  # yesterday's closing price
        "change": round(data.last_price - data.previous_close, 2),  # price change
        "change_pct": round(                    # percentage change
            (data.last_price - data.previous_close) / data.previous_close * 100, 2
        ),
    }


def validate_symbol(symbol: str) -> bool:
    ticker = yf.Ticker(symbol) 
    data = ticker.fast_info  
    return data.last_price is not None


