from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import List, Dict, Any
from pydantic import BaseModel
from src.database.repository import DatabaseRepository
from src.database.models import Trade
from src.market.data_fetcher import MarketDataFetcher
import json
import os


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

        # Load balance from portfolio.json if it exists
        portfolio_file = os.getenv("PORTFOLIO_FILE", "portfolio.json")
        saved_balance = None
        if os.path.exists(portfolio_file):
            try:
                with open(portfolio_file, 'r') as f:
                    data = json.load(f)
                    saved_balance = data.get("cash_balance")
                    # Validate that the saved balance is reasonable (not 0 when it shouldn't be)
                    if saved_balance is not None and saved_balance > 0:
                        self._current_balance = saved_balance
                    else:
                        self._current_balance = initial_balance
            except (json.JSONDecodeError, IOError):
                self._current_balance = initial_balance
        else:
            self._current_balance = initial_balance

    async def get_account_balance(self) -> float:
        return self._current_balance

    def update_balance(self, amount: float):
        """Update balance and save to portfolio.json"""
        self._current_balance = amount

        # Save to portfolio.json for persistence
        portfolio_file = os.getenv("PORTFOLIO_FILE", "portfolio.json")
        try:
            data = {}
            if os.path.exists(portfolio_file):
                with open(portfolio_file, 'r') as f:
                    data = json.load(f)
            data["cash_balance"] = self._current_balance
            data["timestamp"] = datetime.now(timezone.utc).isoformat()
            with open(portfolio_file, 'w') as f:
                json.dump(data, f, indent=4)
        except (json.JSONDecodeError, IOError) as e:
            print(f"[WARNING] Failed to save portfolio file: {e}")

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
        self.update_balance(self._current_balance)

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
        self.update_balance(self._current_balance)

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
