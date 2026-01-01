"""Tests for paper trading functionality."""

import os
from unittest.mock import AsyncMock
import pytest
import tempfile
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


@pytest.fixture(autouse=True)
def clean_portfolio_file():
    """Clean up portfolio.json before and after each test."""
    portfolio_file = "portfolio.json"
    # Save original if exists
    original_exists = os.path.exists(portfolio_file)
    original_content = None
    if original_exists:
        with open(portfolio_file, 'r') as f:
            original_content = f.read()
        os.remove(portfolio_file)
    
    yield
    
    # Cleanup after test
    if os.path.exists(portfolio_file):
        os.remove(portfolio_file)
    
    # Restore original if it existed
    if original_exists and original_content:
        with open(portfolio_file, 'w') as f:
            f.write(original_content)


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
    assert trader._current_balance == 500.0  # 1000 - (10*50)

    repo.log_trade.assert_called_once()


@pytest.mark.asyncio
async def test_paper_buy_insufficient_funds():
    """Test paper trading buy order with insufficient funds."""
    repo = MockRepo()
    fetcher = MockFetcher()
    trader = PaperTrader(repo, fetcher, initial_balance=100.0)

    with pytest.raises(ValueError):
        await trader.buy("TEST", 10, 50.0)  # Cost 500 > 100
