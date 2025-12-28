from .models import Base, Stock, Position, Trade, MarketSnapshot, AIDecision
from .repository import DatabaseRepository

async def init_db(db_url: str, reset: bool = False):
    repo = DatabaseRepository(db_url)
    if reset:
        await repo.reset_db()
    else:
        await repo.init_db()
    return repo
