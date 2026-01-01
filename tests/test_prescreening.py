"""Tests for stock prescreening and technical analysis."""

import pytest
from unittest.mock import MagicMock, AsyncMock
from src.trading.prescreening import StockPrescreener


class TestTechnicalIndicators:
    """Test technical indicator calculations."""

    def test_calculate_rsi(self):
        """Test RSI calculation."""
        prescreener = StockPrescreener()

        # Sample prices (random walk)
        prices = [100.0, 101.0, 102.0, 101.0, 103.0, 104.0, 103.0, 105.0, 104.0, 106.0, 105.0, 107.0, 108.0, 109.0, 110.0]

        rsi = prescreener.calculate_rsi(prices)

        # RSI should be between 0 and 100
        assert 0 <= rsi <= 100

    def test_calculate_rsi_few_data_points(self):
        """Test RSI with minimal data."""
        prescreener = StockPrescreener()

        # Not enough data for RSI
        prices = [100.0, 101.0, 102.0]

        rsi = prescreener.calculate_rsi(prices)

        # Should return default 50.0 for insufficient data
        assert rsi == 50.0

    def test_calculate_sma(self):
        """Test SMA calculation."""
        prescreener = StockPrescreener()

        prices = [10.0, 20.0, 30.0, 40.0, 50.0]

        sma_3 = prescreener.calculate_sma(prices, 3)
        sma_5 = prescreener.calculate_sma(prices, 5)

        # SMA of last 3 prices
        assert sma_3 == (30.0 + 40.0 + 50.0) / 3

        # SMA of all prices
        assert sma_5 == (10.0 + 20.0 + 30.0 + 40.0 + 50.0) / 5

    def test_calculate_sma_insufficient_data(self):
        """Test SMA with insufficient data."""
        prescreener = StockPrescreener()

        prices = [10.0, 20.0]

        sma = prescreener.calculate_sma(prices, 5)

        # Should return last price for insufficient data
        assert sma == 20.0

    def test_calculate_macd(self):
        """Test MACD calculation."""
        prescreener = StockPrescreener()

        # Sample prices - need at least 26 for MACD
        prices = [100.0 + i for i in range(30)]

        macd, signal = prescreener.calculate_macd(prices)

        # MACD and signal should be floats
        assert isinstance(macd, float)
        assert isinstance(signal, float)

    def test_calculate_macd_short_data(self):
        """Test MACD with short price history."""
        prescreener = StockPrescreener()

        prices = [100.0, 101.0, 102.0]

        macd, signal = prescreener.calculate_macd(prices)

        # Should return 0, 0 for short data
        assert macd == 0.0
        assert signal == 0.0


class TestStockScoring:
    """Test stock scoring and ranking."""

    def test_score_stock_bullish(self):
        """Test scoring a bullish stock."""
        prescreener = StockPrescreener()

        indicators = {
            "rsi": 45.0,
            "macd": 2.5,
            "sma_50": 95.0,
            "sma_200": 90.0,
            "current_price": 100.0,
            "passed": True
        }

        score = prescreener.score_stock(indicators)

        # Should have positive score for bullish setup
        assert score > 0

    def test_score_stock_bearish(self):
        """Test scoring a bearish stock."""
        prescreener = StockPrescreener()

        indicators = {
            "rsi": 80.0,
            "macd": -3.0,
            "sma_50": 95.0,
            "sma_200": 90.0,
            "current_price": 92.0,
            "passed": False
        }

        score = prescreener.score_stock(indicators)

        # Should have negative score for bearish setup
        assert score < 0

    def test_score_stock_overbought(self):
        """Test scoring an overbought stock."""
        prescreener = StockPrescreener()

        indicators = {
            "rsi": 75.0,  # Overbought
            "macd": 1.0,
            "sma_50": 95.0,
            "sma_200": 90.0,
            "current_price": 100.0,
            "passed": True
        }

        score = prescreener.score_stock(indicators)

        # RSI > 70 gives penalty
        assert score < 50  # Should be penalized


class TestPrescreening:
    """Test stock prescreening logic."""

    def test_evaluate_indicators_pass(self):
        """Test indicators that pass screening."""
        prescreener = StockPrescreener()

        # Bullish setup: RSI < 70, Price > SMA50, MACD > 0
        result = prescreener._evaluate_indicators(
            rsi=45.0,
            macd=1.5,
            signal=0.5,
            sma_50=95.0,
            sma_200=90.0,
            current_price=100.0
        )

        # Should pass (at least 2 of 3 conditions)
        assert result is True

    def test_evaluate_indicators_fail(self):
        """Test indicators that fail screening."""
        prescreener = StockPrescreener()

        # Bearish setup: RSI > 70, Price < SMA50, MACD < 0
        result = prescreener._evaluate_indicators(
            rsi=75.0,
            macd=-2.0,
            signal=-1.0,
            sma_50=100.0,
            sma_200=90.0,
            current_price=95.0
        )

        # Should fail
        assert result is False

    def test_evaluate_indicators_boundary(self):
        """Test boundary case for screening."""
        prescreener = StockPrescreener()

        # RSI exactly at threshold - should fail (RSI >= 70 always fails)
        result = prescreener._evaluate_indicators(
            rsi=70.0,
            macd=0.5,
            signal=0.2,
            sma_50=95.0,
            sma_200=90.0,
            current_price=100.0
        )

        # RSI = 70 means overbought - fails
        assert result is False

    def test_evaluate_indicators_rsi_overbought(self):
        """Test that RSI >= 70 always fails."""
        prescreener = StockPrescreener()

        # Even with bullish MACD and price > SMA50
        result = prescreener._evaluate_indicators(
            rsi=70.0,  # Exactly at threshold - fails
            macd=5.0,
            signal=2.0,
            sma_50=90.0,
            sma_200=80.0,
            current_price=100.0
        )

        assert result is False

    def test_evaluate_indicators_all_bullish(self):
        """Test with all bullish criteria."""
        prescreener = StockPrescreener()

        result = prescreener._evaluate_indicators(
            rsi=25.0,  # Oversold
            macd=3.0,  # Strong momentum
            signal=1.5,
            sma_50=95.0,
            sma_200=90.0,
            current_price=100.0  # Above SMA50
        )

        assert result is True


class TestStockRanking:
    """Test stock ranking by technical score."""

    def test_score_stock_sorting(self):
        """Test that scores can be used for sorting."""
        prescreener = StockPrescreener()

        stocks = [
            {"rsi": 75.0, "macd": -2.0, "sma_50": 100.0, "current_price": 95.0},
            {"rsi": 45.0, "macd": 2.0, "sma_50": 95.0, "current_price": 100.0},
            {"rsi": 25.0, "macd": 3.0, "sma_50": 90.0, "current_price": 95.0}
        ]

        scored = [(s["rsi"], prescreener.score_stock(s)) for s in stocks]

        # Sort by score descending
        scored.sort(key=lambda x: x[1], reverse=True)

        # Most bullish should be first
        assert scored[0][0] == 25.0  # Lowest RSI
        assert scored[2][0] == 75.0  # Highest RSI

    def test_score_calculation_breakdown(self):
        """Test score calculation components."""
        prescreener = StockPrescreener()

        # Very bullish: RSI < 30 (+40), MACD > 0 (+30), Price > SMA50 (+30) = 100
        indicators = {
            "rsi": 25.0,
            "macd": 1.0,
            "sma_50": 95.0,
            "current_price": 100.0
        }

        score = prescreener.score_stock(indicators)

        # Should be 100 (40 + 30 + 30)
        assert score == 100.0

    def test_score_bearish(self):
        """Test bearish stock scoring."""
        prescreener = StockPrescreener()

        # Bearish: RSI > 70 (-100), MACD < 0 (0), Price < SMA50 (0) = -100
        indicators = {
            "rsi": 75.0,
            "macd": -1.0,
            "sma_50": 100.0,
            "current_price": 95.0
        }

        score = prescreener.score_stock(indicators)

        # Should be -100
        assert score == -100.0


class TestPrescreenStocks:
    """Test async prescreening functionality."""

    @pytest.mark.asyncio
    async def test_prescreen_stocks_empty(self):
        """Test prescreening with no tickers."""
        prescreener = StockPrescreener()

        mock_fetcher = MagicMock()
        mock_fetcher.get_historical = AsyncMock(return_value=[])

        result = await prescreener.prescreen_stocks([], mock_fetcher)

        assert result == {}

    @pytest.mark.asyncio
    async def test_prescreen_stocks_single(self):
        """Test prescreening a single stock."""
        prescreener = StockPrescreener()

        # Create mock OHLCV data
        class MockOHLCV:
            close = 100.0
            volume = 1000000

        mock_fetcher = MagicMock()
        mock_fetcher.get_historical = AsyncMock(return_value=[MockOHLCV() for _ in range(60)])

        result = await prescreener.prescreen_stocks(["TEST.L"], mock_fetcher)

        assert "TEST.L" in result
        assert "rsi" in result["TEST.L"]
        assert "passed" in result["TEST.L"]
