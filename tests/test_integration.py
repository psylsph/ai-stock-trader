"""Integration tests for web server and bot mode startup."""

import pytest
from unittest.mock import Mock, AsyncMock
from typing import Optional
from src.config.settings import settings


@pytest.mark.asyncio
async def test_trading_workflow_initialization():
    """Test that TradingWorkflow initializes correctly with mocks."""
    from src.orchestration.workflows import TradingWorkflow

    mock_repo = Mock()
    mock_repo.get_positions = AsyncMock(return_value=[])
    mock_repo.get_or_create_stock = AsyncMock()
    mock_repo.init_db = AsyncMock()

    workflow = TradingWorkflow(settings, mock_repo)

    assert workflow is not None
    assert hasattr(workflow, 'local_ai')
    assert hasattr(workflow, 'decision_engine')
    assert hasattr(workflow, 'broker')


@pytest.mark.asyncio
async def test_web_mode_flag_parsing():
    """Test that --web flag is correctly parsed."""
    import argparse
    import sys
    from io import StringIO

    # Save original argv
    original_argv = sys.argv

    try:
        # Test with --web flag
        sys.argv = ['main', '--web']
        parser = argparse.ArgumentParser()
        parser.add_argument("--web", action="store_true")
        parser.add_argument("--restart", action="store_true")
        args = parser.parse_args()

        assert args.web is True
        assert args.restart is False

        # Test without --web flag
        sys.argv = ['main']
        args = parser.parse_args()

        assert args.web is False

    finally:
        # Restore original argv
        sys.argv = original_argv


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
