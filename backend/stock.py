import yfinance as yf
from datetime import datetime, timedelta

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


def get_stock_history(symbol: str, period: str, interval: str = "1d") -> list:
    ticker = yf.Ticker(symbol)
    if period == "7d":                                                        # yfinance has no native 7d period
        end = datetime.today()
        start = end - timedelta(days=7)
        hist = ticker.history(start=start, end=end, interval=interval)
    else:
        hist = ticker.history(period=period, interval=interval)

    return [
        {
            "date": index.strftime("%Y-%m-%d %H:%M") if interval == "1h" else str(index.date()),  # include time for hourly
            "close": round(row["Close"], 2)
        }
        for index, row in hist.iterrows()
    ]

