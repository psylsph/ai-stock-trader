"""Tests for web mode remote AI hand-off behavior."""

import pytest
from unittest.mock import Mock, AsyncMock

from src.database.models import Base, Stock, Position, AIDecision
from src.database.repository import DatabaseRepository
from src.ai.decision_engine import TradingDecisionEngine
from src.ai.local_ai_client import LocalAIClient
from src.ai.openrouter_client import OpenRouterClient


@pytest.fixture
async def db_repo():
    """Create a test database repository."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from src.database.models import Base

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    repo = DatabaseRepository(engine, async_session)
    yield repo

    await engine.dispose()


@pytest.fixture
def mock_local_ai():
    """Mock local AI client."""
    return Mock(spec=LocalAIClient)


@pytest.fixture
def mock_remote_ai():
    """Mock remote AI client."""
    client = Mock(spec=OpenRouterClient)
    client.client = Mock()
    client.client.chat = Mock()
    client.client.chat.completions = Mock()
    return client


@pytest.fixture
def decision_engine(mock_local_ai, mock_remote_ai):
    """Create decision engine with mocked AIs."""
    return TradingDecisionEngine(mock_local_ai, mock_remote_ai)

    @pytest.mark.asyncio
    async def test_bot_mode_initialization(self, monkeypatch):
        """Test that web mode flag is NOT set when running in bot mode."""
        from src import main

        monkeypatch.setattr("sys.argv", [])
        import asyncio
        await asyncio.sleep(0.01)

        assert not web_mode_settings.is_web_mode, "Web mode should be disabled in bot mode"

    @pytest.mark.asyncio
    async def test_remote_ai_modify_without_web_mode(self, db_repo, mock_remote_ai, decision_engine):
        """Test that remote AI modification in bot mode directly updates the decision."""
        web_mode_settings.is_web_mode = False

        original_decision = await db_repo.log_decision(
            symbol="AZN.L",
            ai_type="local",
            decision="BUY",
            confidence=0.90,
            context={"rec": {"reasoning": "Initial buy"}}
        )

        mock_remote_ai.client.chat.completions.create.return_value = Mock(
            choices=[Mock(
                message=Mock(content='{"decision": "MODIFY", "comments": "Reduce size"}')
            )]
        )

        validation_result = await decision_engine.validate_with_remote_ai(
            action="BUY",
            symbol="AZN.L",
            reasoning="Initial buy",
            confidence=0.90,
            size_pct=0.05
        )

        assert validation_result["decision"] == "MODIFY", "Should be modified"

        pending_decisions = await db_repo.get_pending_decisions()
        assert len(pending_decisions) == 1, "Should have one pending decision"
        assert pending_decisions[0].decision == "BUY", "Original decision should remain BUY"

    @pytest.mark.asyncio
    async def test_remote_ai_modify_with_web_mode(self, db_repo, mock_remote_ai, decision_engine):
        """Test that remote AI modification in web mode stores feedback but doesn't execute trade."""
        web_mode_settings.is_web_mode = True

        original_decision = await db_repo.log_decision(
            symbol="AZN.L",
            ai_type="local",
            decision="BUY",
            confidence=0.90,
            context={"rec": {"reasoning": "Initial buy"}}
        )

        validation_result = await decision_engine.validate_with_remote_ai(
            action="BUY",
            symbol="AZN.L",
            reasoning="Initial buy",
            confidence=0.90,
            size_pct=0.05
        )

        assert validation_result["decision"] == "MODIFY", "Should be modified"
        assert validation_result["new_confidence"] == 0.95, "Confidence should increase"

        all_decisions = await db_repo.get_all_decisions()
        assert len(all_decisions) >= 1, "Should have at least one decision"

        azn_decisions = [d for d in all_decisions if d.symbol == "AZN.L"]
        latest_azn = max(azn_decisions, key=lambda d: d.timestamp)

        assert latest_azn.decision == "BUY", "Decision should remain BUY"

        context_data = latest_azn.context
        assert "rec" in context_data, "Should have original recommendation"
        assert "new_confidence" in context_data, "Should have new confidence from remote AI"
        assert "new_size_pct" in context_data, "Should have new size from remote AI"

    @pytest.mark.asyncio
    async def test_remote_ai_reject_with_web_mode(self, db_repo, mock_remote_ai, decision_engine):
        """Test that remote AI rejection in web mode stores rejection reason."""
        web_mode_settings.is_web_mode = True

        original_decision = await db_repo.log_decision(
            symbol="LLOY.L",
            ai_type="local",
            decision="BUY",
            confidence=0.85,
            context={"rec": {"reasoning": "Good setup"}}
        )

        mock_remote_ai.client.chat.completions.create.return_value = Mock(
            choices=[Mock(message='{"decision": "REJECT", "comments": "Overvalued, too risky"}')]
        )

        validation_result = await decision_engine.validate_with_remote_ai(
            action="BUY",
            symbol="LLOY.L",
            reasoning="Good setup",
            confidence=0.85,
            size_pct=0.05
        )

        assert validation_result["decision"] == "REJECT", "Should be rejected"


        all_decisions = await db_repo.get_all_decisions()
        lloy_decisions = [d for d in all_decisions if d.symbol == "LLOY.L"]
        latest_lloy = max(lloy_decisions, key=lambda d: d.timestamp)

        assert latest_lloy.decision == "BUY", "Latest decision should be BUY"

    @pytest.mark.asyncio
    async def test_remote_ai_proceed_stays_original_with_web_mode(self, db_repo, decision_engine):
        """Test that PROCEED response keeps original decision in web mode."""
        web_mode_settings.is_web_mode = True

        original_decision = await db_repo.log_decision(
            symbol="BARC.L",
            ai_type="local",
            decision="HOLD",
            confidence=0.75,
            context={"rec": {"reasoning": "Wait and see"}}
        )

        mock_remote_ai.client.chat.completions.create.return_value = Mock(
            choices=[Mock(message='{"decision": "PROCEED"}')]
        )

        validation_result = await decision_engine.validate_with_remote_ai(
            action="HOLD",
            symbol="BARC.L",
            reasoning="Wait and see",
            confidence=0.75,
            size_pct=0.0
        )

        assert validation_result["decision"] == "PROCEED", "Should proceed"

        all_decisions = await db_repo.get_all_decisions()
        barc_decisions = [d for d in all_decisions if d.symbol == "BARC.L"]
        latest_barc = max(barc_decisions, key=lambda d: d.timestamp)

        assert latest_barc.decision == "HOLD", "Original HOLD decision should persist"

    @pytest.mark.asyncio
    async def test_concurrent_web_mode_access(self, db_repo):
        """Test that multiple web server sessions can read decisions correctly."""
        web_mode_settings.is_web_mode = True

        decision1 = await db_repo.log_decision(
            symbol="BA.L",
            ai_type="local",
            decision="BUY",
            confidence=0.80,
            context={"rec": {"reasoning": "Good entry"}}
        )

        decision2 = await db_repo.log_decision(
            symbol="BA.L",
            ai_type="local",
            decision="BUY",
            confidence=0.85,
            context={"rec": {"reasoning": "Confirmed"}}
        )

        all_decisions = await db_repo.get_all_decisions()
        ba_decisions = [d for d in all_decisions if d.symbol == "BA.L"]
        assert len(ba_decisions) == 2, "Should have both decisions"

        latest = max(ba_decisions, key=lambda d: d.timestamp)

        assert latest.decision == "BUY", "Latest decision should be BUY"
        assert latest.context["rec"]["reasoning"] == "Confirmed", "Should use latest context"
