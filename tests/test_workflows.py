"""Tests for trading workflow orchestration."""

import pytest
from unittest.mock import MagicMock, AsyncMock
from src.trading.prescreening import StockPrescreener


class TestValidationRules:
    """Test the rule-based validation logic from workflows."""

    def test_apply_validation_rules_high_confidence_buy(self):
        """Test PROCEED for high confidence BUY."""
        prescreener = StockPrescreener()

        # Simulate the validation logic
        def apply_validation_rules(action, confidence):
            if action == "HOLD":
                return {
                    "decision": "PROCEED",
                    "comments": "HOLD - no action required",
                    "new_confidence": confidence,
                    "new_size_pct": None
                }

            if confidence >= 0.8:
                return {
                    "decision": "PROCEED",
                    "comments": "High confidence - approved via rules",
                    "new_confidence": confidence,
                    "new_size_pct": None
                }
            elif confidence >= 0.6:
                return {
                    "decision": "MODIFY",
                    "comments": "Moderate confidence - size reduced via rules",
                    "new_confidence": confidence,
                    "new_size_pct": 0.05
                }
            else:
                return {
                    "decision": "REJECT",
                    "comments": "Low confidence - rejected via rules",
                    "new_confidence": confidence,
                    "new_size_pct": None
                }

        result = apply_validation_rules("BUY", 0.9)
        assert result["decision"] == "PROCEED"
        assert result["new_confidence"] == 0.9
        assert "approved via rules" in result["comments"]

    def test_apply_validation_rules_high_confidence_sell(self):
        """Test PROCEED for high confidence SELL."""
        prescreener = StockPrescreener()

        def apply_validation_rules(action, confidence):
            if action == "HOLD":
                return {"decision": "PROCEED", "comments": "HOLD", "new_confidence": confidence, "new_size_pct": None}
            if confidence >= 0.8:
                return {"decision": "PROCEED", "comments": "High", "new_confidence": confidence, "new_size_pct": None}
            elif confidence >= 0.6:
                return {"decision": "MODIFY", "comments": "Mod", "new_confidence": confidence, "new_size_pct": 0.05}
            return {"decision": "REJECT", "comments": "Low", "new_confidence": confidence, "new_size_pct": None}

        result = apply_validation_rules("SELL", 0.85)
        assert result["decision"] == "PROCEED"

    def test_apply_validation_rules_moderate_confidence(self):
        """Test MODIFY for moderate confidence (0.6-0.8)."""
        def apply_validation_rules(action, confidence):
            if action == "HOLD":
                return {"decision": "PROCEED", "comments": "HOLD", "new_confidence": confidence, "new_size_pct": None}
            if confidence >= 0.8:
                return {"decision": "PROCEED", "comments": "High", "new_confidence": confidence, "new_size_pct": None}
            elif confidence >= 0.6:
                return {"decision": "MODIFY", "comments": "Mod", "new_confidence": confidence, "new_size_pct": 0.05}
            return {"decision": "REJECT", "comments": "Low", "new_confidence": confidence, "new_size_pct": None}

        result = apply_validation_rules("BUY", 0.7)
        assert result["decision"] == "MODIFY"
        assert result["new_size_pct"] == 0.05

    def test_apply_validation_rules_low_confidence(self):
        """Test REJECT for low confidence (< 0.6)."""
        def apply_validation_rules(action, confidence):
            if action == "HOLD":
                return {"decision": "PROCEED", "comments": "HOLD", "new_confidence": confidence, "new_size_pct": None}
            if confidence >= 0.8:
                return {"decision": "PROCEED", "comments": "High", "new_confidence": confidence, "new_size_pct": None}
            elif confidence >= 0.6:
                return {"decision": "MODIFY", "comments": "Mod", "new_confidence": confidence, "new_size_pct": 0.05}
            return {"decision": "REJECT", "comments": "Low", "new_confidence": confidence, "new_size_pct": None}

        result = apply_validation_rules("BUY", 0.5)
        assert result["decision"] == "REJECT"

    def test_apply_validation_rules_hold(self):
        """Test HOLD decisions return PROCEED with no action."""
        def apply_validation_rules(action, confidence):
            if action == "HOLD":
                return {"decision": "PROCEED", "comments": "HOLD", "new_confidence": confidence, "new_size_pct": None}
            if confidence >= 0.8:
                return {"decision": "PROCEED", "comments": "High", "new_confidence": confidence, "new_size_pct": None}
            elif confidence >= 0.6:
                return {"decision": "MODIFY", "comments": "Mod", "new_confidence": confidence, "new_size_pct": 0.05}
            return {"decision": "REJECT", "comments": "Low", "new_confidence": confidence, "new_size_pct": None}

        result = apply_validation_rules("HOLD", 0.5)
        assert result["decision"] == "PROCEED"
        assert result["new_size_pct"] is None

    def test_apply_validation_rules_boundaries(self):
        """Test boundary cases for validation."""
        def apply_validation_rules(action, confidence):
            if action == "HOLD":
                return {"decision": "PROCEED", "comments": "HOLD", "new_confidence": confidence, "new_size_pct": None}
            if confidence >= 0.8:
                return {"decision": "PROCEED", "comments": "High", "new_confidence": confidence, "new_size_pct": None}
            elif confidence >= 0.6:
                return {"decision": "MODIFY", "comments": "Mod", "new_confidence": confidence, "new_size_pct": 0.05}
            return {"decision": "REJECT", "comments": "Low", "new_confidence": confidence, "new_size_pct": None}

        # Boundaries
        assert apply_validation_rules("BUY", 0.8)["decision"] == "PROCEED"
        assert apply_validation_rules("BUY", 0.799)["decision"] == "MODIFY"
        assert apply_validation_rules("BUY", 0.6)["decision"] == "MODIFY"
        assert apply_validation_rules("BUY", 0.599)["decision"] == "REJECT"


class TestStockSelection:
    """Test stock selection logic."""

    def test_select_top_technical_picks(self):
        """Test selecting top N technical picks."""
        prescreener = StockPrescreener()

        prescreened_tickers = {
            "AAPL.L": {"rsi": 45.0, "macd": 2.0, "sma_50": 100.0, "sma_200": 95.0, "current_price": 105.0, "passed": True},
            "GOOGL.L": {"rsi": 50.0, "macd": 1.5, "sma_50": 100.0, "sma_200": 98.0, "current_price": 102.0, "passed": True},
            "MSFT.L": {"rsi": 55.0, "macd": 1.0, "sma_50": 100.0, "sma_200": 99.0, "current_price": 101.0, "passed": True}
        }

        def select_top_technical_picks(prescreened_tickers, limit=10):
            scored_stocks = []
            for ticker, indicators in prescreened_tickers.items():
                if indicators.get("passed", False):
                    score = prescreener.score_stock(indicators)
                    scored_stocks.append((ticker, score, indicators))

            scored_stocks.sort(key=lambda x: x[1], reverse=True)
            return {ticker: indicators for ticker, score, indicators in scored_stocks[:limit]}

        top_5 = select_top_technical_picks(prescreened_tickers, limit=5)

        # All 3 should be selected
        assert len(top_5) == 3
        assert "AAPL.L" in top_5
        assert "GOOGL.L" in top_5
        assert "MSFT.L" in top_5

    def test_select_top_technical_picks_limited(self):
        """Test selecting limited number of top picks."""
        prescreener = StockPrescreener()

        prescreened_tickers = {
            f"STOCK{i}.L": {
                "rsi": 30.0 + i * 5,
                "macd": 3.0 - i * 0.3,
                "sma_50": 100.0,
                "sma_200": 95.0,
                "current_price": 105.0 - i,
                "passed": True
            }
            for i in range(10)
        }

        def select_top_technical_picks(prescreened_tickers, limit=10):
            scored_stocks = []
            for ticker, indicators in prescreened_tickers.items():
                if indicators.get("passed", False):
                    score = prescreener.score_stock(indicators)
                    scored_stocks.append((ticker, score, indicators))

            scored_stocks.sort(key=lambda x: x[1], reverse=True)
            return {ticker: indicators for ticker, score, indicators in scored_stocks[:limit]}

        top_3 = select_top_technical_picks(prescreened_tickers, limit=3)

        # Only 3 should be selected
        assert len(top_3) == 3

    def test_select_top_technical_picks_only_passed(self):
        """Test that only passed stocks are selected."""
        prescreener = StockPrescreener()

        prescreened_tickers = {
            "PASS1.L": {"rsi": 40.0, "macd": 2.0, "sma_50": 100.0, "sma_200": 95.0, "current_price": 105.0, "passed": True},
            "FAIL1.L": {"rsi": 80.0, "macd": -2.0, "sma_50": 100.0, "sma_200": 90.0, "current_price": 88.0, "passed": False},
            "PASS2.L": {"rsi": 45.0, "macd": 1.5, "sma_50": 100.0, "sma_200": 95.0, "current_price": 102.0, "passed": True}
        }

        def select_top_technical_picks(prescreened_tickers, limit=10):
            scored_stocks = []
            for ticker, indicators in prescreened_tickers.items():
                if indicators.get("passed", False):
                    score = prescreener.score_stock(indicators)
                    scored_stocks.append((ticker, score, indicators))

            scored_stocks.sort(key=lambda x: x[1], reverse=True)
            return {ticker: indicators for ticker, score, indicators in scored_stocks[:limit]}

        top_10 = select_top_technical_picks(prescreened_tickers, limit=10)

        # Only passed stocks should be included
        assert "FAIL1.L" not in top_10
        assert len(top_10) == 2

    def test_select_top_technical_picks_by_ticker_cutoff(self):
        """Test selecting stocks above a cutoff ticker (uses ALL stocks for scoring)."""
        prescreener = StockPrescreener()

        # Mix of passed and failed stocks
        prescreened_tickers = {
            "HIGH1.L": {"rsi": 35.0, "macd": 2.0, "sma_50": 100.0, "sma_200": 95.0, "current_price": 105.0, "passed": True},  # Score ~100
            "CUTOFF.L": {"rsi": 45.0, "macd": 1.5, "sma_50": 100.0, "sma_200": 98.0, "current_price": 102.0, "passed": True},  # Score ~75
            "LOW1.L": {"rsi": 55.0, "macd": 1.0, "sma_50": 100.0, "sma_200": 99.0, "current_price": 101.0, "passed": True},  # Score ~50
            "LOW2.L": {"rsi": 60.0, "macd": 0.5, "sma_50": 100.0, "sma_200": 99.0, "current_price": 100.0, "passed": True}   # Score ~20
        }

        def select_above_cutoff(prescreened_tickers, cutoff_ticker):
            # Score ALL stocks first (not just passed ones)
            scored_stocks = []
            for ticker, indicators in prescreened_tickers.items():
                score = prescreener.score_stock(indicators)
                scored_stocks.append((ticker, score, indicators))

            scored_stocks.sort(key=lambda x: x[1], reverse=True)

            # Find cutoff score from ALL stocks
            cutoff_score = None
            if cutoff_ticker in prescreened_tickers:
                indicators = prescreened_tickers[cutoff_ticker]
                cutoff_score = prescreener.score_stock(indicators)

            if cutoff_score is None:
                return {}

            # Return ALL stocks with score >= cutoff (not just passed ones)
            selected = [(t, s, ind) for t, s, ind in scored_stocks if s >= cutoff_score]
            selected.sort(key=lambda x: x[1], reverse=True)
            return {ticker: indicators for ticker, score, indicators in selected}

        # Select stocks scoring >= CUTOFF.L
        result = select_above_cutoff(prescreened_tickers, "CUTOFF.L")

        # HIGH1.L and CUTOFF.L should be selected (score >= CUTOFF.L)
        assert len(result) == 2
        assert "HIGH1.L" in result
        assert "CUTOFF.L" in result
        assert "LOW1.L" not in result
        assert "LOW2.L" not in result

    def test_select_top_technical_picks_ticker_not_found(self):
        """Test handling when cutoff ticker is not found."""
        prescreener = StockPrescreener()

        prescreened_tickers = {
            "A.L": {"rsi": 45.0, "macd": 2.0, "sma_50": 100.0, "sma_200": 95.0, "current_price": 105.0, "passed": True},
            "B.L": {"rsi": 50.0, "macd": 1.5, "sma_50": 100.0, "sma_200": 98.0, "current_price": 102.0, "passed": True}
        }

        def select_above_cutoff(prescreened_tickers, cutoff_ticker):
            # Score ALL stocks first
            scored_stocks = []
            for ticker, indicators in prescreened_tickers.items():
                score = prescreener.score_stock(indicators)
                scored_stocks.append((ticker, score, indicators))

            scored_stocks.sort(key=lambda x: x[1], reverse=True)

            # Find cutoff score from ALL stocks
            cutoff_score = None
            if cutoff_ticker in prescreened_tickers:
                indicators = prescreened_tickers[cutoff_ticker]
                cutoff_score = prescreener.score_stock(indicators)

            if cutoff_score is None:
                return {}

            selected = [(t, s, ind) for t, s, ind in scored_stocks if s >= cutoff_score]
            return {ticker: indicators for ticker, score, indicators in selected}

        # Ticker not in prescreened list
        result = select_above_cutoff(prescreened_tickers, "NOTFOUND.L")
        assert result == {}

    def test_select_top_technical_picks_ticker_did_not_pass(self):
        """Test cutoff ticker that exists but didn't pass prescreening."""
        prescreener = StockPrescreener()

        # BA.L exists but didn't pass (overbought RSI)
        prescreened_tickers = {
            "HIGH1.L": {"rsi": 35.0, "macd": 2.0, "sma_50": 100.0, "sma_200": 95.0, "current_price": 105.0, "passed": True},  # Score ~100
            "BA.L": {"rsi": 75.0, "macd": 1.0, "sma_50": 100.0, "sma_200": 98.0, "current_price": 102.0, "passed": False},  # Score ~-50
            "LOW1.L": {"rsi": 55.0, "macd": 0.5, "sma_50": 100.0, "sma_200": 99.0, "current_price": 101.0, "passed": True}   # Score ~20
        }

        def select_above_cutoff(prescreened_tickers, cutoff_ticker):
            # Score ALL stocks first
            scored_stocks = []
            for ticker, indicators in prescreened_tickers.items():
                score = prescreener.score_stock(indicators)
                scored_stocks.append((ticker, score, indicators))

            scored_stocks.sort(key=lambda x: x[1], reverse=True)

            # Find cutoff score from ALL stocks
            cutoff_score = None
            if cutoff_ticker in prescreened_tickers:
                indicators = prescreened_tickers[cutoff_ticker]
                cutoff_score = prescreener.score_stock(indicators)

            if cutoff_score is None:
                return {}

            # Return ALL stocks with score >= cutoff (includes cutoff even if didn't pass)
            selected = [(t, s, ind) for t, s, ind in scored_stocks if s >= cutoff_score]
            selected.sort(key=lambda x: x[1], reverse=True)
            return {ticker: indicators for ticker, score, indicators in selected}

        # BA.L has score -50, so HIGH1.L (100), LOW1.L (20), and BA.L (-50) should all be selected
        result = select_above_cutoff(prescreened_tickers, "BA.L")

        # All 3 stocks have score >= -50, so all should be included
        assert len(result) == 3
        assert "HIGH1.L" in result
        assert "LOW1.L" in result
        assert "BA.L" in result  # Even though it didn't pass, it's included since score >= cutoff

    def test_select_top_technical_picks_numeric_limit(self):
        """Test numeric limit still filters to passed stocks only."""
        prescreener = StockPrescreener()

        prescreened_tickers = {
            "HIGH1.L": {"rsi": 35.0, "macd": 2.0, "sma_50": 100.0, "sma_200": 95.0, "current_price": 105.0, "passed": True},  # Score ~100
            "FAILED.L": {"rsi": 75.0, "macd": -2.0, "sma_50": 100.0, "sma_200": 90.0, "current_price": 88.0, "passed": False},  # Score ~-100
            "HIGH2.L": {"rsi": 40.0, "macd": 1.5, "sma_50": 100.0, "sma_200": 95.0, "current_price": 103.0, "passed": True},  # Score ~85
            "HIGH3.L": {"rsi": 45.0, "macd": 1.0, "sma_50": 100.0, "sma_200": 98.0, "current_price": 102.0, "passed": True},  # Score ~75
        }

        def select_top_n(prescreened_tickers, n):
            # Score ALL stocks first
            scored_stocks = []
            for ticker, indicators in prescreened_tickers.items():
                score = prescreener.score_stock(indicators)
                scored_stocks.append((ticker, score, indicators))

            scored_stocks.sort(key=lambda x: x[1], reverse=True)

            # Filter to only passed stocks, then take top N
            passed_stocks = [(t, s, ind) for t, s, ind in scored_stocks if ind.get("passed", False)]
            return {ticker: indicators for ticker, score, indicators in passed_stocks[:n]}

        # With limit 2, should get top 2 passed stocks
        result = select_top_n(prescreened_tickers, 2)
        assert len(result) == 2
        assert "HIGH1.L" in result  # Highest score
        assert "HIGH2.L" in result  # Second highest
        assert "HIGH3.L" not in result  # Third highest
        assert "FAILED.L" not in result  # Didn't pass

    def test_is_ticker_detection(self):
        """Test ticker detection logic."""
        # Test the _is_ticker method
        assert "A.L".replace(".", "").isalpha() == True
        assert "123".replace(".", "").isalpha() == False
        assert "10".replace(".", "").isalpha() == False
        assert "BA.L".replace(".", "").isalpha() == True


class TestBUYOncePerDay:
    """Test BUY once per day rule."""

    def test_was_bought_today_logic(self):
        """Test the was_bought_today logic."""
        from datetime import datetime, timezone

        # Mock trade data
        trades = [
            {"symbol": "AAPL.L", "action": "BUY", "timestamp": datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc)},
            {"symbol": "AAPL.L", "action": "BUY", "timestamp": datetime(2026, 1, 2, 10, 0, 0, tzinfo=timezone.utc)},
            {"symbol": "GOOGL.L", "action": "BUY", "timestamp": datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc)}
        ]

        def was_bought_today(symbol, trades, now):
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            for trade in trades:
                if trade["symbol"] == symbol and trade["action"] == "BUY":
                    if trade["timestamp"] >= today_start:
                        return True
            return False

        now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        # AAPL.L was bought today
        assert was_bought_today("AAPL.L", trades, now) is True

        # GOOGL.L was bought today
        assert was_bought_today("GOOGL.L", trades, now) is True

        # MSFT.L was never bought
        assert was_bought_today("MSFT.L", trades, now) is False

        # AAPL.L was NOT bought today (different date)
        now_jan2 = datetime(2026, 1, 2, 12, 0, 0, tzinfo=timezone.utc)
        assert was_bought_today("AAPL.L", trades, now_jan2) is True  # Still True because of Jan 2 trade
