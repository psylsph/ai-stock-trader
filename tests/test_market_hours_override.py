import pytest
from datetime import datetime, time
import pytz
from src.config.settings import settings
from src.market.data_fetcher import YahooFinanceFetcher, MarketStatus

@pytest.mark.asyncio
async def test_market_hours_override():
    """Test that IGNORE_MARKET_HOURS override works."""
    fetcher = YahooFinanceFetcher()
    
    # Force override to True
    original_override = settings.IGNORE_MARKET_HOURS
    settings.IGNORE_MARKET_HOURS = True
    
    try:
        status = await fetcher.get_market_status()
        assert status.is_open is True
    finally:
        # Restore original setting
        settings.IGNORE_MARKET_HOURS = original_override

@pytest.mark.asyncio
async def test_market_hours_normal_logic():
    """Test that normal market hours logic still works when override is False."""
    fetcher = YahooFinanceFetcher()
    
    # Force override to False
    original_override = settings.IGNORE_MARKET_HOURS
    settings.IGNORE_MARKET_HOURS = False
    
    try:
        # We can't easily mock datetime.now() without a lot of effort or a library
        # but we can check if the logic seems consistent with the current time
        status = await fetcher.get_market_status()
        
        # Determine what it SHOULD be based on current London time
        london_tz = pytz.timezone("Europe/London")
        now = datetime.now(london_tz)
        
        expected_is_open = True
        if now.weekday() >= 5:
            expected_is_open = False
        else:
            market_open = time(8, 0)
            market_close = time(16, 30)
            expected_is_open = market_open <= now.time() <= market_close
            
        assert status.is_open == expected_is_open
    finally:
        settings.IGNORE_MARKET_HOURS = original_override
