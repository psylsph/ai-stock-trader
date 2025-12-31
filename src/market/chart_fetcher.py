import base64
from pathlib import Path
from typing import Optional

import matplotlib
import yfinance as yf

matplotlib.use('Agg')
import matplotlib.pyplot as plt


class ChartFetcher:
    """Fetcher for stock chart images generated locally."""

    def __init__(self, cache_dir: str = "cache/charts"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    async def fetch_chart_image(
        self,
        symbol: str,
        period: str = "1mo",
        use_cache: bool = True
    ) -> Optional[str]:
        """Generate and save chart image. Returns path to image.

        Args:
            symbol: Stock symbol
            period: Chart period (1mo, 3mo, 6mo, 1y, etc.)
            use_cache: Whether to use cached images if available

        Returns:
            Path to saved chart image, or None if generation fails
        """
        cache_key = f"{symbol}_{period}.png"
        cache_path = self.cache_dir / cache_key

        if use_cache and cache_path.exists():
            return str(cache_path)

        return await self._generate_chart_with_matplotlib(symbol, period, cache_path)

    async def _generate_chart_with_matplotlib(
        self,
        symbol: str,
        period: str,
        output_path: Path
    ) -> Optional[str]:
        """Generate chart using yfinance data and matplotlib."""
        try:
            ticker = yf.Ticker(symbol)
            data = ticker.history(period=period)

            if data.empty:
                return None

            fig, ax = plt.subplots(figsize=(12, 6))
            ax.plot(data.index, data['Close'], label='Close Price', linewidth=2)
            ax.set_title(f'{symbol} - {period.upper()} Chart')
            ax.set_xlabel('Date')
            ax.set_ylabel('Price (GBP)')
            ax.grid(True, alpha=0.3)
            ax.legend()
            plt.tight_layout()
            plt.savefig(output_path, dpi=100)
            plt.close(fig)

            return str(output_path)
        except Exception as e:
            print(f"Error generating chart for {symbol}: {e}")
            return None

    def image_to_base64(self, image_path: str) -> str:
        """Convert image file to base64 data URI for LM Studio API."""
        with open(image_path, 'rb', encoding=None) as image_file:
            base64_data = base64.b64encode(image_file.read()).decode('utf-8')
            mime_type = "image/png"
            return f"data:{mime_type};base64,{base64_data}"
