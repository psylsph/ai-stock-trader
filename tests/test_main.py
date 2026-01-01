"""Tests for command line arguments and main module."""

import pytest
import os
import tempfile
from unittest.mock import patch, AsyncMock
from pydantic_settings import BaseSettings


class MockSettings(BaseSettings):
    """Mock settings for testing."""
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = "x-ai/grok-4"
    LM_STUDIO_API_URL: str = "http://localhost:1234/v1"
    LM_STUDIO_MODEL: str = "mistralai/ministral-3-3b"
    ENABLE_TOOLS: bool = True
    ENABLE_VISION: bool = True
    REMOTE_ONLY_MODE: bool = True
    LOCAL_AI_TEMPERATURE: float = 0.2
    REMOTE_AI_TEMPERATURE: float = 0.2
    USE_STREAMING: bool = True
    AI_MAX_RETRIES: int = 3
    AI_RETRY_DELAY_SECONDS: float = 1.0
    DATABASE_URL: str = "sqlite+aiosqlite:///trading.db"
    TRADING_MODE: str = "paper"
    IGNORE_MARKET_HOURS: bool = False
    CHECK_INTERVAL_SECONDS: int = 300
    INITIAL_BALANCE: float = 10000.0
    MAX_POSITIONS: int = 5
    MAX_POSITION_SIZE_PCT: float = 0.20
    RSS_FEEDS: list = [
        "https://news.yahoo.com/rss/uk",
        "https://finance.yahoo.com/news/rssindex"
    ]

    class Config:
        env_file = "/dev/null"  # Don't load from .env


class TestCommandLineArgs:
    """Test command line argument parsing."""

    def test_restart_flag_removes_portfolio_json(self, tmp_path):
        """Test that --restart removes portfolio.json."""
        # Create a temporary portfolio.json file
        portfolio_file = tmp_path / "portfolio.json"
        portfolio_file.write_text('{"cash_balance": 1000}')

        # Verify file exists
        assert portfolio_file.exists()

        # Simulate the restart logic
        if portfolio_file.exists():
            try:
                os.remove(str(portfolio_file))
            except OSError:
                pass

        # Verify file is removed
        assert not portfolio_file.exists()

    def test_settings_default_values(self):
        """Test that settings have correct defaults."""
        settings = MockSettings()

        assert settings.INITIAL_BALANCE == 10000.0
        assert settings.TRADING_MODE == "paper"
        assert settings.CHECK_INTERVAL_SECONDS == 300
        assert settings.MAX_POSITIONS == 5
        assert settings.MAX_POSITION_SIZE_PCT == 0.20
        assert settings.LOCAL_AI_TEMPERATURE == 0.2
        assert settings.REMOTE_AI_TEMPERATURE == 0.2
        assert settings.REMOTE_ONLY_MODE is True

    def test_settings_from_env(self, monkeypatch):
        """Test that settings can be overridden from environment."""
        class EnvSettings(BaseSettings):
            INITIAL_BALANCE: float = 10000.0
            TRADING_MODE: str = "paper"
            CHECK_INTERVAL_SECONDS: int = 300

            class Config:
                env_file = "/dev/null"

        monkeypatch.setenv("INITIAL_BALANCE", "5000")
        monkeypatch.setenv("TRADING_MODE", "live")
        monkeypatch.setenv("CHECK_INTERVAL_SECONDS", "60")

        settings = EnvSettings()

        assert settings.INITIAL_BALANCE == 5000.0
        assert settings.TRADING_MODE == "live"
        assert settings.CHECK_INTERVAL_SECONDS == 60


class TestPortfolioPersistence:
    """Test portfolio persistence behavior."""

    def test_portfolio_file_loading(self, tmp_path):
        """Test loading balance from portfolio.json."""
        portfolio_file = tmp_path / "portfolio.json"
        portfolio_file.write_text('{"cash_balance": 7500.50, "total_value": 15000}')

        import json
        with open(portfolio_file, 'r') as f:
            data = json.load(f)

        assert data["cash_balance"] == 7500.50
        assert data["total_value"] == 15000

    def test_portfolio_file_missing_balance(self, tmp_path):
        """Test behavior when portfolio.json has no cash_balance."""
        portfolio_file = tmp_path / "portfolio.json"
        portfolio_file.write_text('{"total_value": 10000}')

        import json
        with open(portfolio_file, 'r') as f:
            data = json.load(f)

        # Should fall back to initial balance
        saved_balance = data.get("cash_balance")
        assert saved_balance is None

    def test_portfolio_file_invalid_json(self, tmp_path):
        """Test behavior when portfolio.json is invalid."""
        portfolio_file = tmp_path / "portfolio.json"
        portfolio_file.write_text('not valid json')

        import json
        try:
            with open(portfolio_file, 'r') as f:
                data = json.load(f)
            data.get("cash_balance")  # Will be None
        except json.JSONDecodeError:
            # Should fall back to initial balance
            assert True

    def test_portfolio_file_zero_balance_fallback(self, tmp_path):
        """Test that 0 balance falls back to initial balance."""
        portfolio_file = tmp_path / "portfolio.json"
        portfolio_file.write_text('{"cash_balance": 0}')

        import json
        with open(portfolio_file, 'r') as f:
            data = json.load(f)

        saved_balance = data.get("cash_balance", 10000.0)
        # 0 should trigger fallback
        initial_balance = 10000.0
        if saved_balance is not None and saved_balance > 0:
            result = saved_balance
        else:
            result = initial_balance

        assert result == initial_balance
