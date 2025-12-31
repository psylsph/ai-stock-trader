"""Trading workflow orchestration for AI Stock Trader application."""

import asyncio
import json
from datetime import datetime
from typing import Dict, Any, List

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
from src.trading.prescreening import StockPrescreener


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
            model=settings.LM_STUDIO_MODEL.strip()
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
        
        self.prescreener = StockPrescreener()

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

        # 4. Prescreen FTSE 100 stocks
        print("\nPrescreening FTSE 100 stocks using technical indicators...")
        
        ftse100_tickers = [
            "III.L",    # 3i Group
            "ADM.L",    # Admiral Group
            "AAF.L",    # Airtel Africa
            "ALW.L",    # Alliance Witan
            "AAL.L",    # Anglo American
            "ANTO.L",   # Antofagasta
            "AHT.L",    # Ashtead Group
            "ABF.L",    # Associated British Foods
            "AZN.L",    # AstraZeneca
            "AUTO.L",   # Auto Trader Group
            "AV.L",     # Aviva
            "BA.L",     # BAE Systems
            "BARC.L",   # Barclays
            "BTRW.L",   # Barratt Redrow
            "BEZ.L",    # Beazley
            "BKG.L",    # Berkeley Group
            "BP.L",     # BP
            "BATS.L",   # British American Tobacco
            "BLND.L",   # British Land
            "BT-A.L",   # BT Group
            "BNZL.L",   # Bunzl
            "CNA.L",    # Centrica
            "CCH.L",    # Coca-Cola HBC
            "CPG.L",    # Compass Group
            "CTEC.L",   # Convatec
            "CRDA.L",   # Croda International
            "DCC.L",    # DCC
            "DGE.L",    # Diageo
            "DPLM.L",   # Diploma
            "EZJ.L",    # EasyJet
            "EDV.L",    # Endeavour Mining
            "ENT.L",    # Entain
            "EXPN.L",   # Experian
            "FCIT.L",   # F&C Investment Trust
            "FRES.L",   # Fresnillo
            "GAW.L",    # Games Workshop
            "GLEN.L",   # Glencore
            "GSK.L",    # GSK
            "HLN.L",    # Haleon
            "HLMA.L",   # Halma
            "HIK.L",    # Hikma Pharmaceuticals
            "HSX.L",    # Hiscox
            "HWDN.L",   # Howden Joinery
            "HSBA.L",   # HSBC
            "IMI.L",    # IMI
            "IMB.L",    # Imperial Brands
            "INF.L",    # Informa
            "IHG.L",    # Intercontinental Hotels
            "ICG.L",    # Intermediate Capital
            "ITRK.L",   # Intertek
            "IAG.L",    # IAG
            "JD.L",     # JD Sports
            "KGF.L",    # Kingfisher
            "LAND.L",   # Land Securities
            "LGEN.L",   # Legal & General
            "LLOY.L",   # Lloyds
            "LSEG.L",   # London Stock Exchange
            "LMP.L",    # Londonmetric
            "MNG.L",    # M&G
            "MKS.L",    # Marks & Spencer
            "MRO.L",    # Melrose
            "MNDI.L",   # Mondi
            "NG.L",     # National Grid
            "NWG.L",    # NatWest
            "NXT.L",    # Next
            "PSON.L",   # Pearson
            "PSH.L",    # Pershing Square
            "PSN.L",    # Persimmon
            "PHNX.L",   # Phoenix Group
            "PRU.L",    # Prudential
            "RKT.L",    # Reckitt
            "REL.L",    # RELX
            "RIO.L",    # Rio Tinto
            "RTO.L",    # Rentokil
            "RMV.L",    # Rightmove
            "RR.L",     # Rolls-Royce
            "SGE.L",    # Sage
            "SBRY.L",   # Sainsbury's
            "SDR.L",    # Schroders
            "SMT.L",    # Scottish Mortgage
            "SGRO.L",   # Segro
            "SVT.L",    # Severn Trent
            "SHEL.L",   # Shell
            "SN.L",     # Smith & Nephew
            "SMIN.L",   # Smiths Group
            "SPX.L",    # Spirax
            "SSE.L",    # SSE
            "STJ.L",    # St James's Place
            "STAN.L",   # Standard Chartered
            "TW.L",     # Taylor Wimpey
            "TSCO.L",   # Tesco
            "ULVR.L",   # Unilever
            "UTG.L",    # Unite Group
            "UU.L",     # United Utilities
            "VOD.L",    # Vodafone
            "WEIR.L",   # Weir Group
            "WTB.L",    # Whitbread
            "WPP.L"     # WPP
        ]
        
        print(f"Checking {len(ftse100_tickers)} FTSE 100 stocks...")
        
        prescreened_tickers = await self.prescreener.prescreen_stocks(
            ftse100_tickers,
            self.market_data
        )
        
        passed_count = sum(1 for v in prescreened_tickers.values() if v.get("passed", False))
        print(f"Prescreened {passed_count} / {len(ftse100_tickers)} stocks")

        # 5. Get targeted news for prescreened stocks
        print("\nFetching news for prescreened stocks...")
        filtered_news = await self._fetch_filtered_news(prescreened_tickers)

        # Create filtered news summary
        news_summary = self._create_filtered_news_summary(
            prescreened_tickers,
            filtered_news
        )

        # 6. Local AI Analysis on prescreened stocks with news
        print("\nRunning AI Analysis on Prescreened Stocks with News...")
        
        max_retries = self.settings.AI_MAX_RETRIES
        retry_delay = self.settings.AI_RETRY_DELAY_SECONDS
        analysis = {
            "analysis_summary": "Analysis incomplete",
            "recommendations": []
        }

        for attempt in range(max_retries):
            try:
                analysis = await self.decision_engine.startup_analysis_with_prescreening(
                    portfolio_summary=portfolio_summary,
                    market_status=str(market_status),
                    prescreened_tickers=prescreened_tickers,
                    rss_news_summary=news_summary,
                    tools=self.tools
                )
                break
            except Exception as e:
                if attempt < max_retries - 1:
                    delay = retry_delay * (attempt + 1)
                    print(f"  Analysis attempt {attempt + 1}/{max_retries} failed: {e}. Retrying in {delay}s...", end='', flush=True)
                    await asyncio.sleep(delay)
                else:
                    print(f"\nAll {max_retries} attempts failed. Using fallback.")
                    analysis = {
                        "analysis_summary": f"Error during analysis: {str(e)}",
                        "recommendations": []
                    }

        print("\n" + "=" * 50)
        print(f"{'LOCAL AI ANALYSIS RESULT':^50}")
        print("=" * 50)
        print(json.dumps(analysis, indent=4))
        print("=" * 50 + "\n")

        # 7. Execute Recommendations with Remote Validation
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

            except Exception as e:
                print(
                    f"Error processing recommendation for "
                    f"{rec.get('symbol', 'unknown')}: {e}"
                )

    async def _fetch_filtered_news(self, prescreened_tickers: Dict[str, Dict[str, Any]]) -> Dict[str, List[Dict]]:
        """Fetch news only for prescreened tickers."""
        filtered_news = {}
        
        for ticker, indicators in prescreened_tickers.items():
            if indicators.get("passed", False):
                try:
                    news = await self.yahoo_news_fetcher.get_ticker_news(ticker, limit=3)
                    if news:
                        filtered_news[ticker] = news
                except Exception:
                    pass
        
        return filtered_news
    
    def _create_filtered_news_summary(self, prescreened_tickers: Dict[str, Dict[str, Any]], filtered_news: Dict[str, List[Dict]]) -> str:
        """Create news summary focused on prescreened stocks."""
        if not filtered_news:
            return "No recent news available for prescreened stocks."
        
        summary = "News for Prescreened Stocks:\n"
        
        for ticker, news_items in filtered_news.items():
            for item in news_items:
                title = item.get("title", "No title")
                publisher = item.get("publisher", "Unknown")
                summary += f"\n{ticker}:\n  - [{publisher}] {title}\n"
        
        return summary

    async def run_monitoring_loop(self):
        """Run monitoring loop for checking positions.

        Continuously monitors open positions and makes trading decisions.
        """
        print(
            f"[{datetime.now()}] Starting Monitoring Loop "
            f"(Interval: {self.settings.CHECK_INTERVAL_SECONDS}s)"
        )

        while True:
            try:
                positions = await self.repo.get_positions()

                for position in positions:
                    try:
                        print(f"Checking position: {position.stock.symbol}")

                        quote = await self.market_data.get_quote(position.stock.symbol)
                        history = await self.market_data.get_historical(
                            position.stock.symbol, period="1mo"
                        )

                        history_str = "\n".join([
                            f"{h.timestamp}: C={h.close} V={h.volume}"
                            for h in history[-20:]
                        ])

                        indicators = {
                            "rsi": 50,
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
                        await asyncio.sleep(2)

                    except Exception as pos_error:
                        print(
                            f"Error checking position "
                            f"{position.stock.symbol}: {pos_error}"
                        )
                        await asyncio.sleep(5)

            except Exception as e:
                print(f"Error in monitoring loop: {e}")

            await asyncio.sleep(self.settings.CHECK_INTERVAL_SECONDS)
