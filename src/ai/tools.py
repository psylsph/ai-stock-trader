from typing import Dict, Any

from src.market.yahoo_news_fetcher import YahooNewsFetcher
from src.market.chart_fetcher import ChartFetcher
from src.market.data_fetcher import MarketDataFetcher


class TradingTools:
    """Collection of tools for AI trading agent."""

    def __init__(
        self,
        news_fetcher: YahooNewsFetcher,
        chart_fetcher: ChartFetcher,
        data_fetcher: MarketDataFetcher
    ):
        self.news_fetcher = news_fetcher
        self.chart_fetcher = chart_fetcher
        self.data_fetcher = data_fetcher

    def get_tool_schemas(self) -> list[Dict[str, Any]]:
        """Return tool schemas for OpenAI function calling."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "get_ticker_news",
                    "description": "Fetch recent news articles for a specific stock ticker from Yahoo Finance",
                    "parameters": {
                        "type": "object",
                        "required": ["symbol"],
                        "properties": {
                            "symbol": {
                                "type": "string",
                                "description": "Stock ticker symbol (e.g., 'LLOY.L')"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of news items (default: 5)",
                                "default": 5
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_price_history",
                    "description": "Get historical price data for a stock ticker",
                    "parameters": {
                        "type": "object",
                        "required": ["symbol"],
                        "properties": {
                            "symbol": {
                                "type": "string",
                                "description": "Stock ticker symbol (e.g., 'LLOY.L')"
                            },
                            "period": {
                                "type": "string",
                                "description": "Time period (1mo, 3mo, 6mo, 1y, default: 1mo)",
                                "default": "1mo"
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_current_quote",
                    "description": "Get current market quote for a stock ticker",
                    "parameters": {
                        "type": "object",
                        "required": ["symbol"],
                        "properties": {
                            "symbol": {
                                "type": "string",
                                "description": "Stock ticker symbol (e.g., 'LLOY.L')"
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "analyze_chart",
                    "description": "Fetch and analyze a stock chart image visually",
                    "parameters": {
                        "type": "object",
                        "required": ["symbol"],
                        "properties": {
                            "symbol": {
                                "type": "string",
                                "description": "Stock ticker symbol (e.g., 'LLOY.L')"
                            },
                            "period": {
                                "type": "string",
                                "description": "Chart period (1mo, 3mo, 6mo, 1y, default: 1mo)",
                                "default": "1mo"
                            }
                        }
                    }
                }
            }
        ]

    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool by name with provided arguments."""
        try:
            if tool_name == "get_ticker_news":
                news = await self.news_fetcher.get_ticker_news(
                    symbol=arguments["symbol"],
                    limit=arguments.get("limit", 5)
                )
                return {"news": news}

            elif tool_name == "get_price_history":
                history = await self.data_fetcher.get_historical(
                    symbol=arguments["symbol"],
                    period=arguments.get("period", "1mo")
                )
                return {
                    "history": [
                        {
                            "timestamp": h.timestamp.isoformat(),
                            "open": h.open,
                            "high": h.high,
                            "low": h.low,
                            "close": h.close,
                            "volume": h.volume
                        }
                        for h in history
                    ]
                }

            elif tool_name == "get_current_quote":
                quote = await self.data_fetcher.get_quote(arguments["symbol"])
                return {
                    "symbol": quote.symbol,
                    "price": quote.price,
                    "change": quote.change,
                    "change_percent": quote.change_percent,
                    "volume": quote.volume,
                    "timestamp": quote.timestamp.isoformat()
                }

            elif tool_name == "analyze_chart":
                chart_path = await self.chart_fetcher.fetch_chart_image(
                    symbol=arguments["symbol"],
                    period=arguments.get("period", "1mo")
                )
                if chart_path:
                    return {
                        "chart_path": chart_path,
                        "analysis_needed": True
                    }
                else:
                    return {"error": "Failed to fetch chart"}

            else:
                return {"error": f"Unknown tool: {tool_name}"}

        except Exception as e:
            return {"error": str(e)}
