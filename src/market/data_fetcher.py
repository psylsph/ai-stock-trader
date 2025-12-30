"""Market data fetcher for retrieving stock information."""

import asyncio
import time as time_module
from abc import ABC, abstractmethod
from datetime import datetime, time
from typing import List, Optional

try:
    from pydantic import BaseModel  # pylint: disable=import-error
except ImportError:
    BaseModel = object

try:
    import aiohttp  # pylint: disable=import-error
except ImportError:
    aiohttp = None

try:
    import yfinance as yf  # pylint: disable=import-error
except ImportError:
    yf = None

import pytz


class Quote(BaseModel):
    symbol: str
    price: float
    change: float
    change_percent: float
    volume: int
    timestamp: datetime

class OHLCV(BaseModel):
    """Model representing OHLCV (Open, High, Low, Close, Volume) data."""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


class MarketStatus(BaseModel):
    """Model representing the market status."""
    is_open: bool
    next_open: Optional[datetime]
    next_close: Optional[datetime]


class MarketDataFetcher(ABC):
    """Abstract base class for market data fetchers."""

    @abstractmethod
    async def get_quote(self, symbol: str) -> Quote:
        """Get current quote for a symbol."""

    @abstractmethod
    async def get_historical(
        self, symbol: str, period: str = "1mo"
    ) -> List[OHLCV]:
        """Get historical OHLCV data for a symbol."""

    @abstractmethod
    async def get_market_status(self) -> MarketStatus:
        """Get current market status."""


class YahooFinanceFetcher(MarketDataFetcher):
    """Market data fetcher using Yahoo Finance API."""

    def __init__(self):
        """Initialize the Yahoo Finance fetcher."""
        self.tz = pytz.timezone("Europe/London")

    def _format_symbol(self, symbol: str) -> str:
        """Format symbol for Yahoo Finance.

        Args:
            symbol: The stock symbol.

        Returns:
            Formatted symbol with .L suffix for LSE.
        """
        if not symbol.endswith(".L") and not symbol.endswith(".l"):
            return f"{symbol}.L"
        return symbol

    async def get_quote(self, symbol: str) -> Quote:
        """Get current quote for a symbol.

        Args:
            symbol: The stock symbol.

        Returns:
            Quote object with current price data.
        """
        formatted_symbol = self._format_symbol(symbol)
        ticker = yf.Ticker(formatted_symbol)
        info = ticker.fast_info

        return Quote(
            symbol=symbol,
            price=info.last_price,
            change=info.last_price - info.previous_close,
            change_percent=(
                (info.last_price - info.previous_close) /
                info.previous_close
            ) * 100,
            volume=info.last_volume,
            timestamp=datetime.now(self.tz)
        )

    async def get_historical(
        self, symbol: str, period: str = "1mo"
    ) -> List[OHLCV]:
        """Get historical OHLCV data for a symbol.

        Args:
            symbol: The stock symbol.
            period: The time period for historical data.

        Returns:
            List of OHLCV objects.
        """
        formatted_symbol = self._format_symbol(symbol)
        ticker = yf.Ticker(formatted_symbol)
        history = ticker.history(period=period)

        results = []
        for index, row in history.iterrows():
            results.append(OHLCV(
                timestamp=index.to_pydatetime(),
                open=row["Open"],
                high=row["High"],
                low=row["Low"],
                close=row["Close"],
                volume=row["Volume"]
            ))
        return results

    async def get_market_status(self) -> MarketStatus:
        """Get current market status.

        Returns:
            MarketStatus object with current market state.
        """
        now = datetime.now(self.tz)
        if now.weekday() >= 5:
            return MarketStatus(is_open=False, next_open=None, next_close=None)
        market_open = time(8, 0)
        market_close = time(16, 30)
        is_open = market_open <= now.time() <= market_close
        return MarketStatus(is_open=is_open, next_open=None, next_close=None)


class AlphaVantageFetcher(MarketDataFetcher):
    """Market data fetcher using Alpha Vantage API."""

    def __init__(self, api_key: str):
        """Initialize the Alpha Vantage fetcher.

        Args:
            api_key: The Alpha Vantage API key.
        """
        self.api_key = api_key
        self.base_url = "https://www.alphavantage.co/query"
        self.tz = pytz.timezone("Europe/London")
        self.last_request_time = 0
        self.min_interval = 1.1  # 1.1s to be safe

    def _format_symbol(self, symbol: str) -> str:
        """Format symbol for Alpha Vantage.

        Args:
            symbol: The stock symbol.

        Returns:
            Formatted symbol with .L suffix for LSE.
        """
        # Alpha Vantage supports LSE symbols with .LON suffix sometimes or .L?
        # Check docs: LSE usually requires .L or .LON. Alpha Vantage usually
        # supports standard exchange suffixes. But commonly for LSE, it might need
        # to be "LLOY.LON" or just "LLOY.L". Standard Alpha Vantage
        # convention for LSE is often ".LON" or just checking "LLOY.L".
        # Let's try ".L" first as it is most common for non-US.
        if not symbol.endswith(".L") and not symbol.endswith(".LON"):
            return f"{symbol}.L"
        return symbol

    async def _get_json(self, params: dict):
        """Make a JSON request to Alpha Vantage API.

        Args:
            params: Query parameters for the API request.

        Returns:
            JSON response from the API.

        Raises:
            Exception: If API request fails or rate limit is exceeded.
        """
        # Rate limiting
        elapsed = time_module.time() - self.last_request_time
        if elapsed < self.min_interval:
            await asyncio.sleep(self.min_interval - elapsed)

        params["apikey"] = self.api_key
        self.last_request_time = time_module.time()

        async with aiohttp.ClientSession() as session:
            async with session.get(self.base_url, params=params) as response:
                if response.status != 200:
                    raise Exception(  # pylint: disable=broad-exception-raised
                        f"Alpha Vantage API error: {response.status}"
                    )
                data = await response.json()

                if ("Information" in data and
                        "rate limit" in data["Information"].lower()):
                    raise Exception(  # pylint: disable=broad-exception-raised
                        f"Alpha Vantage Rate Limit: {data['Information']}"
                    )

                return data

    async def get_quote(self, symbol: str) -> Quote:
        """Get current quote for a symbol.

        Args:
            symbol: The stock symbol.

        Returns:
            Quote object with current price data.
        """
        symbol = self._format_symbol(symbol)
        data = await self._get_json({
            "function": "GLOBAL_QUOTE",
            "symbol": symbol
        })

        # Parse Response
        # { "Global Quote": { "01. symbol": "...", "05. price": "...", ... } }
        q = data.get("Global Quote", {})
        if not q:
            raise ValueError(f"No quote data found for {symbol}: {data}")

        return Quote(
            symbol=q.get("01. symbol", symbol),
            price=float(q.get("05. price", 0)),
            change=float(q.get("09. change", 0)),
            change_percent=float(
                q.get("10. change percent", "0").replace("%", "")
            ),
            volume=int(q.get("06. volume", 0)),
            timestamp=datetime.now(self.tz)
        )

    async def get_historical(
        self, symbol: str, period: str = "1mo"
    ) -> List[OHLCV]:
        """Get historical OHLCV data for a symbol.

        Args:
            symbol: The stock symbol.
            period: The time period for historical data.

        Returns:
            List of OHLCV objects.

        Raises:
            Exception: If API request fails or rate limit is exceeded.
        """
        symbol = self._format_symbol(symbol)
        data = await self._get_json({
            "function": "TIME_SERIES_DAILY",
            "symbol": symbol,
            "outputsize": "compact"
        })

        if "Error Message" in data:
            raise Exception(  # pylint: disable=broad-exception-raised
                f"API Error: {data['Error Message']}"
            )

        if "Information" in data:
            # Rate limit or premium endpoint message
            raise Exception(  # pylint: disable=broad-exception-raised
                f"API Rate Limit/Info: {data['Information']}"
            )

        ts = data.get("Time Series (Daily)", {})
        results = []
        for date_str, values in ts.items():
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            results.append(OHLCV(
                timestamp=dt,
                open=float(values["1. open"]),
                high=float(values["2. high"]),
                low=float(values["3. low"]),
                close=float(values["4. close"]),
                volume=int(values["5. volume"])
            ))

        # Sort by date ascending
        results.sort(key=lambda x: x.timestamp)
        return results

    async def get_market_status(self) -> MarketStatus:
        """Get current market status.

        Returns:
            MarketStatus object with current market state.
        """
        # Re-use same local time logic as Yahoo for now as AV doesn't have
        # a status endpoint
        now = datetime.now(self.tz)
        if now.weekday() >= 5:
            return MarketStatus(is_open=False, next_open=None, next_close=None)
        market_open = time(8, 0)
        market_close = time(16, 30)
        is_open = market_open <= now.time() <= market_close
        return MarketStatus(is_open=is_open, next_open=None, next_close=None)
