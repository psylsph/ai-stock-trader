"""Database initialization and exports for the AI Stock Trader application."""

from .models import Base, Stock, Position, Trade, MarketSnapshot, AIDecision
from .repository import DatabaseRepository


async def init_db(db_url: str, reset: bool = False):
    """Initialize the database.

    Args:
        db_url: The database connection URL.
        reset: Whether to reset the database (drop and recreate tables).

    Returns:
        The initialized DatabaseRepository instance.
    """
    repo = DatabaseRepository(db_url)
    if reset:
        await repo.reset_db()
    else:
        await repo.init_db()
    return repo
