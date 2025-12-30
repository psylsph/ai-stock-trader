import pytest
import asyncio
from src.ai.tools import TradingTools
from src.market.yahoo_news_fetcher import YahooNewsFetcher
from src.market.chart_fetcher import ChartFetcher
from src.market.data_fetcher import YahooFinanceFetcher


@pytest.mark.asyncio
async def test_ticker_news_fetch():
    fetcher = YahooNewsFetcher()
    news = await fetcher.get_ticker_news("LLOY.L")
    assert isinstance(news, list)


@pytest.mark.asyncio
async def test_chart_generation():
    fetcher = ChartFetcher()
    chart_path = await fetcher.fetch_chart_image("LLOY.L", period="1mo")
    assert chart_path is not None
    assert "LLOY.L" in chart_path


@pytest.mark.asyncio
async def test_tool_execution():
    news_fetcher = YahooNewsFetcher()
    chart_fetcher = ChartFetcher()
    data_fetcher = YahooFinanceFetcher()
    tools = TradingTools(news_fetcher, chart_fetcher, data_fetcher)
    
    result = await tools.execute_tool("get_current_quote", {"symbol": "LLOY.L"})
    assert "symbol" in result
    assert result["symbol"] == "LLOY.L"
