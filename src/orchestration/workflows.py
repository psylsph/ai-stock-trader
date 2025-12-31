"""Trading workflow orchestration for AI Stock Trader application."""

import asyncio
import json
from datetime import datetime
from typing import Dict, Any, List

from src.config.settings import Settings
from src.database.repository import DatabaseRepository
from src.market.data_fetcher import YahooFinanceFetcher
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
from src.database.models import AIDecision
from src.config.web_mode_config import web_mode


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
        print("Using Yahoo Finance for market data")
        self.market_data = YahooFinanceFetcher()
        self.web_mode = web_mode.is_web_mode
        self.web_mode = False  # Track if web server is running

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
            self.local_ai,
            self.openrouter_client
        )

        self.broker = PaperTrader(repo, self.market_data, settings.INITIAL_BALANCE)
        self.position_manager = PositionManager(repo)
        self.risk_manager = RiskManager(
            max_position_pct=settings.MAX_POSITION_SIZE_PCT,
            max_positions=settings.MAX_POSITIONS
        )

        self.prescreener = StockPrescreener()
        self.last_full_portfolio_revaluation = datetime.min


    async def _execute_trade(self, rec: dict, validation: dict, balance: float) -> bool:
        """Execute a trade (BUY/SELL) after validation."""
        symbol = rec["symbol"]
        action = rec["action"]
        print(f"Fetching quote for {symbol}...")
        quote = await self.market_data.get_quote(symbol)
        current_price = quote.price

        if action == "BUY":
            size_pct = validation.get("new_size_pct", rec.get("size_pct", 0.05))
            
            # Calculate target quantity based on total portfolio value
            quantity = int((balance * size_pct) / current_price)
            
            # Cap quantity by available cash balance
            cash_balance = await self.broker.get_account_balance()
            max_qty_by_cash = int(cash_balance / current_price)
            if quantity > max_qty_by_cash:
                print(f"[DEBUG] Capping quantity for {symbol} from {quantity} to {max_qty_by_cash} due to cash limit ({cash_balance:.2f})")
                quantity = max_qty_by_cash

            print(f"[DEBUG] BUY calculation: balance={balance}, cash={cash_balance}, size_pct={size_pct}, price={current_price}, quantity={quantity}")

            if quantity > 0:
                current_positions = await self.broker.get_positions()
                
                # Check if we already have a position in this stock
                existing_pos = next((p for p in current_positions if p["symbol"] == symbol), None)
                current_pos_size = (existing_pos["quantity"] * current_price) if existing_pos else 0.0
                
                # If it's a new stock, count it as an additional position
                num_positions = len(current_positions)
                if not existing_pos:
                    num_positions += 1

                print(f"[DEBUG] Risk Check: symbol={symbol}, quantity={quantity}, price={current_price}, portfolio_val={balance}, pos_size={current_pos_size}, num_pos={num_positions}")
                if self.risk_manager.validate_trade(
                    action="BUY",
                    quantity=quantity,
                    price=current_price,
                    total_portfolio_value=balance,
                    current_position_size=current_pos_size,
                    num_current_positions=num_positions
                ):
                    print(f"Executing BUY for {symbol}: {quantity} shares @ £{current_price:.2f}")
                    await self.broker.buy(symbol, quantity, current_price)
                    new_balance = await self.broker.get_account_balance()
                    await self.position_manager.update_position(
                        symbol, quantity, current_price, "BUY", balance=new_balance
                    )
                    return True
                print(f"Risk Manager REJECTED buy for {symbol}: Potential position size/count limit exceeded.")
                return False
        
        elif action == "SELL":
            current_positions = await self.broker.get_positions()
            existing_pos = next((p for p in current_positions if p["symbol"] == symbol), None)
            
            if not existing_pos:
                print(f"Error: Cannot sell {symbol}, no position found.")
                return False
                
            quantity = existing_pos["quantity"]
            print(f"Executing SELL for {symbol}: {quantity} shares @ £{current_price:.2f}")
            await self.broker.sell(symbol, quantity, current_price)
            new_balance = await self.broker.get_account_balance()
            await self.position_manager.update_position(
                symbol, quantity, current_price, "SELL", balance=new_balance
            )
            return True

        return False

    def _select_top_technical_picks(self, prescreened_tickers: Dict[str, Dict[str, Any]], limit: int = 10) -> Dict[str, Dict[str, Any]]:
        """Sort prescreened stocks by technical score and return top N."""
        scored_stocks = []
        for ticker, indicators in prescreened_tickers.items():
            if indicators.get("passed", False):
                score = self.prescreener.score_stock(indicators)
                scored_stocks.append((ticker, score, indicators))
        
        # Sort by score descending
        scored_stocks.sort(key=lambda x: x[1], reverse=True)
        return {ticker: indicators for ticker, score, indicators in scored_stocks[:limit]}

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

        # 5. Sort and filter top 10 stocks based on technical score
        print("\nSelecting top 10 stocks based on technical indicators...")
        top_10_stocks = self._select_top_technical_picks(prescreened_tickers, limit=10)
        
        if top_10_stocks:
            print(f"Selected: {', '.join(top_10_stocks.keys())}")
        else:
            print("No stocks passed technical prescreening.")

        # 6. Get targeted news for top 10 stocks
        print("\nFetching news for top 10 technical picks...")
        filtered_news = await self._fetch_filtered_news(top_10_stocks)

        # Create filtered news summary
        news_summary = self._create_filtered_news_summary(
            top_10_stocks,
            filtered_news
        )

        # 7. Local AI Analysis on top 10 stocks with news
        print("\nRunning AI Analysis on Top 10 Technical Picks with News...")

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
                    prescreened_tickers=top_10_stocks,
                    rss_news_summary=news_summary,
                    tools=self.tools
                )
                break
            except Exception as e:
                if attempt < max_retries - 1:
                    delay = retry_delay * (attempt + 1)
                    msg = (f"  Analysis attempt {attempt + 1}/{max_retries} failed: {e}. "
                           f"Retrying in {delay}s...",)
                    print(msg, end='', flush=True)
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
        active_symbols = {p["symbol"] for p in positions}

        for rec in recommendations:
            try:
                symbol = rec["symbol"]
                action = rec["action"]
                
                # Re-fetch balance to ensure sequential trades respect previous ones
                balance = await self.broker.get_account_balance()

                # Ignore HOLD or SELL recommendations for stocks we don't own
                if action in ["HOLD", "SELL"] and symbol not in active_symbols:
                    print(f"Ignoring {action} for {symbol} (not in active positions)")
                    continue

                # Ignore low confidence recommendations
                if action in ["BUY", "SELL"] and rec["confidence"] < 0.8:
                    print(f"Ignoring low-confidence {action} for {symbol} ({rec['confidence']})")
                    continue

                # Log local decision
                local_decision_record = AIDecision(
                    ai_type="local",
                    symbol=symbol,
                    context={"rec": rec},
                    response=analysis,
                    decision=action,
                    confidence=rec["confidence"],
                    requires_manual_review=self.settings.TRADING_MODE == "live" and not self.settings.IGNORE_MARKET_HOURS
                )
                await self.repo.log_decision(local_decision_record)

                if rec["action"] in ["BUY", "SELL"]:
                    print(f"\nValidating {rec['action']} for {rec['symbol']} with Remote AI...")

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

                    # Update decision with validation results
                    await self.repo.update_decision_with_validation(
                        symbol=rec["symbol"],
                        remote_validation_decision=validation["decision"],
                        remote_validation_comments=validation.get("comments", ""),
                        requires_manual_review=self.settings.TRADING_MODE == "live" and validation["decision"] == "PROCEED" and not self.settings.IGNORE_MARKET_HOURS
                    )

                    if validation["decision"] in ["PROCEED", "MODIFY"]:
                        target_rec = rec
                        if validation["decision"] == "MODIFY":
                            target_rec = rec.copy()
                            target_rec["confidence"] = validation.get("new_confidence", rec["confidence"])
                            target_rec["size_pct"] = validation.get("new_size_pct", rec.get("size_pct", 0.05))

                        if target_rec["confidence"] < 0.8:
                            print(f"Validation rejection for {rec['symbol']}: Confidence {target_rec['confidence']} < 0.8")
                            continue

                        if market_status.is_open or self.settings.IGNORE_MARKET_HOURS:
                            # Re-fetch balance and positions for latest portfolio state
                            current_balance = await self.broker.get_account_balance()
                            current_positions = await self.broker.get_positions()
                            
                            # Calculate total portfolio value for risk management
                            total_value = current_balance
                            for p in current_positions:
                                p_quote = await self.market_data.get_quote(p["symbol"])
                                total_value += p["quantity"] * p_quote.price

                            success = await self._execute_trade(target_rec, validation, total_value)
                            if success:
                                await self.repo.mark_decision_executed(rec["symbol"])
                        else:
                            print(f"Market CLOSED: Recommendation for {rec['symbol']} will be held as PLANNED.")
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

    def _create_filtered_news_summary(
        self,
        prescreened_tickers: Dict[str, Dict[str, Any]],
        filtered_news: Dict[str, List[Dict]]
    ) -> str:
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

    async def _execute_pending_trades(self):
        """Check for and execute any pending trade decisions."""
        pending = await self.repo.get_pending_executions()
        if not pending:
            return

        print(f"Found {len(pending)} pending trades to execute...")
        
        for decision in pending:
            try:
                # Re-fetch balance and positions for latest portfolio state
                current_balance = await self.broker.get_account_balance()
                current_positions = await self.broker.get_positions()
                
                # Calculate total portfolio value for risk management
                total_value = current_balance
                for p in current_positions:
                    p_quote = await self.market_data.get_quote(p["symbol"])
                    total_value += p["quantity"] * p_quote.price

                # Reconstruct rec and validation from decision context
                rec = decision.context.get("rec") if decision.context else None
                if not rec:
                    continue
                
                validation = {
                    "decision": decision.remote_validation_decision,
                    "comments": decision.remote_validation_comments,
                }
                
                # Check if it was a MODIFY decision and apply changes
                if decision.remote_validation_decision == "MODIFY":
                    # In MODIFY cases, target_rec should have the modified values.
                    pass

                success = await self._execute_trade(rec, validation, total_value)
                if success:
                    await self.repo.mark_decision_executed(decision.symbol)

            except Exception as e:
                print(f"Error executing pending trade for {decision.symbol}: {e}")

    async def _perform_full_portfolio_revaluation(self):
        """Perform deep analysis on all open positions using Local and Remote AI."""
        positions = await self.repo.get_positions()
        if not positions:
            print("No active positions to revaluate.")
            return

        print(f"Revaluating {len(positions)} active positions...")
        for position in positions:
            try:
                print(f"\n[Revaluation] Analyzing {position.stock.symbol}...")
                
                # 1. Fetch deep context
                quote = await self.market_data.get_quote(position.stock.symbol)
                history = await self.market_data.get_historical(position.stock.symbol, period="1mo")
                prices = [h.close for h in history]
                history_str = "\n".join([f"{h.timestamp}: C={h.close} V={h.volume}" for h in history[-20:]])
                
                # Indicators for AI
                rsi = self.prescreener.calculate_rsi(prices)
                macd, signal = self.prescreener.calculate_macd(prices)
                sma_20 = self.prescreener.calculate_sma(prices, 20)
                sma_50 = self.prescreener.calculate_sma(prices, 50)
                
                indicators = {
                    "rsi": rsi,
                    "macd": macd,
                    "signal": signal,
                    "sma_20": sma_20,
                    "sma_50": sma_50
                }
                
                # 2. Local AI Intraday Check
                decision = await self.decision_engine.intraday_check(
                    position=position,
                    price_history=history_str,
                    indicators=indicators,
                    volume_data={"current": quote.volume, "average": sum(h.volume for h in history)/len(history)}
                )
                
                # 3. Always escalate to Remote AI for hourly revaluation if any action suggested or for health check
                print(f"Escalating {position.stock.symbol} to Remote AI for hourly validation...")
                validation = await self.decision_engine.validate_with_remote_ai(
                    action=decision["action"],
                    symbol=position.stock.symbol,
                    reasoning=f"Hourly Revaluation. Local AI suggests: {decision['action']}. Reasoning: {decision['reasoning']}",
                    confidence=decision["confidence"],
                    size_pct=0.0 # Not a new buy
                )
                
                print(f"Remote AI Revaluation Decision: {validation['decision']} ({validation.get('comments', '')})")
                
                # 4. Act on remote decision
                if validation["decision"] == "PROCEED" and decision["action"] == "SELL":
                    print(f"Hourly Revaluation: Executing SELL for {position.stock.symbol}")
                    await self._execute_trade(
                        {"symbol": position.stock.symbol, "action": "SELL"},
                        validation,
                        0.0
                    )
                elif validation["decision"] == "MODIFY" and validation.get("new_action") == "SELL":
                    print(f"Hourly Revaluation: Remote AI OVERRIDE to SELL for {position.stock.symbol}")
                    await self._execute_trade(
                        {"symbol": position.stock.symbol, "action": "SELL"},
                        validation,
                        0.0
                    )
                
            except Exception as e:
                print(f"Error during revaluation of {position.stock.symbol}: {e}")

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
                # 1. Check for pending executions (e.g. from closed market)
                market_status = await self.market_data.get_market_status()
                if market_status.is_open or self.settings.IGNORE_MARKET_HOURS:
                    await self._execute_pending_trades()

                # 2. Check if it's time for hourly full portfolio revaluation
                now = datetime.now()
                if (now - self.last_full_portfolio_revaluation).total_seconds() >= 3600:
                    print(f"[{now}] Starting hourly full portfolio revaluation...")
                    await self._perform_full_portfolio_revaluation()
                    self.last_full_portfolio_revaluation = now

                # 3. Monitor existing positions (regular interval)
                positions = await self.repo.get_positions()

                for position in positions:
                    try:
                        print(f"Checking position: {position.stock.symbol}")

                        quote = await self.market_data.get_quote(position.stock.symbol)
                        history = await self.market_data.get_historical(
                            position.stock.symbol, period="1mo"
                        )
                        prices = [h.close for h in history]

                        # Calculate real indicators using prescreener logic
                        rsi = self.prescreener.calculate_rsi(prices)
                        macd, signal = self.prescreener.calculate_macd(prices)
                        sma_20 = self.prescreener.calculate_sma(prices, 20)
                        sma_50 = self.prescreener.calculate_sma(prices, 50)
                        
                        history_str = "\n".join([
                            f"{h.timestamp}: C={h.close} V={h.volume}"
                            for h in history[-20:]
                        ])

                        indicators = {
                            "rsi": rsi,
                            "macd": macd,
                            "signal": signal,
                            "sma_20": sma_20,
                            "sma_50": sma_50
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

                        # Log decision
                        final_action = decision["action"]
                        if final_action == "SELL" and decision["confidence"] < 0.8:
                            # Downgrade low-confidence SELL to HOLD for logging
                            final_action = "HOLD"

                        if final_action == "HOLD" and position.stock.symbol not in {p.stock.symbol for p in positions}:
                            continue

                        monitoring_decision = AIDecision(
                            ai_type="local",
                            symbol=position.stock.symbol,
                            context={"position_id": position.id, "indicators": indicators},
                            response=decision,
                            decision=final_action,
                            confidence=decision["confidence"],
                            requires_manual_review=self.settings.TRADING_MODE == "live" and final_action == "SELL" and not self.settings.IGNORE_MARKET_HOURS
                        )
                        await self.repo.log_decision(monitoring_decision)

                        print(f"--- Decision for {position.stock.symbol} ---")
                        print(json.dumps(decision, indent=4))
                        print("-" * (18 + len(position.stock.symbol)))

                        if (decision["action"] == "SELL" and
                                decision["confidence"] >= 0.8):
                            # Check market status before selling
                            market_status = await self.market_data.get_market_status()
                            if not (market_status.is_open or self.settings.IGNORE_MARKET_HOURS):
                                print(f"Market CLOSED: Delaying SELL for {position.stock.symbol}")
                                continue

                            print("\nValidating SELL with Remote AI...")
                            validation = await self.decision_engine.validate_with_remote_ai(
                                action="SELL",
                                symbol=position.stock.symbol,
                                reasoning=decision["reasoning"],
                                confidence=decision["confidence"],
                                size_pct=0.0
                            )

                            print(f"Remote AI Validation: {validation['decision']}")

                            # Update decision with validation results
                            await self.repo.update_decision_with_validation(
                                symbol=position.stock.symbol,
                                remote_validation_decision=validation["decision"],
                                remote_validation_comments=validation.get("comments", ""),
                                requires_manual_review=self.settings.TRADING_MODE == "live" and validation["decision"] == "PROCEED" and not self.settings.IGNORE_MARKET_HOURS
                            )

                            if validation["decision"] in ["PROCEED", "MODIFY"]:
                                final_confidence = validation.get("new_confidence", decision["confidence"])
                                if final_confidence < 0.8:
                                    print(f"SELL aborted for {position.stock.symbol}: Validation confidence {final_confidence} < 0.8")
                                    continue

                                # Reconstruct rec for _execute_trade
                                sell_rec = {
                                    "symbol": position.stock.symbol,
                                    "action": "SELL",
                                    "confidence": final_confidence,
                                    "reasoning": decision["reasoning"]
                                }
                                
                                # Re-fetch balance and positions for latest portfolio state
                                current_balance = await self.broker.get_account_balance()
                                current_positions = await self.broker.get_positions()
                                
                                # Calculate total portfolio value for risk management
                                total_value = current_balance
                                for p in current_positions:
                                    p_quote = await self.market_data.get_quote(p["symbol"])
                                    total_value += p["quantity"] * p_quote.price

                                success = await self._execute_trade(sell_rec, validation, balance=total_value)
                                if success:
                                    await self.repo.mark_decision_executed(position.stock.symbol)
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
