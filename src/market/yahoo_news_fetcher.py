import yfinance as yf
from typing import List, Dict


class YahooNewsFetcher:
    """Fetcher for ticker-specific news from Yahoo Finance."""
    
    async def get_ticker_news(self, symbol: str, limit: int = 5) -> List[Dict[str, str]]:
        """Fetch recent news for a specific ticker.
        
        Args:
            symbol: Stock symbol (e.g., "LLOY.L")
            limit: Maximum number of news items to return
            
        Returns:
            List of news items with title, link, published_date
        """
        ticker = yf.Ticker(symbol)
        news = ticker.news
        
        if not news:
            return []
            
        formatted_news = []
        for item in news[:limit]:
            formatted_news.append({
                "title": item.get("title", ""),
                "link": item.get("link", ""),
                "published": item.get("providerPublishTime", ""),
                "publisher": item.get("publisher", "")
            })
            
        return formatted_news
