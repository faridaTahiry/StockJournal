from pydantic import BaseModel          # base class for all schemas
from typing import Optional             # for optional fields
from datetime import datetime           # for timestamp fields

# --- Watchlist ---

class WatchlistItemCreate(BaseModel):
    symbol: str                         # only need the ticker to add to watchlist

class WatchlistItemResponse(BaseModel):
    id: int                             # included in response but not in create
    symbol: str
    added_at: datetime

    class Config:
        from_attributes = True          # lets Pydantic read SQLAlchemy model objects

# --- Trades ---

class TradeCreate(BaseModel):
    symbol: str                         # required fields when creating a trade
    entry_price: float
    quantity: int
    exit_price: Optional[float] = None  # optional — you may not have exited yet
    notes: Optional[str] = None         # optional trade notes

class TradeResponse(BaseModel):
    id: int                             # full trade data returned in responses
    symbol: str
    entry_price: float
    exit_price: Optional[float] = None
    quantity: int
    notes: Optional[str] = None
    traded_at: datetime

    class Config:
        from_attributes = True          # lets Pydantic read SQLAlchemy model objects


# --- Stock ---

class StockResponse(BaseModel):
    symbol: str
    price: float
    previous_close: float
    change: float
    change_pct: float
