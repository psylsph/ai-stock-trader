from datetime import datetime
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from src.database.models import Base, Stock, Position, Trade, AIDecision

class DatabaseRepository:
    def __init__(self, db_url: str):
        self.engine = create_async_engine(db_url)
        self.session_maker = async_sessionmaker(self.engine, expire_on_commit=False)

    async def init_db(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def reset_db(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

    async def get_active_stocks(self) -> List[Stock]:
        async with self.session_maker() as session:
            result = await session.execute(select(Stock).where(Stock.is_active == True))
            return list(result.scalars().all())

    async def get_or_create_stock(self, symbol: str, name: str, type_: str = "stock") -> Stock:
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
        async with self.session_maker() as session:
            result = await session.execute(
                select(Position).options(selectinload(Position.stock))
            )
            return list(result.scalars().all())

    async def log_trade(self, trade: Trade):
        async with self.session_maker() as session:
            session.add(trade)
            await session.commit()

    async def log_decision(self, decision: AIDecision):
        async with self.session_maker() as session:
            session.add(decision)
            await session.commit()
