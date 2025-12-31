"""Comprehensive behavior tests that verify actual implementation logic."""

import pytest
from unittest.mock import Mock, AsyncMock
from src.ai.decision_engine import TradingDecisionEngine


@pytest.mark.asyncio
async def test_remote_validation_buy_high_confidence():

    mock_local_ai = Mock()
    mock_remote_ai = Mock()
    mock_remote_ai.client = Mock()
    mock_remote_ai.client.chat = Mock()
    mock_remote_ai.client.chat.completions = Mock()
    mock_remote_ai.model = "test-model"
    mock_remote_ai.client.chat.completions.create = AsyncMock()

    engine = TradingDecisionEngine(mock_local_ai, mock_remote_ai)

    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message = Mock()
    mock_response.choices[0].message.content = '{"decision": "PROCEED", "comments": "Valid"}'
    mock_remote_ai.client.chat.completions.create.return_value = mock_response

    result = await engine.validate_with_remote_ai(
        action="BUY",
        symbol="TEST.L",
        reasoning="Test",
        confidence=0.85,
        size_pct=0.05
    )

    mock_remote_ai.client.chat.completions.create.assert_called_once()
    call_args = mock_remote_ai.client.chat.completions.create.call_args
    assert call_args is not None
    messages = call_args.kwargs.get("messages", [])
    assert len(messages) >= 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert "BUY" in messages[1]["content"]
    assert "TEST.L" in messages[1]["content"]
    assert result["decision"] == "PROCEED"


@pytest.mark.asyncio
async def test_remote_validation_sell_high_confidence():
    """
    Verify remote validation with correct parameters for SELL.
    """

    mock_local_ai = Mock()
    mock_remote_ai = Mock()
    mock_remote_ai.client = Mock()
    mock_remote_ai.client.chat = Mock()
    mock_remote_ai.client.chat.completions = Mock()
    mock_remote_ai.model = "test-model"
    mock_remote_ai.client.chat.completions.create = AsyncMock()

    engine = TradingDecisionEngine(mock_local_ai, mock_remote_ai)

    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message = Mock()
    mock_response.choices[0].message.content = '{"decision": "PROCEED", "comments": "Valid"}'
    mock_remote_ai.client.chat.completions.create.return_value = mock_response

    result = await engine.validate_with_remote_ai(
        action="SELL",
        symbol="TEST.L",
        reasoning="Test",
        confidence=0.85,
        size_pct=0.05
    )

    mock_remote_ai.client.chat.completions.create.assert_called_once()
    call_args = mock_remote_ai.client.chat.completions.create.call_args
    assert call_args is not None
    messages = call_args.kwargs.get("messages", [])
    assert len(messages) >= 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert "SELL" in messages[1]["content"]
    assert result["decision"] == "PROCEED"


@pytest.mark.asyncio
async def test_remote_validation_returns_proceed_on_success():
    """
    Verify remote validation returns PROCEED on successful validation.
    """

    mock_local_ai = Mock()
    mock_remote_ai = Mock()
    mock_remote_ai.client = Mock()
    mock_remote_ai.client.chat = Mock()
    mock_remote_ai.client.chat.completions = Mock()
    mock_remote_ai.model = "test-model"
    mock_remote_ai.client.chat.completions.create = AsyncMock()

    engine = TradingDecisionEngine(mock_local_ai, mock_remote_ai)

    mock_completion = Mock()
    mock_completion.choices = [Mock()]
    mock_completion.choices[0].message = Mock()
    mock_completion.choices[0].message.content = '{"decision": "PROCEED", "comments": "Looks good"}'
    mock_remote_ai.client.chat.completions.create.return_value = mock_completion

    result = await engine.validate_with_remote_ai(
        action="BUY",
        symbol="TEST.L",
        reasoning="Test reasoning",
        confidence=0.9,
        size_pct=0.1
    )

    assert result["decision"] == "PROCEED"
    assert result["comments"] == "Looks good"


@pytest.mark.asyncio
async def test_remote_validation_returns_modify():
    """
    Verify remote validation can return MODIFY with new parameters.
    """

    mock_local_ai = Mock()
    mock_remote_ai = Mock()
    mock_remote_ai.client = Mock()
    mock_remote_ai.client.chat = Mock()
    mock_remote_ai.client.chat.completions = Mock()
    mock_remote_ai.model = "test-model"
    mock_remote_ai.client.chat.completions.create = AsyncMock()

    engine = TradingDecisionEngine(mock_local_ai, mock_remote_ai)

    mock_completion = Mock()
    mock_completion.choices = [Mock()]
    mock_completion.choices[0].message = Mock()
    mock_completion.choices[0].message.content = '{"decision": "MODIFY", "new_confidence": 0.75, "new_size_pct": 0.05, "comments": "Reduce position size"}'
    mock_remote_ai.client.chat.completions.create.return_value = mock_completion

    result = await engine.validate_with_remote_ai(
        action="BUY",
        symbol="TEST.L",
        reasoning="Test",
        confidence=0.9,
        size_pct=0.1
    )

    assert result["decision"] == "MODIFY"
    assert result["new_confidence"] == 0.75
    assert result["new_size_pct"] == 0.05


@pytest.mark.asyncio
async def test_remote_validation_returns_reject():
    """
    Verify remote validation can REJECT a trade.
    """

    mock_local_ai = Mock()
    mock_remote_ai = Mock()
    mock_remote_ai.client = Mock()
    mock_remote_ai.client.chat = Mock()
    mock_remote_ai.client.chat.completions = Mock()
    mock_remote_ai.model = "test-model"
    mock_remote_ai.client.chat.completions.create = AsyncMock()

    engine = TradingDecisionEngine(mock_local_ai, mock_remote_ai)

    mock_completion = Mock()
    mock_completion.choices = [Mock()]
    mock_completion.choices[0].message = Mock()
    mock_completion.choices[0].message.content = '{"decision": "REJECT", "comments": "Too risky"}'
    mock_remote_ai.client.chat.completions.create.return_value = mock_completion

    result = await engine.validate_with_remote_ai(
        action="SELL",
        symbol="TEST.L",
        reasoning="Test",
        confidence=0.85,
        size_pct=0.05
    )

    assert result["decision"] == "REJECT"
    assert result["comments"] == "Too risky"


@pytest.mark.asyncio
async def test_remote_validation_handles_exception():
    """
    Verify remote validation returns PROCEED with error comment on exception.
    """

    mock_local_ai = Mock()
    mock_remote_ai = Mock()
    mock_remote_ai.client = Mock()
    mock_remote_ai.client.chat = Mock()
    mock_remote_ai.client.chat.completions = Mock()
    mock_remote_ai.model = "test-model"
    mock_remote_ai.client.chat.completions.create = AsyncMock(side_effect=Exception("API error"))

    engine = TradingDecisionEngine(mock_local_ai, mock_remote_ai)

    result = await engine.validate_with_remote_ai(
        action="BUY",
        symbol="TEST.L",
        reasoning="Test",
        confidence=0.85,
        size_pct=0.05
    )

    assert result["decision"] == "PROCEED"
    assert "Validation failed" in result["comments"]
    assert "API error" in result["comments"]


@pytest.mark.asyncio
async def test_paper_mode_does_not_set_manual_review_flag():
    """
    Verify paper mode does NOT set requires_manual_review flag (not implemented).
    """

    mock_local_ai = Mock()
    mock_remote_ai = Mock()
    mock_remote_ai.client = Mock()
    mock_remote_ai.client.chat = Mock()
    mock_remote_ai.client.chat.completions = Mock()
    mock_remote_ai.model = "test-model"
    mock_remote_ai.client.chat.completions.create = AsyncMock()

    engine = TradingDecisionEngine(mock_local_ai, mock_remote_ai)

    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message = Mock()
    mock_response.choices[0].message.content = '{"decision": "PROCEED"}'
    mock_remote_ai.client.chat.completions.create.return_value = mock_response

    result = await engine.validate_with_remote_ai(
        action="BUY",
        symbol="TEST.L",
        reasoning="Test",
        confidence=0.9,
        size_pct=0.05
    )

    mock_remote_ai.client.chat.completions.create.assert_called_once()
    assert result.get("requires_manual_review") is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
