from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any
from pydantic import BaseModel
from src.database.repository import DatabaseRepository
from src.database.models import Trade, Position, Stock
from src.market.data_fetcher import MarketDataFetcher

class Order(BaseModel):
    id: str
    symbol: str
    action: str  # "BUY" or "SELL"
    quantity: float
    price: float
    timestamp: datetime
    status: str = "FILLED"

class Broker(ABC):
    @abstractmethod
    async def buy(self, symbol: str, quantity: float, price: float) -> Order: ...
    
    @abstractmethod
    async def sell(self, symbol: str, quantity: float, price: float) -> Order: ...
    
    @abstractmethod
    async def get_account_balance(self) -> float: ...
    
    @abstractmethod
    async def get_positions(self) -> List[Dict[str, Any]]: ...

class PaperTrader(Broker):
    def __init__(self, repo: DatabaseRepository, market_data: MarketDataFetcher, initial_balance: float = 10000.0):
        self.repo = repo
        self.market_data = market_data
        self.initial_balance = initial_balance
        # Note: In a real app, balance needs to be persisted in DB. 
        # For simplicity, we'll assume balance is calculated from trades or stored in a User model (not yet created).
        # We will track cash in a simple variable for this session, but in reality it should be in DB.
        self._current_balance = initial_balance 

    async def get_account_balance(self) -> float:
        # TODO: Retrieve from DB to be persistent
        return self._current_balance

    async def get_positions(self) -> List[Dict[str, Any]]:
        db_positions = await self.repo.get_positions()
        # Enriched with current market data if needed
        return [{
            "symbol": p.stock.symbol, 
            "quantity": p.quantity,
            "entry_price": p.entry_price
        } for p in db_positions]

    async def buy(self, symbol: str, quantity: float, price: float) -> Order:
        cost = quantity * price
        if cost > self._current_balance:
            raise ValueError(f"Insufficient funds: {cost} > {self._current_balance}")
        
        self._current_balance -= cost
        
        # Update DB
        stock = await self.repo.get_or_create_stock(symbol, symbol) # Name fallback
        
        trade = Trade(
            stock_id=stock.id,
            action="BUY",
            quantity=quantity,
            price=price,
            timestamp=datetime.now(timezone.utc)
        )
        await self.repo.log_trade(trade)
        
        # Update Position logic should be handled by PositionManager usually, but for simplicity here:
        # We'll rely on PositionManager or workflow to update the Position table based on this trade.
        # But wait, Broker usually executes, PositionManager monitors. 
        # For PaperTrader, it needs to update the "broker" state. 
        # Since our "broker" state IS the DB (mostly), we should update it or let the caller update it.
        # Let's return the Order and let PositionManager handle DB updates for positions.
        
        return Order(
            id=f"paper-{datetime.now(timezone.utc).timestamp()}",
            symbol=symbol,
            action="BUY",
            quantity=quantity,
            price=price,
            timestamp=datetime.now(timezone.utc)
        )

    async def sell(self, symbol: str, quantity: float, price: float) -> Order:
        revenue = quantity * price
        self._current_balance += revenue
        
        stock = await self.repo.get_or_create_stock(symbol, symbol)
        
        trade = Trade(
            stock_id=stock.id,
            action="SELL",
            quantity=quantity,
            price=price,
            timestamp=datetime.now(timezone.utc)
        )
        await self.repo.log_trade(trade)
        
        return Order(
            id=f"paper-{datetime.now(timezone.utc).timestamp()}",
            symbol=symbol,
            action="SELL",
            quantity=quantity,
            price=price,
            timestamp=datetime.now(timezone.utc)
        )
