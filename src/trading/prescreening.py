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
                results[ticker] = {
                    "rsi": 50.0,
                    "macd": 0.0,
                    "signal": 0.0,
                    "sma_50": 50.0,
                    "sma_200": 50.0,
                    "current_price": 0.0,
                    "passed": False
                }
            else:
                results[ticker] = result
        
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
                    "current_price": 0.0,
                    "passed": False
                }
            
            prices = [h.close for h in history]
            
            rsi = self.calculate_rsi(prices)
            macd, signal = self.calculate_macd(prices)
            sma_50 = self.calculate_sma(prices, 50)
            sma_200 = self.calculate_sma(prices, 200)
            
            current_price = prices[-1]
            
            passed = self._evaluate_indicators(
                rsi=rsi,
                macd=macd,
                signal=signal,
                sma_50=sma_50,
                sma_200=sma_200,
                current_price=current_price
            )
            
            return {
                "rsi": rsi,
                "macd": macd,
                "signal": signal,
                "sma_50": sma_50,
                "sma_200": sma_200,
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
        current_price: float
    ) -> bool:
        """Evaluate if stock passes prescreening criteria."""
        criteria_met = 0
        
        if rsi < 70:
            criteria_met += 1
        
        if current_price > sma_50:
            criteria_met += 1
        
        if macd > 0:
            criteria_met += 1
        
        return criteria_met >= 2
