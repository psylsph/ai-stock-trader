"""Tests for paper trading functionality."""

from unittest.mock import AsyncMock
import pytest
from src.trading.paper_trader import PaperTrader
from src.market.data_fetcher import MarketDataFetcher
from src.database.repository import DatabaseRepository
from src.database.models import Stock


class MockRepo(DatabaseRepository):
    """Mock repository for testing."""

    def __init__(self):
        self.get_or_create_stock = AsyncMock()
        self.log_trade = AsyncMock()
        self.get_positions = AsyncMock(return_value=[])


class MockFetcher(MarketDataFetcher):
    """Mock market data fetcher for testing."""

    async def get_quote(self, symbol):
        """Mock get_quote method."""

    async def get_historical(self, symbol, period="1y"):
        """Mock get_historical method."""

    async def get_market_status(self):
        """Mock get_market_status method."""

@pytest.mark.asyncio
async def test_paper_buy():
    """Test paper trading buy order execution."""
    repo = MockRepo()
    repo.get_or_create_stock.return_value = Stock(id=1, symbol="TEST", name="Test")

    fetcher = MockFetcher()
    trader = PaperTrader(repo, fetcher, initial_balance=1000.0)

    order = await trader.buy("TEST", 10, 50.0)

    assert order.action == "BUY"
    assert order.quantity == 10
    assert order.price == 50.0
    assert trader._current_balance == 500.0 # 1000 - (10*50)

    repo.log_trade.assert_called_once()

@pytest.mark.asyncio
async def test_paper_buy_insufficient_funds():
    """Test paper trading buy order with insufficient funds."""
    repo = MockRepo()
    fetcher = MockFetcher()
    trader = PaperTrader(repo, fetcher, initial_balance=100.0)

    with pytest.raises(ValueError):
        await trader.buy("TEST", 10, 50.0) # Cost 500 > 100
