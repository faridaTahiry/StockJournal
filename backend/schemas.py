from pydantic import BaseModel, Field   # base class for all schemas
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


# --- Universe / Scanner ---

class UniverseSymbolCreate(BaseModel):
    symbol: str
    exchange: Optional[str] = None
    active: bool = True


class UniverseSymbolResponse(BaseModel):
    id: int
    symbol: str
    exchange: Optional[str] = None
    active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ScanResultResponse(BaseModel):
    symbol: str
    last_price: Optional[float] = None
    change_abs: Optional[float] = None
    change_pct: Optional[float] = None
    score: Optional[float] = None
    volume: Optional[float] = None
    avg_volume: Optional[float] = None
    relative_volume: Optional[float] = None


class ScanSnapshotResponse(BaseModel):
    id: int
    run_at: datetime
    triggered_by: str
    window: str
    universe_size: int
    candidate_count: int
    results: list[ScanResultResponse]

    class Config:
        from_attributes = True


class RunScannerRequest(BaseModel):
    window: str = "15m"  # "5m" | "15m" | "1h" | "1d"


class RunScannerResponse(BaseModel):
    snapshot_id: int
    message: str


# --- News ---

class NewsItemResponse(BaseModel):
    id: int
    source: str
    title: str
    url: str
    published_at: datetime
    summary: Optional[str] = None
    symbols: list[str] = []

    class Config:
        from_attributes = True


class IngestNewsResponse(BaseModel):
    ingested: int
    skipped_stale: int
    skipped_duplicate: int


class AgentNewsItemResponse(BaseModel):
    source: str
    title: str
    url: str
    published_at: datetime
    importance_score: float
    recency_score: float
    priority_score: float
    why: str


# --- Social (manual ingest for now; X automation later) ---

class SocialPostIngest(BaseModel):
    source: str = "manual"
    author: Optional[str] = None
    external_id: Optional[str] = None
    content: str
    url: Optional[str] = None
    created_at: datetime  # client should send UTC ISO; server enforces recency


class SocialPostResponse(BaseModel):
    id: int
    source: str
    author: Optional[str] = None
    external_id: Optional[str] = None
    content: str
    url: Optional[str] = None
    created_at: datetime
    symbols: list[str] = []

    class Config:
        from_attributes = True


class IngestSocialResponse(BaseModel):
    ingested: int
    skipped_stale: int
    skipped_duplicate: int


# --- Signals ---

class SignalResponse(BaseModel):
    id: int
    created_at: datetime
    snapshot_id: Optional[int] = None
    symbol: str
    signal_type: str
    confidence: Optional[float] = None
    rationale: str
    key_levels: Optional[str] = None
    catalysts: Optional[str] = None

    class Config:
        from_attributes = True


class GenerateSignalsRequest(BaseModel):
    limit: int = 20


class GenerateSignalsResponse(BaseModel):
    created: int
    message: str


# --- Alerts ---

class AlertResponse(BaseModel):
    id: int
    created_at: datetime
    symbol: str
    title: str
    body: str
    priority: str
    channel: str
    sent: bool
    read: bool

    class Config:
        from_attributes = True


class MarkAlertReadRequest(BaseModel):
    read: bool = True


class TestEmailRequest(BaseModel):
    subject: str = "[Automated] Stock Journal digest — your feedback helps improve our models"
    greeting: str = "Hello,"
    body: Optional[str] = Field(
        default=None,
        description="Optional notes appended after the digest. Omit or use null; clear Swagger's default if needed.",
        json_schema_extra={"examples": [None]},
    )
    limit_news: int = 12
    limit_movers: int = 12


# --- Agent Movers ---

class AgentMoverResponse(BaseModel):
    symbol: str
    price: Optional[float] = None
    change_pct: Optional[float] = None
    volume: Optional[float] = None
    sources: list[str] = []
    priority_score: float
    why: str


# --- Day Trader Advisor ---

class DayTraderSuggestionResponse(BaseModel):
    symbol: str
    setup: str
    confidence: float
    bias: str  # long | short | neutral
    reason: str
    levels: dict = {}
    plan: str
    risk_note: str
    catalysts: list[str] = []
    metrics: dict = {}


class DayTraderAdviceResponse(BaseModel):
    generated_at: datetime
    summary: str
    suggestions: list[DayTraderSuggestionResponse]
