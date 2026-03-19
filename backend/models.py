from sqlalchemy import Column, Integer, String, Float, DateTime  # column types
from sqlalchemy.sql import func  # for auto timestamps
from database import Base        # parent class from database.py

class WatchlistItem(Base):
    __tablename__ = "watchlist"          # name of the table in the database

    id = Column(Integer, primary_key=True, index=True)  # unique ID, auto-incremented
    symbol = Column(String, unique=True, nullable=False) # stock ticker e.g. "AAPL"
    added_at = Column(DateTime, server_default=func.now()) # timestamp, set automatically

class Trade(Base):
    __tablename__ = "trades"             # name of the table in the database

    id = Column(Integer, primary_key=True, index=True)  # unique ID, auto-incremented
    symbol = Column(String, nullable=False)              # stock ticker e.g. "AAPL"
    entry_price = Column(Float, nullable=False)          # price you bought at
    exit_price = Column(Float, nullable=True)            # price you sold at (optional)
    quantity = Column(Integer, nullable=False)            # number of shares
    notes = Column(String, nullable=True)                # your trade notes (optional)
    traded_at = Column(DateTime, server_default=func.now()) # timestamp, set automatically
