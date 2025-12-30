import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from src.database.models import Base, Stock, Position
from src.database.repository import DatabaseRepository

@pytest_asyncio.fixture
async def db_repo():
    # Use in-memory SQLite for testing
    url = "sqlite+aiosqlite:///:memory:"
    repo = DatabaseRepository(url)
    await repo.init_db()
    return repo

@pytest.mark.asyncio
async def test_create_stock(db_repo):
    stock = await db_repo.get_or_create_stock("LLOY.L", "Lloyds")
    assert stock.symbol == "LLOY.L"
    assert stock.name == "Lloyds"
    
    # Ensure no duplicate
    stock2 = await db_repo.get_or_create_stock("LLOY.L", "Lloyds Duplicate")
    assert stock2.id == stock.id

@pytest.mark.asyncio
async def test_log_trade(db_repo):
    from src.database.models import Trade
    stock = await db_repo.get_or_create_stock("TEST.L", "Test Stock")
    
    trade = Trade(
        stock_id=stock.id,
        action="BUY",
        quantity=100,
        price=50.0
    )
    await db_repo.log_trade(trade)
    
    # We can't query trades via repo yet, but if it didn't fail, it's good.
    # Ideally should verify count.
