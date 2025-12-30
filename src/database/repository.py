"""Database repository for managing database operations."""

from typing import List

try:
    from sqlalchemy import select  # pylint: disable=import-error
    from sqlalchemy.orm import selectinload  # pylint: disable=import-error
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker  # pylint: disable=import-error
except ImportError:
    select = None
    selectinload = None
    create_async_engine = None
    async_sessionmaker = None

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
        """Get all active stocks from the database.

        Returns:
            List of active Stock objects.
        """
        async with self.session_maker() as session:
            result = await session.execute(select(Stock).where(Stock.is_active is True))
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
