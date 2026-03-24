from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey  # column types
from sqlalchemy.sql import func  # for auto timestamps
from database import Base        # parent class from database.py
from sqlalchemy.orm import relationship

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


class UniverseSymbol(Base):
    __tablename__ = "universe_symbols"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, unique=True, nullable=False, index=True)
    exchange = Column(String, nullable=True)
    active = Column(Boolean, nullable=False, server_default="1", index=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class ScanSnapshot(Base):
    __tablename__ = "scan_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    run_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)
    triggered_by = Column(String, nullable=False)  # "schedule" | "on_demand"
    window = Column(String, nullable=False)  # "5m" | "15m" | "1h" | "1d"
    universe_size = Column(Integer, nullable=False)
    candidate_count = Column(Integer, nullable=False, server_default="0")

    results = relationship("ScanResult", back_populates="snapshot", cascade="all, delete-orphan")


class ScanResult(Base):
    __tablename__ = "scan_results"

    id = Column(Integer, primary_key=True, index=True)
    snapshot_id = Column(Integer, ForeignKey("scan_snapshots.id"), nullable=False, index=True)
    symbol = Column(String, nullable=False, index=True)

    last_price = Column(Float, nullable=True)
    change_abs = Column(Float, nullable=True)
    change_pct = Column(Float, nullable=True)

    score = Column(Float, nullable=True)  # for future ranking beyond raw change

    snapshot = relationship("ScanSnapshot", back_populates="results")


class NewsItem(Base):
    __tablename__ = "news_items"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String, nullable=False, index=True)
    title = Column(String, nullable=False)
    url = Column(String, nullable=False, unique=True, index=True)
    published_at = Column(DateTime, nullable=False, index=True)
    summary = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    mentions = relationship("NewsMention", back_populates="news_item", cascade="all, delete-orphan")


class NewsMention(Base):
    __tablename__ = "news_mentions"

    id = Column(Integer, primary_key=True, index=True)
    news_item_id = Column(Integer, ForeignKey("news_items.id"), nullable=False, index=True)
    symbol = Column(String, nullable=False, index=True)

    news_item = relationship("NewsItem", back_populates="mentions")


class SocialPost(Base):
    __tablename__ = "social_posts"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String, nullable=False, index=True)  # e.g. "manual", "stocktwits"
    author = Column(String, nullable=True, index=True)
    external_id = Column(String, nullable=True, unique=True, index=True)  # provider ID if present
    content = Column(String, nullable=False)
    url = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, index=True)  # when post was created
    ingested_at = Column(DateTime, server_default=func.now(), nullable=False)

    mentions = relationship("SocialMention", back_populates="post", cascade="all, delete-orphan")


class SocialMention(Base):
    __tablename__ = "social_mentions"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("social_posts.id"), nullable=False, index=True)
    symbol = Column(String, nullable=False, index=True)

    post = relationship("SocialPost", back_populates="mentions")


class Signal(Base):
    __tablename__ = "signals"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)
    snapshot_id = Column(Integer, ForeignKey("scan_snapshots.id"), nullable=True, index=True)
    symbol = Column(String, nullable=False, index=True)
    signal_type = Column(String, nullable=False)  # "watch" | "breakout" | "mean_reversion" | "news_spike"
    confidence = Column(Float, nullable=True)
    rationale = Column(String, nullable=False)
    key_levels = Column(String, nullable=True)  # JSON-ish string for now
    catalysts = Column(String, nullable=True)  # JSON-ish string for now


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)
    symbol = Column(String, nullable=False, index=True)
    title = Column(String, nullable=False)
    body = Column(String, nullable=False)
    priority = Column(String, nullable=False, server_default="normal")  # normal | high
    channel = Column(String, nullable=False, server_default="in_app")  # in_app | email
    sent = Column(Boolean, nullable=False, server_default="0")
    read = Column(Boolean, nullable=False, server_default="0", index=True)

