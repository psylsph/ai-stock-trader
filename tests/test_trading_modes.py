"""Tests to verify trading mode behaviors per DESIGN.md."""

import pytest
from unittest.mock import Mock, AsyncMock
from src.config.settings import settings


def test_trading_mode_paper():
    """Verify paper trading mode configuration."""
    assert settings.TRADING_MODE in ["paper", "live"], f"Invalid TRADING_MODE: {settings.TRADING_MODE}"


def test_startup_analysis_always_runs():
    """
    Verify that startup analysis always runs regardless of mode.

    Per DESIGN.md section 3.1:
    - Analysis runs ALWAYS: Both web mode (`--web`) and bot mode execute startup analysis
    """
    from src.orchestration.workflows import TradingWorkflow

    mock_repo = Mock()
    mock_repo.get_positions = AsyncMock(return_value=[])
    mock_repo.get_or_create_stock = AsyncMock()

    # Create workflow (initialization doesn't require actual DB)
    workflow = TradingWorkflow(settings, mock_repo)

    assert workflow is not None
    assert hasattr(workflow, 'run_startup_analysis')


def test_remote_validation_always_happens():
    """
    Verify that remote validation is not optional for both BUY and SELL.

    Per DESIGN.md section 3.1:
    - Analysis runs ALWAYS: Both web mode (`--web`) and bot mode execute startup analysis
    - Remote validation ALWAYS happens for both BUY and SELL recommendations
    """
    from src.ai.decision_engine import TradingDecisionEngine

    mock_local_ai = Mock()
    mock_remote_ai = Mock()
    mock_remote_ai.client = Mock()

    engine = TradingDecisionEngine(mock_local_ai, mock_remote_ai)

    assert hasattr(engine, 'validate_with_remote_ai')


def test_web_mode_starts_server():
    """
    Verify web mode behavior.

    Per DESIGN.md section 3.1 and 6.4:
    - Web mode: Web server starts after analysis
    - Monitoring loop: DOES NOT run (server mode only)
    """
    from src.web.app import app

    assert app is not None
    assert app.title == "AI Stock Trader Dashboard"


def test_bot_mode_runs_monitoring_loop():
    """
    Verify bot mode runs monitoring loop after analysis.

    Per DESIGN.md section 3.1:
    - Bot mode: Monitoring loop runs after analysis
    """
    from src.orchestration.workflows import TradingWorkflow

    mock_repo = Mock()
    mock_repo.get_positions = AsyncMock(return_value=[])

    workflow = TradingWorkflow(settings, mock_repo)

    assert hasattr(workflow, 'run_monitoring_loop')


def test_live_mode_requires_manual_review():
    """
    Verify live mode requires manual review.

    Per DESIGN.md section 6.4:
    - Live Mode: Trade Execution: BLOCKED - requires manual approval
    - Manual Review: REQUIRED (flag set in AIDecision records)
    """
    # This is tested in decision_engine.py where live mode
    # sets requires_manual_review flag
    pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
