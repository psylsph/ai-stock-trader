import asyncio
import os
import sys
from src.market.data_fetcher import AlphaVantageFetcher

async def verify():
    api_key = os.getenv("MARKET_DATA_API_KEY")
    if not api_key:
        print("Error: MARKET_DATA_API_KEY not found in env.")
        # Try to load from .env manually if not running via main wrapper
        from dotenv import load_dotenv
        load_dotenv()
        api_key = os.getenv("MARKET_DATA_API_KEY")
    
    if not api_key:
        print("Error: Still no API key found.")
        return

    print(f"Using API Key: {api_key[:4]}***")
    fetcher = AlphaVantageFetcher(api_key)
    
    try:
        symbol = "LLOY.L"
        print(f"Fetching quote for {symbol}...")
        quote = await fetcher.get_quote(symbol)
        print(f"Success! Price: {quote.price}")
        
        print("Waiting 15s for rate limit...")
        await asyncio.sleep(15)
        
        print(f"Fetching history for {symbol}...")
        history = await fetcher.get_historical(symbol)
        print(f"Success! History points: {len(history)}")
        print(f"First point: {history[0]}")
        print(f"Last point: {history[-1]}")
        
    except Exception as e:
        print(f"Verification Failed: {e}")

if __name__ == "__main__":
    asyncio.run(verify())
