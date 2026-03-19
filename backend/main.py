from fastapi import FastAPI, Depends, HTTPException   # FastAPI core — like [ApiController] in C#
from starlette.middleware.cors import CORSMiddleware   # handles cross-origin requests (frontend talking to backend)
from sqlalchemy.orm import Session                    # DB session type hint
from typing import List                               # like List<T> in C#
from pydantic import BaseModel                        # for ChatRequest schema

import models, schemas                               # our models and schemas
from database import engine, get_db                  # DB engine and session dependency
from agent import chat_with_agent                    # our agent function
from stock import get_stock_price, validate_symbol, get_stock_history


models.Base.metadata.create_all(bind= engine)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],          # only allow requests from our frontend
    allow_methods=["*"],                             # allow all HTTP methods (GET, POST, etc.)
    allow_headers=["*"],                             # allow all headers
)


@app.post("/watchlist", response_model=schemas.WatchlistItemResponse)
def add_to_watchlist(item : schemas.WatchlistItemCreate, db: Session = Depends(get_db)):
    if not validate_symbol(item.symbol):                                 # reject invalid tickers
        raise HTTPException(status_code=400, detail="Invalid stock symbol")
    
    db_item = models.WatchlistItem(symbol=item.symbol.upper())          # create new DB model instance
    db.add(db_item)                                                      # add to session — like .Add() in EF
    db.commit()                                                          # save to database — like .SaveChanges()
    db.refresh(db_item)                                                  # refresh with DB-generated values (id, timestamp)
    return db_item

@app.get("/watchlist", response_model=List[schemas.WatchlistItemResponse])  # like [HttpGet]
def get_watchlist(db: Session = Depends(get_db)):
    return db.query(models.WatchlistItem).all()                         # like dbContext.Watchlist.ToList()

@app.delete("/watchlist/{symbol}")                                       # like [HttpDelete("{symbol}")]
def remove_from_watchlist(symbol: str, db: Session = Depends(get_db)):
    item = db.query(models.WatchlistItem).filter(                       # like .Where() in LINQ
        models.WatchlistItem.symbol == symbol.upper()
    ).first()                                                            # like .FirstOrDefault()
    if not item:
        raise HTTPException(status_code=404, detail="Symbol not found")
    db.delete(item)                                                      # like .Remove() in EF
    db.commit()
    return {"message": f"Removed {symbol} from watchlist"}              # f"" is like $"" in C#

# --- Stock Price Endpoint ---

@app.get("/stock/{symbol}", response_model=schemas.StockResponse)       # like [HttpGet("{symbol}")]
def get_price(symbol: str):
    return get_stock_price(symbol)                                       # calls our yfinance function

# --- Trade Endpoints ---

@app.post("/trades", response_model=schemas.TradeResponse)
def log_trade(trade: schemas.TradeCreate, db: Session = Depends(get_db)):
    db_trade = models.Trade(**trade.model_dump())                        # ** unpacks dict into keyword args
    db.add(db_trade)
    db.commit()
    db.refresh(db_trade)
    return db_trade

@app.get("/trades", response_model=List[schemas.TradeResponse])
def get_trades(db: Session = Depends(get_db)):
    return db.query(models.Trade).all()

@app.delete("/trades/{trade_id}")
def delete_trade(trade_id: int, db: Session = Depends(get_db)):
    trade = db.query(models.Trade).filter(models.Trade.id == trade_id).first()
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    db.delete(trade)
    db.commit()
    return {"message": f"Trade {trade_id} deleted"}

# --- Agent Endpoint ---

class ChatRequest(BaseModel):                                            # simple schema for chat request
    message: str                                                         # the user's message

@app.post("/agent/chat")                                                 # like [HttpPost] in C#
def chat(request: ChatRequest, db: Session = Depends(get_db)):
    watchlist = db.query(models.WatchlistItem).all()                     # fetch user's watchlist from DB
    response = chat_with_agent(request.message, watchlist)               # send to agent with context
    return {"response": response}   


@app.get("/stock/{symbol}/history")
def get_history(symbol: str, period: str = "3mo", interval: str = "1d"):
    return get_stock_history(symbol, period, interval)
