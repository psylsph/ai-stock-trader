import asyncio
import schedule
import json
from datetime import datetime
from typing import List
from src.config import Settings
from src.database.repository import DatabaseRepository
from src.market.data_fetcher import MarketDataFetcher, AlphaVantageFetcher, YahooFinanceFetcher
from src.ai.ollama_client import OllamaClient
from src.ai.openrouter_client import OpenRouterClient
from src.ai.decision_engine import TradingDecisionEngine
from src.trading.paper_trader import PaperTrader
from src.trading.managers import PositionManager, RiskManager
from src.market.news_fetcher import NewsFetcher

class TradingWorkflow:
    def __init__(self, settings: Settings, repo: DatabaseRepository):
        self.settings = settings
        self.repo = repo
        
        # Initialize Components
        if not settings.MARKET_DATA_API_KEY or settings.MARKET_DATA_API_KEY == "yahoo":
             print("Using Yahoo Finance for market data (no API key required/provided)")
             self.market_data = YahooFinanceFetcher()
        else:
             self.market_data = AlphaVantageFetcher(settings.MARKET_DATA_API_KEY)
        self.news_fetcher = NewsFetcher(settings.RSS_FEEDS)
        
        self.ollama_client = OllamaClient(settings.OLLAMA_HOST, settings.OLLAMA_MODEL)
        self.openrouter_client = OpenRouterClient(settings.OPENROUTER_API_KEY, settings.OPENROUTER_MODEL)
        self.decision_engine = TradingDecisionEngine(self.ollama_client, self.openrouter_client)
        
        self.broker = PaperTrader(repo, self.market_data, settings.INITIAL_BALANCE)
        self.position_manager = PositionManager(repo)
        self.risk_manager = RiskManager()

    async def run_startup_analysis(self):
        print(f"[{datetime.now()}] Running Startup Market Analysis...")
        
        # 1. Fetch News
        print("Fetching News...")
        news_summary = await self.news_fetcher.get_news_summary()
        
        # 2. Get Market Status
        market_status = await self.market_data.get_market_status()
        if not market_status.is_open:
            print("Market is currently CLOSED.")
            # We might still run analysis if allowed
        
        # 3. Get Portfolio Summary
        positions = await self.broker.get_positions()
        balance = await self.broker.get_account_balance()
        portfolio_summary = f"Balance: {balance}\nPositions: {positions}"
        
        # Display initial portfolio
        await self.position_manager.display_portfolio(balance=balance)
        
        # 4. AI Analysis
        analysis = await self.decision_engine.startup_analysis(
            portfolio_summary=portfolio_summary,
            market_status=str(market_status),
            news_summary=news_summary
        )
        
        print("\n" + "="*50)
        print(f"{'AI MARKET ANALYSIS RESULT':^50}")
        print("="*50)
        print(json.dumps(analysis, indent=4))
        print("="*50 + "\n")
        
        # 4. Execute Recommendations (Simplified)
        recommendations = analysis.get("recommendations", [])
        for rec in recommendations:
            try:
                if rec["action"] == "BUY" and rec["confidence"] > 0.8:
                    symbol = rec["symbol"]
                    # Calculate size based on rec["size_pct"] or risk manager
                    # For demo: Fixed small size or calculated
                    print(f"Fetching quote for {symbol}...")
                    quote = await self.market_data.get_quote(symbol)
                    current_price = quote.price
                    quantity = int((balance * rec.get("size_pct", 0.05)) / current_price)
                    
                    if quantity > 0:
                        if self.risk_manager.validate_trade("BUY", quantity, current_price, balance):
                             print(f"Executing BUY for {symbol}")
                             await self.broker.buy(symbol, quantity, current_price)
                             # Pass updated balance
                             new_balance = await self.broker.get_account_balance()
                             await self.position_manager.update_position(symbol, quantity, current_price, "BUY", balance=new_balance)
            except Exception as e:
                print(f"Error executing recommendation for {rec.get('symbol', 'unknown')}: {e}")

    async def run_monitoring_loop(self):
        print(f"[{datetime.now()}] Starting Monitoring Loop (Interval: {self.settings.CHECK_INTERVAL_SECONDS}s)")
        
        while True:
            try:
                # Get current positions from DB
                positions = await self.repo.get_positions()
                
                for position in positions:
                    try:
                        print(f"Checking position: {position.stock.symbol}")
                        
                        # Fetch live data
                        quote = await self.market_data.get_quote(position.stock.symbol)
                        history = await self.market_data.get_historical(position.stock.symbol, period="1mo")
                        
                        # Pre-calculate simple technicals (can use pandas-ta here)
                        # For MVP, passing raw history string to AI
                        history_str = "\n".join([f"{h.timestamp}: C={h.close} V={h.volume}" for h in history[-20:]])
                        
                        indicators = {
                            "rsi": 50, # TODO: Calculate real RSI
                            "macd": 0,
                             "sma_20": sum([h.close for h in history[-20:]])/20
                        }
                        
                        volume_data = {
                            "current": quote.volume,
                            "average": sum([h.volume for h in history])/len(history)
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
                        
                        if decision["action"] == "SELL" and decision["confidence"] > 0.8:
                            await self.broker.sell(position.stock.symbol, position.quantity, quote.price)
                            new_balance = await self.broker.get_account_balance()
                            await self.position_manager.update_position(position.stock.symbol, position.quantity, quote.price, "SELL", balance=new_balance)
                        
                        # Small delay between positions to avoid rate limiting
                        await asyncio.sleep(2)
                        
                    except Exception as pos_error:
                        print(f"Error checking position {position.stock.symbol}: {pos_error}")
                        await asyncio.sleep(5) # Longer wait on error
                        
            except Exception as e:
                print(f"Error in monitoring loop: {e}")
            
            await asyncio.sleep(self.settings.CHECK_INTERVAL_SECONDS)
