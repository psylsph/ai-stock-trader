import asyncio
from src.market.news_fetcher import NewsFetcher

RSS_FEEDS = [
    "https://www.ft.com/rss/home/international",
    "https://money.com/money/feed/"
]

async def verify():
    print(f"Fetching news from {len(RSS_FEEDS)} feeds...")
    fetcher = NewsFetcher(RSS_FEEDS)
    summary = await fetcher.get_news_summary()
    
    print("\n--- News Summary ---")
    print(summary)
    print("\n--- End Summary ---")
    
    if "RECENT MARKET NEWS:" in summary and "Error" not in summary:
        print("\nVerification Passed!")
    elif "No recent news" in summary:
        print("\nVerification Warning: No news found (could be network or empty feeds).")
    else:
        print("\nVerification Failed.")

if __name__ == "__main__":
    asyncio.run(verify())
