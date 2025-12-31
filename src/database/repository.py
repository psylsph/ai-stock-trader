"""Database repository for managing database operations."""

from typing import List
from datetime import datetime, timedelta

from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from src.database.models import Base, Stock, Position, Trade, AIDecision


class DatabaseRepository:
    """Repository for managing database operations."""

    def __init__(self, db_url: str):
        """Initialize the database repository.

        Args:
            db_url: The database connection URL.
        """
        self.engine = create_async_engine(db_url)
        self.session_maker = async_sessionmaker(self.engine, expire_on_commit=False)

    async def init_db(self):
        """Initialize the database schema."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def reset_db(self):
        """Reset the database by dropping and recreating all tables."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

    async def get_active_stocks(self) -> List[Stock]:
        """Get all active stocks from database.

        Returns:
            List of active Stock objects.
        """
        async with self.session_maker() as session:
            result = await session.execute(select(Stock).where(Stock.is_active is True))  # type: ignore[arg-type]
            return list(result.scalars().all())

    async def get_or_create_stock(self, symbol: str, name: str, type_: str = "stock") -> Stock:
        """Get an existing stock by symbol or create a new one.

        Args:
            symbol: The stock symbol.
            name: The stock name.
            type_: The stock type (default: "stock").

        Returns:
            The Stock object.
        """
        async with self.session_maker() as session:
            result = await session.execute(select(Stock).where(Stock.symbol == symbol))
            stock = result.scalar_one_or_none()

            if not stock:
                stock = Stock(symbol=symbol, name=name, type=type_)
                session.add(stock)
                await session.commit()
                await session.refresh(stock)

            return stock

    async def get_positions(self) -> List[Position]:
        """Get all positions from the database.

        Returns:
            List of Position objects with related Stock data.
        """
        async with self.session_maker() as session:
            result = await session.execute(
                select(Position).options(selectinload(Position.stock))
            )
            return list(result.scalars().all())

    async def log_trade(self, trade: Trade):
        """Log a trade to the database.

        Args:
            trade: The Trade object to log.
        """
        async with self.session_maker() as session:
            session.add(trade)
            await session.commit()

    async def log_decision(self, decision: AIDecision):
        """Log an AI decision to the database.

        Args:
            decision: The AIDecision object to log.
        """
        async with self.session_maker() as session:
            session.add(decision)
            await session.commit()

    async def get_all_decisions(self) -> List[AIDecision]:
        """Get all AI decisions from the database.

        Returns:
            List of AIDecision objects.
        """
        async with self.session_maker() as session:
            result = await session.execute(select(AIDecision))
            return list(result.scalars().all())

    async def update_decision_with_validation(
        self,
        symbol: str,
        remote_validation_decision: str,
        remote_validation_comments: str,
        requires_manual_review: bool
    ):
        """Update existing AIDecision with remote validation results."""
        async with self.session_maker() as session:
            stmt = (
                select(AIDecision)
                .where(and_(AIDecision.symbol == symbol, AIDecision.ai_type == "local"))
                .order_by(AIDecision.timestamp.desc())
            )
            result = await session.execute(stmt)
            decision = result.scalar_one_or_none()

            if decision:
                decision.remote_validation_decision = remote_validation_decision
                decision.remote_validation_comments = remote_validation_comments
                decision.validation_timestamp = datetime.utcnow()
                decision.requires_manual_review = requires_manual_review
                await session.commit()

    async def get_pending_decisions(self, timeout_minutes: int = 60) -> List[AIDecision]:
        """Get decisions awaiting manual review that haven't timed out."""
        timeout_threshold = datetime.utcnow() - timedelta(minutes=timeout_minutes)
        async with self.session_maker() as session:
            result = await session.execute(
                select(AIDecision).where(
                    and_(
                        AIDecision.requires_manual_review is True,
                        AIDecision.executed is False,
                        or_(
                            AIDecision.manual_review_timeout.is_(None),
                            AIDecision.manual_review_timeout > timeout_threshold
                        )
                    )
                )
            )
            return list(result.scalars().all())

    async def mark_decision_executed(self, symbol: str):
        """Mark a decision as executed (for completed trades)."""

        async with self.session_maker() as session:
            stmt = (
                select(AIDecision)
                .where(AIDecision.symbol == symbol)
                .order_by(AIDecision.timestamp.desc())
            )
            result = await session.execute(stmt)
            decision = result.scalar_one_or_none()

            if decision:
                decision.executed = True
                await session.commit()

    async def timeout_pending_decision(self, symbol: str):
        """Mark a pending decision as timed out (auto-rejected)."""

        async with self.session_maker() as session:
            stmt = (
                select(AIDecision)
                .where(AIDecision.symbol == symbol)
                .order_by(AIDecision.timestamp.desc())
            )
            result = await session.execute(stmt)
            decision = result.scalar_one_or_none()

            if decision:
                decision.remote_validation_decision = "TIMEOUT"
                decision.remote_validation_comments = "Auto-rejected: No manual approval within 1 hour"
                decision.executed = False
                await session.commit()

    async def close(self):
        """Close the database engine and dispose of all connections."""
        await self.engine.dispose()
