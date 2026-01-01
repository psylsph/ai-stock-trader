"""Stock prescreening module using technical indicators."""

import asyncio
from typing import List, Dict, Any


class StockPrescreener:
    """Prescreen FTSE 100 stocks using technical indicators."""

    def calculate_rsi(self, prices: List[float]) -> float:
        """Calculate RSI (Relative Strength Index) with 14-period."""
        if len(prices) < 15:
            return 50.0

        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]

        gains = [delta for delta in deltas[-14:] if delta > 0]
        losses = [abs(delta) for delta in deltas[-14:] if delta < 0]

        avg_gain = sum(gains) / len(gains) if gains else 0.0
        avg_loss = sum(losses) / len(losses) if losses else 0.0

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return float(rsi)

    def calculate_macd(self, prices: List[float]) -> tuple[float, float]:
        """Calculate MACD (Moving Average Convergence Divergence)."""
        if len(prices) < 26:
            return 0.0, 0.0

        multiplier_12 = 2 / (12 + 1)
        multiplier_26 = 2 / (26 + 1)
        multiplier_9 = 2 / (9 + 1)

        ema_12 = prices[-1]
        ema_26 = prices[-1]

        for price in prices[-12:]:
            ema_12 = (price * multiplier_12) + (ema_12 * (1 - multiplier_12))

        for price in prices[-26:]:
            ema_26 = (price * multiplier_26) + (ema_26 * (1 - multiplier_26))

        macd = ema_12 - ema_26

        macd_series = [macd]
        for price in prices[-25:]:
            macd_series.append(macd)

        signal = macd_series[-1]
        for val in macd_series[-9:]:
            signal = (val * multiplier_9) + (signal * (1 - multiplier_9))

        return float(macd), float(signal)

    def calculate_sma(self, prices: List[float], period: int) -> float:
        """Calculate Simple Moving Average."""
        if len(prices) < period:
            return prices[-1] if prices else 50.0

        return float(sum(prices[-period:]) / period)

    def calculate_bollinger_bands(self, prices: List[float], period: int = 20, std_mult: float = 2.0) -> tuple[float, float, float]:
        """
        Calculate Bollinger Bands.
        
        Returns:
            Tuple of (lower_band, middle_band, upper_band)
        """
        if len(prices) < period:
            return 0.0, 0.0, 0.0
        
        middle = self.calculate_sma(prices, period)
        
        # Calculate standard deviation
        slice_prices = prices[-period:]
        variance = sum((p - middle) ** 2 for p in slice_prices) / period
        std_dev = variance ** 0.5
        
        lower = middle - (std_mult * std_dev)
        upper = middle + (std_mult * std_dev)
        
        return float(lower), float(middle), float(upper)

    async def prescreen_stocks(
        self,
        tickers: List[str],
        data_fetcher
    ) -> Dict[str, Dict[str, Any]]:
        """
        Prescreen stocks based on technical indicators.

        Returns:
            Dict mapping ticker to indicator results
        """
        results = {}

        tasks = [self._analyze_ticker(ticker, data_fetcher) for ticker in tickers]
        ticker_results = await asyncio.gather(*tasks, return_exceptions=True)

        for ticker, result in zip(tickers, ticker_results):
            if isinstance(result, Exception):
                results[ticker] = {  # type: ignore[assignment]
                    "rsi": 50.0,
                    "macd": 0.0,
                    "signal": 0.0,
                    "sma_50": 50.0,
                    "sma_200": 50.0,
                    "current_price": 0.0,
                    "passed": False
                }
            else:
                results[ticker] = result  # type: ignore[assignment]

        return results

    async def _analyze_ticker(
        self,
        ticker: str,
        data_fetcher
    ) -> Dict[str, Any]:
        """Analyze a single ticker."""
        try:
            history = await data_fetcher.get_historical(ticker, period="2y")

            if not history or len(history) < 50:
                return {
                    "rsi": 50.0,
                    "macd": 0.0,
                    "signal": 0.0,
                    "sma_50": 50.0,
                    "sma_200": 50.0,
                    "bb_lower": 0.0,
                    "bb_middle": 0.0,
                    "bb_upper": 0.0,
                    "current_price": 0.0,
                    "passed": False
                }

            prices = [h.close for h in history]

            rsi = self.calculate_rsi(prices)
            macd, signal = self.calculate_macd(prices)
            sma_50 = self.calculate_sma(prices, 50)
            sma_200 = self.calculate_sma(prices, 200)
            bb_lower, bb_middle, bb_upper = self.calculate_bollinger_bands(prices)

            current_price = prices[-1]

            passed = self._evaluate_indicators(
                rsi=rsi,
                macd=macd,
                signal=signal,
                sma_50=sma_50,
                sma_200=sma_200,
                bb_lower=bb_lower,
                bb_upper=bb_upper,
                current_price=current_price
            )

            return {
                "rsi": rsi,
                "macd": macd,
                "signal": signal,
                "sma_50": sma_50,
                "sma_200": sma_200,
                "bb_lower": bb_lower,
                "bb_middle": bb_middle,
                "bb_upper": bb_upper,
                "current_price": current_price,
                "passed": bool(passed)
            }

        except Exception:
            return {
                "rsi": 50.0,
                "macd": 0.0,
                "signal": 0.0,
                "sma_50": 50.0,
                "sma_200": 50.0,
                "bb_lower": 0.0,
                "bb_middle": 0.0,
                "bb_upper": 0.0,
                "current_price": 0.0,
                "passed": False
            }

    def _evaluate_indicators(
        self,
        rsi: float,
        macd: float,
        signal: float,
        sma_50: float,
        sma_200: float,
        bb_lower: float,
        bb_upper: float,
        current_price: float
    ) -> bool:
        """Evaluate if stock passes prescreening criteria."""
        # MUST NOT be overbought (RSI > 70) or at upper Bollinger Band
        if rsi >= 70:
            return False

        criteria_met = 0

        # Bullish criteria (must meet at least 2)
        if rsi < 30: # Oversold / Value opportunity
            criteria_met += 1

        if current_price > sma_50: # Uptrend
            criteria_met += 1

        if macd > 0: # Momentum
            criteria_met += 1

        if bb_lower > 0 and current_price <= bb_lower: # At or below lower Bollinger Band (oversold)
            criteria_met += 1

        return criteria_met >= 2

    def score_stock(self, indicators: Dict[str, Any]) -> float:
        """
        Calculate a technical score for sorting.
        Higher is better.
        """
        score = 0.0
        
        rsi = indicators.get("rsi", 50.0)
        macd = indicators.get("macd", 0.0)
        current_price = indicators.get("current_price", 0.0)
        sma_50 = indicators.get("sma_50", 0.0)
        bb_lower = indicators.get("bb_lower", 0.0)
        bb_upper = indicators.get("bb_upper", 0.0)
        bb_middle = indicators.get("bb_middle", 0.0)
        
        # 1. RSI Score: Smooth curve - lower is better but not overbought
        if rsi < 30:
            score += 40  # Very bullish (oversold)
        elif rsi < 40:
            score += 30  # Bullish
        elif rsi < 50:
            score += 25  # Mildly bullish
        elif rsi < 60:
            score += 15  # Neutral
        elif rsi < 70:
            score += 5   # Mildly bearish
        else:
            score -= 50  # Overbought penalty
            
        # 2. MACD Score: Positive MACD is bullish
        if macd > 0:
            score += 30
            
        # 3. Trend Score: Price above SMA 50
        if current_price > sma_50:
            score += 30
            
        # 4. Bollinger Bands Score
        if bb_lower > 0 and bb_upper > 0:
            bb_range = bb_upper - bb_lower
            if bb_range > 0:
                # Price position within bands (0 = at lower band, 1 = at upper band)
                price_position = (current_price - bb_lower) / bb_range
                
                # Reward being near or below lower band (oversold)
                if price_position < 0.1:  # Within 10% of lower band
                    score += 25
                elif price_position < 0.2:  # Within 20% of lower band
                    score += 15
                elif price_position < 0.3:  # Within 30% of lower band
                    score += 5
                    
                # Penalize being near or above upper band (overbought)
                if price_position > 0.9:  # Within 10% of upper band
                    score -= 15
                elif price_position > 0.8:  # Within 20% of upper band
                    score -= 5
                    
        return score
