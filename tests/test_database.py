import pytest
import pytest_asyncio
from datetime import datetime
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from src.database.models import Base, Stock, Position, Trade, AIDecision
from src.database.repository import DatabaseRepository


@pytest_asyncio.fixture
async def db_repo():
    url = "sqlite+aiosqlite:///:memory:"
    repo = DatabaseRepository(url)
    await repo.init_db()
    return repo


@pytest.mark.asyncio
async def test_create_stock(db_repo):
    stock = await db_repo.get_or_create_stock("LLOY.L", "Lloyds")
    assert stock.symbol == "LLOY.L"
    assert stock.name == "Lloyds"

    stock2 = await db_repo.get_or_create_stock("LLOY.L", "Lloyds Duplicate")
    assert stock2.id == stock.id


@pytest.mark.asyncio
async def test_log_trade(db_repo):
    stock = await db_repo.get_or_create_stock("TEST.L", "Test Stock")

    trade = Trade(
        stock_id=stock.id,
        action="BUY",
        quantity=100,
        price=50.0
    )
    await db_repo.log_trade(trade)


@pytest.mark.asyncio
async def test_log_and_get_decision(db_repo):
    decision = AIDecision(
        ai_type="local",
        symbol="AAPL.L",
        context={"test": True},
        response={"decision": "BUY"},
        decision="BUY",
        confidence=0.85
    )
    await db_repo.log_decision(decision)

    decisions = await db_repo.get_all_decisions()
    assert len(decisions) == 1
    assert decisions[0].symbol == "AAPL.L"
    assert decisions[0].decision == "BUY"


@pytest.mark.asyncio
async def test_update_decision_with_validation(db_repo):
    decision = AIDecision(
        ai_type="local",
        symbol="AAPL.L",
        context={"test": True},
        response={"decision": "BUY"},
        decision="BUY",
        confidence=0.85,
        requires_manual_review=True
    )
    await db_repo.log_decision(decision)

    await db_repo.update_decision_with_validation(
        symbol="AAPL.L",
        remote_validation_decision="PROCEED",
        remote_validation_comments="Looks good",
        requires_manual_review=False
    )

    decisions = await db_repo.get_all_decisions()
    assert len(decisions) == 1
    assert decisions[0].remote_validation_decision == "PROCEED"
    assert decisions[0].remote_validation_comments == "Looks good"
    assert decisions[0].requires_manual_review is False
    assert decisions[0].validation_timestamp is not None


@pytest.mark.asyncio
async def test_mark_decision_executed(db_repo):
    decision = AIDecision(
        ai_type="local",
        symbol="AAPL.L",
        context={"test": True},
        response={"decision": "BUY"},
        decision="BUY",
        confidence=0.85,
        executed=False
    )
    await db_repo.log_decision(decision)

    await db_repo.mark_decision_executed("AAPL.L")

    decisions = await db_repo.get_all_decisions()
    assert decisions[0].executed is True


@pytest.mark.asyncio
async def test_timeout_pending_decision(db_repo):
    decision = AIDecision(
        ai_type="local",
        symbol="AAPL.L",
        context={"test": True},
        response={"decision": "BUY"},
        decision="BUY",
        confidence=0.85,
        remote_validation_decision=None
    )
    await db_repo.log_decision(decision)

    await db_repo.timeout_pending_decision("AAPL.L")

    decisions = await db_repo.get_all_decisions()
    assert decisions[0].remote_validation_decision == "TIMEOUT"
    assert "Auto-rejected" in decisions[0].remote_validation_comments
