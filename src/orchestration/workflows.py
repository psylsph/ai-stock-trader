"""Trading workflow orchestration for the AI Stock Trader application."""

import asyncio
import json
from datetime import datetime

from src.config import Settings
from src.database.repository import DatabaseRepository
from src.market.data_fetcher import AlphaVantageFetcher, YahooFinanceFetcher
from src.ai.local_ai_client import LocalAIClient
from src.ai.openrouter_client import OpenRouterClient
from src.ai.decision_engine import TradingDecisionEngine
from src.trading.paper_trader import PaperTrader
from src.trading.managers import PositionManager, RiskManager
from src.market.news_fetcher import NewsFetcher
from src.market.yahoo_news_fetcher import YahooNewsFetcher
from src.market.chart_fetcher import ChartFetcher
from src.ai.tools import TradingTools


class TradingWorkflow:
    """Orchestrates the trading workflow including analysis and monitoring."""

    def __init__(self, settings: Settings, repo: DatabaseRepository):
        """Initialize the trading workflow.

        Args:
            settings: Application settings.
            repo: Database repository instance.
        """
        self.settings = settings
        self.repo = repo

        # Initialize Components
        if not settings.MARKET_DATA_API_KEY or settings.MARKET_DATA_API_KEY == "yahoo":
            print("Using Yahoo Finance for market data")
            self.market_data = YahooFinanceFetcher()
        else:
            self.market_data = AlphaVantageFetcher(settings.MARKET_DATA_API_KEY)
        
        self.news_fetcher = NewsFetcher(settings.RSS_FEEDS)
        self.yahoo_news_fetcher = YahooNewsFetcher()
        self.chart_fetcher = ChartFetcher()

        # Initialize Tools
        self.tools = TradingTools(
            news_fetcher=self.yahoo_news_fetcher,
            chart_fetcher=self.chart_fetcher,
            data_fetcher=self.market_data
        )

        # Initialize AI Clients
        self.local_ai = LocalAIClient(
            api_url=settings.LM_STUDIO_API_URL,
            model=settings.LM_STUDIO_MODEL
        )
        self.openrouter_client = OpenRouterClient(
            settings.OPENROUTER_API_KEY, 
            settings.OPENROUTER_MODEL
        )
        self.decision_engine = TradingDecisionEngine(
            self.local_ai, self.openrouter_client
        )

        self.broker = PaperTrader(repo, self.market_data, settings.INITIAL_BALANCE)
        self.position_manager = PositionManager(repo)
        self.risk_manager = RiskManager()

    async def _execute_buy(self, rec: dict, validation: dict, balance: float):
        """Execute a buy order after validation."""
        symbol = rec["symbol"]
        print(f"Fetching quote for {symbol}...")
        quote = await self.market_data.get_quote(symbol)
        current_price = quote.price
        
        size_pct = validation.get("new_size_pct", rec.get("size_pct", 0.05))
        quantity = int((balance * size_pct) / current_price)

        if quantity > 0:
            if self.risk_manager.validate_trade(
                "BUY", quantity, current_price, balance
            ):
                print(f"Executing BUY for {symbol}: {quantity} shares @ £{current_price:.2f}")
                await self.broker.buy(symbol, quantity, current_price)
                new_balance = await self.broker.get_account_balance()
                await self.position_manager.update_position(
                    symbol, quantity, current_price, "BUY", balance=new_balance
                )

    async def run_startup_analysis(self):
        """Run startup market analysis with remote validation.

        Fetches news, market status, and portfolio, then performs AI analysis
        and executes recommendations.
        """
        print(f"[{datetime.now()}] Running Startup Market Analysis...")

        # 1. Fetch News
        print("Fetching News...")
        news_summary = await self.news_fetcher.get_news_summary()

        # 2. Get Market Status
        market_status = await self.market_data.get_market_status()
        if not market_status.is_open:
            print("Market is currently CLOSED.")

        # 3. Get Portfolio Summary
        positions = await self.broker.get_positions()
        balance = await self.broker.get_account_balance()
        portfolio_summary = f"Balance: {balance}\nPositions: {positions}"

        await self.position_manager.display_portfolio(balance=balance)

        # 4. Local AI Analysis with Tools
        print("\nRunning Local AI Analysis with Tools...")
        try:
            analysis = await asyncio.wait_for(
                self.decision_engine.startup_analysis(
                    portfolio_summary=portfolio_summary,
                    market_status=str(market_status),
                    rss_news_summary=news_summary,
                    tools=self.tools
                ),
                timeout=60.0  # 60 second timeout for AI analysis
            )
        except asyncio.TimeoutError:
            print("AI Analysis timed out. Using fallback recommendations.")
            analysis = {
                "analysis_summary": "AI analysis timed out. No recommendations available.",
                "recommendations": []
            }
        except Exception as e:  # pylint: disable=broad-except
            print(f"Error during AI analysis: {e}")
            analysis = {
                "analysis_summary": f"Error during analysis: {str(e)}",
                "recommendations": []
            }

        print("\n" + "=" * 50)
        print(f"{'LOCAL AI ANALYSIS RESULT':^50}")
        print("=" * 50)
        print(json.dumps(analysis, indent=4))
        print("=" * 50 + "\n")

        # 5. Execute Recommendations with Remote Validation
        recommendations = analysis.get("recommendations", [])
        for rec in recommendations:
            try:
                if rec["action"] == "BUY" and rec["confidence"] > 0.8:
                    print(f"\nValidating BUY for {rec['symbol']} with Remote AI...")
                    
                    validation = await self.decision_engine.validate_with_remote_ai(
                        action=rec["action"],
                        symbol=rec["symbol"],
                        reasoning=rec["reasoning"],
                        confidence=rec["confidence"],
                        size_pct=rec.get("size_pct", 0.05)
                    )

                    print(f"Remote AI Validation: {validation['decision']}")
                    if validation["comments"]:
                        print(f"Comments: {validation['comments']}")

                    if validation["decision"] == "PROCEED":
                        await self._execute_buy(rec, validation, balance)
                    elif validation["decision"] == "MODIFY":
                        modified_rec = rec.copy()
                        modified_rec["confidence"] = validation.get("new_confidence", rec["confidence"])
                        modified_rec["size_pct"] = validation.get("new_size_pct", rec.get("size_pct", 0.05))
                        await self._execute_buy(modified_rec, validation, balance)
                    else:
                        print(f"REJECTED by Remote AI: {validation.get('comments', 'No reason provided')}")

            except Exception as e:  # pylint: disable=broad-except
                print(
                    f"Error processing recommendation for "
                    f"{rec.get('symbol', 'unknown')}: {e}"
                )

    async def run_monitoring_loop(self):
        """Run the monitoring loop for checking positions.

        Continuously monitors open positions and makes trading decisions.
        """
        print(
            f"[{datetime.now()}] Starting Monitoring Loop "
            f"(Interval: {self.settings.CHECK_INTERVAL_SECONDS}s)"
        )

        while True:
            try:
                # Get current positions from DB
                positions = await self.repo.get_positions()

                for position in positions:
                    try:
                        print(f"Checking position: {position.stock.symbol}")

                        # Fetch live data
                        quote = await self.market_data.get_quote(
                            position.stock.symbol
                        )
                        history = await self.market_data.get_historical(
                            position.stock.symbol, period="1mo"
                        )

                        # Pre-calculate simple technicals (can use pandas-ta here)
                        # For MVP, passing raw history string to AI
                        history_str = "\n".join([
                            f"{h.timestamp}: C={h.close} V={h.volume}"
                            for h in history[-20:]
                        ])

                        indicators = {
                            "rsi": 50,  # TODO: Calculate real RSI  # pylint: disable=fixme
                            "macd": 0,
                            "sma_20": sum(h.close for h in history[-20:]) / 20
                        }

                        volume_data = {
                            "current": quote.volume,
                            "average": sum(h.volume for h in history) / len(history)
                        }

                        decision = await self.decision_engine.intraday_check(
                            position=position,
                            price_history=history_str,
                            indicators=indicators,
                            volume_data=volume_data
                        )

                        print(f"--- Decision for {position.stock.symbol} ---")
                        print(json.dumps(decision, indent=4))
                        print("-" * (18 + len(position.stock.symbol)))

                        if (decision["action"] == "SELL" and
                                decision["confidence"] > 0.8):
                            print("\nValidating SELL with Remote AI...")
                            validation = await self.decision_engine.validate_with_remote_ai(
                                action="SELL",
                                symbol=position.stock.symbol,
                                reasoning=decision["reasoning"],
                                confidence=decision["confidence"],
                                size_pct=0.0
                            )

                            print(f"Remote AI Validation: {validation['decision']}")
                            if validation["decision"] == "PROCEED":
                                await self.broker.sell(
                                    position.stock.symbol, position.quantity, quote.price
                                )
                                new_balance = await self.broker.get_account_balance()
                                await self.position_manager.update_position(
                                    position.stock.symbol, position.quantity, quote.price,
                                    "SELL", balance=new_balance
                                )
                            else:
                                print(f"SELL REJECTED: {validation.get('comments', 'No reason')}")

                        # Small delay between positions to avoid rate limiting
                        await asyncio.sleep(2)

                    except Exception as pos_error:  # pylint: disable=broad-except
                        print(
                            f"Error checking position "
                            f"{position.stock.symbol}: {pos_error}"
                        )
                        await asyncio.sleep(5)  # Longer wait on error

            except Exception as e:  # pylint: disable=broad-except
                print(f"Error in monitoring loop: {e}")

            await asyncio.sleep(self.settings.CHECK_INTERVAL_SECONDS)
