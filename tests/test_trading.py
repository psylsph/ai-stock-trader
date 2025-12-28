import pytest
from unittest.mock import MagicMock, AsyncMock
from src.trading.paper_trader import PaperTrader
from src.market.data_fetcher import MarketDataFetcher
from src.database.repository import DatabaseRepository
from src.database.models import Stock, Position

class MockRepo(DatabaseRepository):
    def __init__(self):
        self.get_or_create_stock = AsyncMock()
        self.log_trade = AsyncMock()
        self.get_positions = AsyncMock(return_value=[])
        
class MockFetcher(MarketDataFetcher):
    async def get_quote(self, symbol):
        pass
    async def get_historical(self, symbol, period):
        pass
    async def get_market_status(self):
        pass

@pytest.mark.asyncio
async def test_paper_buy():
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
    repo = MockRepo()
    fetcher = MockFetcher()
    trader = PaperTrader(repo, fetcher, initial_balance=100.0)
    
    with pytest.raises(ValueError):
        await trader.buy("TEST", 10, 50.0) # Cost 500 > 100
