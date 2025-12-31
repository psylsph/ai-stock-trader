"""News fetcher for retrieving market news from RSS feeds."""

import asyncio
from typing import List, Dict

try:
    import feedparser  # pylint: disable=import-error
except ImportError:
    feedparser = None


class NewsFetcher:
    """Fetcher for retrieving news from RSS feeds."""

    def __init__(self, rss_urls: List[str]):
        """Initialize the news fetcher.

        Args:
            rss_urls: List of RSS feed URLs to fetch news from.
        """
        self.rss_urls = rss_urls

    async def _fetch_feed(self, url: str) -> List[Dict[str, str]]:
        """Fetch and parse an RSS feed.

        Args:
            url: The RSS feed URL.

        Returns:
            List of news items from the feed.
        """
        # feedparser is synchronous, so we run it in an executor
        loop = asyncio.get_event_loop()
        try:
            feed = await loop.run_in_executor(None, feedparser.parse, url)

            # Extract top 3 entries from each feed
            entries = []
            for entry in feed.entries[:3]:
                entries.append({
                    "title": entry.get("title", "No Title"),
                    "summary": entry.get(
                        "summary", entry.get("description", "No Summary")
                    ),
                    "link": entry.get("link", url),
                    "source": feed.feed.get("title", url)
                })
            return entries
        except Exception as e:  # pylint: disable=broad-except
            print(f"Error fetching feed {url}: {e}")
            return []

    async def get_news_summary(self) -> str:
        """Fetch news from all feeds and return a formatted summary string.

        Returns:
            Formatted string containing recent news summaries.
        """
        tasks = [self._fetch_feed(url) for url in self.rss_urls]
        results = await asyncio.gather(*tasks)

        # Flatten results
        all_news = [item for sublist in results for item in sublist]

        if not all_news:
            return "No recent news available."

        summary_lines = ["RECENT MARKET NEWS:"]
        for item in all_news:
            summary_lines.append(f"- [{item['source']}] {item['title']}")
            # Summary can be long, so maybe truncate or omit to save tokens
            # summary_lines.append(f"  {item['summary'][:150]}...")

        return "\n".join(summary_lines)
