from datetime import datetime
from typing import Optional, Any
from sqlalchemy import String, Float, Integer, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

class Stock(Base):
    __tablename__ = "stocks"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String, unique=True, index=True)
    name: Mapped[str] = mapped_column(String)
    type: Mapped[str] = mapped_column(String)  # "stock" or "etf"
    exchange: Mapped[str] = mapped_column(String, default="LSE")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    positions: Mapped[list["Position"]] = relationship(back_populates="stock")
    trades: Mapped[list["Trade"]] = relationship(back_populates="stock")
    snapshots: Mapped[list["MarketSnapshot"]] = relationship(back_populates="stock")

class Position(Base):
    __tablename__ = "positions"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id"))
    quantity: Mapped[float] = mapped_column(Float)
    entry_price: Mapped[float] = mapped_column(Float)
    entry_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    current_price: Mapped[float] = mapped_column(Float)
    unrealized_pnl: Mapped[float] = mapped_column(Float)
    
    stock: Mapped["Stock"] = relationship(back_populates="positions")

class Trade(Base):
    __tablename__ = "trades"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id"))
    action: Mapped[str] = mapped_column(String)  # "BUY" or "SELL"
    quantity: Mapped[float] = mapped_column(Float)
    price: Mapped[float] = mapped_column(Float)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    ai_reasoning: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    escalated: Mapped[bool] = mapped_column(Boolean, default=False)
    
    stock: Mapped["Stock"] = relationship(back_populates="trades")

class MarketSnapshot(Base):
    __tablename__ = "market_snapshots"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id"))
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[int] = mapped_column(Integer)
    
    stock: Mapped["Stock"] = relationship(back_populates="snapshots")

class AIDecision(Base):
    __tablename__ = "ai_decisions"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    ai_type: Mapped[str] = mapped_column(String)  # "local" or "remote"
    symbol: Mapped[str] = mapped_column(String)
    context: Mapped[dict[str, Any]] = mapped_column(JSON)
    response: Mapped[dict[str, Any]] = mapped_column(JSON)
    decision: Mapped[str] = mapped_column(String)  # "BUY", "SELL", "HOLD"
    confidence: Mapped[float] = mapped_column(Float)
