"""Tests for trading decision engine."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timezone

from src.ai.decision_engine import TradingDecisionEngine
from src.ai.local_ai_client import LocalAIClient
from src.ai.openrouter_client import OpenRouterClient


class TestTradingDecisionEngine:
    """Test the TradingDecisionEngine class."""

    @pytest.fixture
    def mock_local_ai(self):
        """Create a mock local AI client."""
        client = MagicMock(spec=LocalAIClient)
        client.analyze_market_with_tools = AsyncMock()
        client.analyze_position = AsyncMock()
        client._stream_chat_completion = AsyncMock()
        return client

    @pytest.fixture
    def mock_remote_ai(self):
        """Create a mock remote AI client."""
        client = MagicMock(spec=OpenRouterClient)
        client.client = MagicMock()
        client.model = "openrouter-model"
        return client

    @pytest.fixture
    def decision_engine(self, mock_local_ai, mock_remote_ai):
        """Create a decision engine with mocked dependencies."""
        return TradingDecisionEngine(local_ai=mock_local_ai, openrouter_client=mock_remote_ai)

    @pytest.mark.asyncio
    async def test_startup_analysis_returns_local_ai_result(self, decision_engine, mock_local_ai):
        """Test that startup_analysis returns the local AI result."""
        expected_result = {
            "analysis_summary": "Market looks bullish",
            "recommendations": [{"action": "BUY", "symbol": "AAPL.L", "confidence": 0.9}]
        }
        mock_local_ai.analyze_market_with_tools.return_value = expected_result

        result = await decision_engine.startup_analysis(
            portfolio_summary="Balance: 10000",
            market_status="Market is OPEN",
            rss_news_summary="News summary here",
            tools=MagicMock()
        )

        assert result == expected_result
        mock_local_ai.analyze_market_with_tools.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_with_remote_ai_proceed(self, decision_engine, mock_remote_ai):
        """Test remote AI validation returns PROCEED for high confidence."""
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock()]
        mock_completion.choices[0].message.content = '{"decision": "PROCEED", "comments": "Looks good"}'
        mock_remote_ai.client.chat.completions.create.return_value = mock_completion

        result = await decision_engine.validate_with_remote_ai(
            action="BUY",
            symbol="AAPL.L",
            reasoning="Technical indicators are bullish",
            confidence=0.9,
            size_pct=0.1
        )

        assert result["decision"] == "PROCEED"

    @pytest.mark.asyncio
    async def test_validate_with_remote_ai_error_fallback(self, decision_engine, mock_remote_ai):
        """Test remote AI validation falls back on error."""
        mock_remote_ai.client.chat.completions.create.side_effect = Exception("API Error")

        result = await decision_engine.validate_with_remote_ai(
            action="BUY",
            symbol="AAPL.L",
            reasoning="Technical indicators are bullish",
            confidence=0.9,
            size_pct=0.1
        )

        assert result["decision"] == "PROCEED"
        assert "failed" in result["comments"].lower()

    @pytest.mark.asyncio
    async def test_request_remote_recommendations_success(self, decision_engine, mock_remote_ai):
        """Test remote recommendations are returned successfully."""
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock()]
        mock_completion.choices[0].message.content = '{"analysis_summary": "Market overview", "recommendations": []}'
        mock_remote_ai.client.chat.completions.create.return_value = mock_completion

        prescreened_tickers = {
            "AAPL.L": {"rsi": 45.0, "macd": 1.0, "signal": 0.8, "sma_50": 100.0, "sma_200": 95.0, "current_price": 105.0, "passed": True}
        }

        result = await decision_engine.request_remote_recommendations(
            portfolio_summary="Balance: 10000",
            market_status="Market is OPEN",
            prescreened_tickers=prescreened_tickers,
            rss_news_summary="News summary"
        )

        assert "analysis_summary" in result
        assert "recommendations" in result
        mock_remote_ai.client.chat.completions.create.assert_called()

    @pytest.mark.asyncio
    async def test_request_remote_recommendations_error(self, decision_engine, mock_remote_ai):
        """Test remote recommendations return error dict on failure."""
        mock_remote_ai.client.chat.completions.create.side_effect = Exception("API Error")

        prescreened_tickers = {
            "AAPL.L": {"rsi": 45.0, "macd": 1.0, "signal": 0.8, "sma_50": 100.0, "sma_200": 95.0, "current_price": 105.0, "passed": True}
        }

        result = await decision_engine.request_remote_recommendations(
            portfolio_summary="Balance: 10000",
            market_status="Market is OPEN",
            prescreened_tickers=prescreened_tickers,
            rss_news_summary="News summary"
        )

        assert "error" in result["analysis_summary"].lower()
        assert result["recommendations"] == []

    @pytest.mark.asyncio
    async def test_intraday_check_local_sell_high_confidence(self, decision_engine, mock_local_ai):
        """Test intraday check with high confidence SELL."""
        mock_local_ai.analyze_position.return_value = {
            "decision": "SELL",
            "reasoning": "Price dropped below support",
            "confidence": 0.9
        }

        position = MagicMock()
        position.stock.symbol = "AAPL.L"
        position.entry_price = 100.0
        position.current_price = 95.0
        position.entry_date = datetime.now(timezone.utc)

        result = await decision_engine.intraday_check(
            position=position,
            price_history="Price history...",
            indicators={"rsi": 30.0, "macd": -0.5},
            volume_data={"current": 1000000, "average": 800000}
        )

        assert result["action"] == "SELL"
        assert result["confidence"] == 0.9
        assert result["escalated"] is False

    @pytest.mark.asyncio
    async def test_intraday_check_local_sell_low_confidence(self, decision_engine, mock_local_ai):
        """Test intraday check with low confidence SELL escalates."""
        mock_local_ai.analyze_position.return_value = {
            "decision": "SELL",
            "reasoning": "Price dropped slightly",
            "confidence": 0.6
        }

        position = MagicMock()
        position.stock.symbol = "AAPL.L"
        position.entry_price = 100.0
        position.current_price = 98.0
        position.entry_date = datetime.now(timezone.utc)

        result = await decision_engine.intraday_check(
            position=position,
            price_history="Price history...",
            indicators={"rsi": 45.0, "macd": 0.1},
            volume_data={"current": 1000000, "average": 800000}
        )

        assert result["action"] == "HOLD"
        assert result["escalated"] is True

    @pytest.mark.asyncio
    async def test_intraday_check_hold(self, decision_engine, mock_local_ai):
        """Test intraday check with HOLD decision."""
        mock_local_ai.analyze_position.return_value = {
            "decision": "HOLD",
            "reasoning": "Price is consolidating",
            "confidence": 0.7
        }

        position = MagicMock()
        position.stock.symbol = "AAPL.L"
        position.entry_price = 100.0
        position.current_price = 100.5
        position.entry_date = datetime.now(timezone.utc)

        result = await decision_engine.intraday_check(
            position=position,
            price_history="Price history...",
            indicators={"rsi": 50.0, "macd": 0.0},
            volume_data={"current": 1000000, "average": 800000}
        )

        assert result["action"] == "HOLD"
        assert result["escalated"] is False

    @pytest.mark.asyncio
    async def test_intraday_check_escales_decision(self, decision_engine, mock_local_ai):
        """Test intraday check when local AI returns ESCALATE."""
        mock_local_ai.analyze_position.return_value = {
            "decision": "ESCALATE",
            "reasoning": "Unclear signal - need human review",
            "confidence": 0.5
        }

        position = MagicMock()
        position.stock.symbol = "AAPL.L"
        position.entry_price = 100.0
        position.current_price = 100.0
        position.entry_date = datetime.now(timezone.utc)

        result = await decision_engine.intraday_check(
            position=position,
            price_history="Price history...",
            indicators={"rsi": 50.0, "macd": 0.0},
            volume_data={"current": 1000000, "average": 800000}
        )

        assert result["action"] == "HOLD"
        assert result["escalated"] is True


class TestValidationRetryLogic:
    """Test retry logic for token limit errors."""

    @pytest.fixture
    def mock_local_ai(self):
        """Create a mock local AI client."""
        client = MagicMock(spec=LocalAIClient)
        client.analyze_market_with_tools = AsyncMock()
        client.analyze_position = AsyncMock()
        client._stream_chat_completion = AsyncMock()
        return client

    @pytest.fixture
    def mock_remote_ai_free_model(self):
        """Create a mock remote AI client with :free model."""
        client = MagicMock(spec=OpenRouterClient)
        client.client = MagicMock()
        client.model = "openrouter-model:free"
        return client

    @pytest.mark.asyncio
    async def test_retry_on_token_limit_with_free_model(self, mock_local_ai, mock_remote_ai_free_model):
        """Test retry logic strips :free suffix on token limit error."""
        decision_engine = TradingDecisionEngine(local_ai=mock_local_ai, openrouter_client=mock_remote_ai_free_model)

        call_count = 0
        original_model = mock_remote_ai_free_model.model

        async def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("context_length_exceeded for :free model")
            mock_completion = MagicMock()
            mock_completion.choices = [MagicMock()]
            mock_completion.choices[0].message.content = '{"decision": "PROCEED"}'
            return mock_completion

        mock_remote_ai_free_model.client.chat.completions.create.side_effect = side_effect

        result = await decision_engine._validate_with_retry("test prompt")

        assert result["decision"] == "PROCEED"
        assert call_count == 2
        assert mock_remote_ai_free_model.model == original_model

    @pytest.mark.asyncio
    async def test_no_retry_on_regular_error(self, mock_local_ai, mock_remote_ai_free_model):
        """Test no retry on regular errors."""
        decision_engine = TradingDecisionEngine(local_ai=mock_local_ai, openrouter_client=mock_remote_ai_free_model)

        mock_remote_ai_free_model.client.chat.completions.create.side_effect = Exception("Connection refused")

        with pytest.raises(Exception):
            await decision_engine._validate_with_retry("test prompt")


class TestStartupAnalysisWithPrescreening:
    """Test startup analysis with prescreened stocks."""

    @pytest.fixture
    def mock_local_ai(self):
        """Create a mock local AI client."""
        client = MagicMock(spec=LocalAIClient)
        client._stream_chat_completion = AsyncMock()
        return client

    @pytest.fixture
    def mock_remote_ai(self):
        """Create a mock remote AI client."""
        client = MagicMock(spec=OpenRouterClient)
        client.client = MagicMock()
        client.model = "openrouter-model"
        return client

    @pytest.mark.asyncio
    async def test_startup_analysis_with_prescreening_success(self, mock_local_ai, mock_remote_ai):
        """Test successful startup analysis with prescreened stocks."""
        decision_engine = TradingDecisionEngine(local_ai=mock_local_ai, openrouter_client=mock_remote_ai)

        mock_local_ai._stream_chat_completion.return_value = (
            '{"analysis_summary": "Market looks good", "recommendations": [{"action": "BUY", "symbol": "AAPL.L", "confidence": 0.85}]}',
            None
        )

        prescreened_tickers = {
            "AAPL.L": {"rsi": 40.0, "macd": 1.5, "signal": 1.2, "sma_50": 100.0, "sma_200": 95.0, "current_price": 105.0, "passed": True},
            "GOOGL.L": {"rsi": 45.0, "macd": 1.0, "signal": 0.9, "sma_50": 100.0, "sma_200": 98.0, "current_price": 102.0, "passed": True}
        }

        result = await decision_engine.startup_analysis_with_prescreening(
            portfolio_summary="Balance: 10000",
            market_status="Market is OPEN",
            prescreened_tickers=prescreened_tickers,
            rss_news_summary="News for AAPL.L and GOOGL.L"
        )

        assert result["analysis_summary"] == "Market looks good"
        assert len(result["recommendations"]) == 1
        assert result["recommendations"][0]["action"] == "BUY"

    @pytest.mark.asyncio
    async def test_startup_analysis_cleans_think_blocks(self, mock_local_ai, mock_remote_ai):
        """Test that [THINK] blocks are removed from response."""
        decision_engine = TradingDecisionEngine(local_ai=mock_local_ai, openrouter_client=mock_remote_ai)

        mock_local_ai._stream_chat_completion.return_value = (
            '''[THINK] Let me analyze the market conditions...[/THINK]
            {"analysis_summary": "Market looks good", "recommendations": []}''',
            None
        )

        prescreened_tickers = {
            "AAPL.L": {"rsi": 40.0, "macd": 1.5, "signal": 1.2, "sma_50": 100.0, "sma_200": 95.0, "current_price": 105.0, "passed": True}
        }

        result = await decision_engine.startup_analysis_with_prescreening(
            portfolio_summary="Balance: 10000",
            market_status="Market is OPEN",
            prescreened_tickers=prescreened_tickers,
            rss_news_summary="News summary"
        )

        assert "[THINK]" not in result["analysis_summary"]

    @pytest.mark.asyncio
    async def test_startup_analysis_handles_invalid_json(self, mock_local_ai, mock_remote_ai):
        """Test fallback when AI returns invalid JSON."""
        decision_engine = TradingDecisionEngine(local_ai=mock_local_ai, openrouter_client=mock_remote_ai)

        mock_local_ai._stream_chat_completion.return_value = (
            "This is not valid JSON at all",
            None
        )

        prescreened_tickers = {
            "AAPL.L": {"rsi": 40.0, "macd": 1.5, "signal": 1.2, "sma_50": 100.0, "sma_200": 95.0, "current_price": 105.0, "passed": True}
        }

        result = await decision_engine.startup_analysis_with_prescreening(
            portfolio_summary="Balance: 10000",
            market_status="Market is OPEN",
            prescreened_tickers=prescreened_tickers,
            rss_news_summary="News summary"
        )

        assert result["analysis_summary"] == "This is not valid JSON at all"
        assert result["recommendations"] == []
