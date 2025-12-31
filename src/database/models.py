"""Database models for the AI Stock Trader application."""

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import String, Float, Integer, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all database models."""


class Stock(Base):
    """Model representing a stock or ETF."""

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
    """Model representing a trading position."""

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
    """Model representing a trade transaction."""

    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(primary_key=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id"))
    action: Mapped[str] = mapped_column(String)  # "BUY" or "SELL"
    quantity: Mapped[float] = mapped_column(Float)
    price: Mapped[float] = mapped_column(Float)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    ai_reasoning: Mapped[str | None] = mapped_column(String, nullable=True)
    escalated: Mapped[bool] = mapped_column(Boolean, default=False)

    stock: Mapped["Stock"] = relationship(back_populates="trades")


class MarketSnapshot(Base):
    """Model representing a market data snapshot."""

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
    """Model representing an AI trading decision."""

    __tablename__ = "ai_decisions"

    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    ai_type: Mapped[str] = mapped_column(String)  # "local" or "remote"
    symbol: Mapped[str] = mapped_column(String)
    context: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=True)
    response: Mapped[dict[str, Any]] = mapped_column(JSON)
    decision: Mapped[str] = mapped_column(String)  # "BUY", "SELL", "HOLD"
    confidence: Mapped[float] = mapped_column(Float)

    remote_validation_decision: Mapped[str | None] = mapped_column(String, nullable=True)
    remote_validation_comments: Mapped[str | None] = mapped_column(String, nullable=True)
    validation_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    requires_manual_review: Mapped[bool] = mapped_column(Boolean, default=False)
    executed: Mapped[bool] = mapped_column(Boolean, default=False)
    manual_review_timeout: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
