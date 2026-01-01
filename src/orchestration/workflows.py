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
        print(f"[DEBUG] _execute_trade called: symbol={symbol}, action={action}, balance={balance}")
        print(f"Fetching quote for {symbol}...")
        quote = await self.market_data.get_quote(symbol)
        current_price = quote.price

        if current_price is None or current_price == 0:
            print(f"Error: No valid price available for {symbol}. Skipping trade.")
            return False

        if action == "BUY":
            size_pct = validation.get("new_size_pct", rec.get("size_pct", 0.05))
            
            # Calculate target quantity based on available cash
            cash_balance = await self.broker.get_account_balance()
            target_amount = cash_balance * size_pct
            quantity = int(target_amount / current_price)
            
            # If we can't buy even 1 share at target allocation, buy 1 share if affordable
            # This ensures we participate in trades even with small allocations
            if quantity == 0:
                if cash_balance >= current_price:
                    quantity = 1
                    print(f"[DEBUG] Adjusted: Buying 1 share (target allocation too small for price {current_price})")
                else:
                    print(f"[DEBUG] Cannot afford {symbol} at price {current_price} with cash {cash_balance}")
            
            print(f"[DEBUG] BUY calculation: cash={cash_balance}, size_pct={size_pct}, target_amount={target_amount:.2f}, price={current_price}, quantity={quantity}")

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

    def _apply_validation_rules(self, action: str, confidence: float) -> Dict[str, Any]:
        """Apply hard-coded validation rules instead of AI.

        Uses deterministic rules for validation decisions instead of calling remote AI.
        This ensures consistent validation results.

        Args:
            action: The proposed action (BUY/SELL/HOLD)
            confidence: The AI's confidence score (0.0-1.0)

        Returns:
            Validation decision dict with decision, comments, new_confidence, and new_size_pct.
        """
        if action == "HOLD":
            return {
                "decision": "PROCEED",
                "comments": "HOLD - no action required",
                "new_confidence": confidence,
                "new_size_pct": None
            }

        if confidence >= 0.8:
            return {
                "decision": "PROCEED",
                "comments": "High confidence - approved via rules",
                "new_confidence": confidence,
                "new_size_pct": None
            }
        elif confidence >= 0.6:
            # Reduce position size by 50% for moderate confidence
            return {
                "decision": "MODIFY",
                "comments": "Moderate confidence - size reduced via rules",
                "new_confidence": confidence,
                "new_size_pct": 0.05  # Half of default 10%
            }
        else:
            return {
                "decision": "REJECT",
                "comments": "Low confidence - rejected via rules",
                "new_confidence": confidence,
                "new_size_pct": None
            }

    def _is_ticker(self, value: str) -> bool:
        """Check if value looks like a stock ticker (contains letters and .L or similar)."""
        return bool(value.replace(".", "").isalpha())

    def _get_prescreen_limit(self, prescreened_tickers: Dict[str, Dict[str, Any]]) -> tuple[int | None, str]:
        """Parse MAX_PRESCREENED_STOCKS setting and return (limit, description).
        
        Returns:
            tuple of (limit_or_None, description_string)
            - If numeric: returns (int, "N stocks")
            - If ticker: returns (None, "stocks above TICKER")
        """
        value = str(self.settings.MAX_PRESCREENED_STOCKS).strip()
        
        if self._is_ticker(value):
            return None, f"stocks above {value}"
        else:
            try:
                return int(value), f"top {value} stocks"
            except ValueError:
                print(f"[WARNING] Invalid MAX_PRESCREENED_STOCKS value: {value}, defaulting to 10")
                return 10, "top 10 stocks"

    def _select_top_technical_picks(
        self, 
        prescreened_tickers: Dict[str, Dict[str, Any]], 
        limit: int | None = None,
        cutoff_ticker: str | None = None
    ) -> Dict[str, Dict[str, Any]]:
        """Sort ALL prescreened stocks by technical score and return based on limit type.
        
        Unlike other methods, this scores ALL stocks first (not just passed ones),
        then applies the cutoff. This ensures the cutoff ticker is always found.
        
        Args:
            prescreened_tickers: Dict of ticker to indicator results
            limit: If set, return top N stocks
            cutoff_ticker: If set, return all stocks scoring >= this ticker
        """
        # Score ALL stocks first (not just passed ones)
        scored_stocks = []
        for ticker, indicators in prescreened_tickers.items():
            score = self.prescreener.score_stock(indicators)
            scored_stocks.append((ticker, score, indicators))
        
        # Sort by score descending
        scored_stocks.sort(key=lambda x: x[1], reverse=True)
        
        if cutoff_ticker:
            # Find the cutoff ticker's score - search in ALL stocks
            cutoff_score = None
            
            if cutoff_ticker in prescreened_tickers:
                indicators = prescreened_tickers[cutoff_ticker]
                cutoff_score = self.prescreener.score_stock(indicators)
            
            if cutoff_score is None:
                print(f"[WARNING] Cutoff ticker {cutoff_ticker} not found, using default of 10")
                return {ticker: indicators for ticker, score, indicators in scored_stocks[:10]}
            
            print(f"[DEBUG] Cutoff ticker {cutoff_ticker} has score {cutoff_score}")
            
            # Return ALL stocks (passed or not) with score >= cutoff_score
            selected = [(t, s, ind) for t, s, ind in scored_stocks if s >= cutoff_score]
            selected.sort(key=lambda x: x[1], reverse=True)
            return {ticker: indicators for ticker, score, indicators in selected}
        elif limit:
            # Return top N by score (all passed stocks since they have scores)
            # But filter to only include passed ones for AI analysis
            passed_stocks = [(t, s, ind) for t, s, ind in scored_stocks if ind.get("passed", False)]
            return {ticker: indicators for ticker, score, indicators in passed_stocks[:limit]}
        else:
            # Return all (filter to passed ones only)
            passed_stocks = [(t, s, ind) for t, s, ind in scored_stocks if ind.get("passed", False)]
            return {ticker: indicators for ticker, score, indicators in passed_stocks}

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
        print(f"[DEBUG] Market status: is_open={market_status.is_open}, IGNORE_MARKET_HOURS={self.settings.IGNORE_MARKET_HOURS}")
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

        max_stocks, limit_desc = self._get_prescreen_limit(prescreened_tickers)
        print(f"\nSelecting {limit_desc} based on technical indicators...")
        
        # Determine if we're using numeric limit or ticker cutoff
        if max_stocks is not None:
            top_stocks = self._select_top_technical_picks(prescreened_tickers, limit=max_stocks)
        else:
            # Parse the ticker from the description
            cutoff_ticker = str(self.settings.MAX_PRESCREENED_STOCKS).strip()
            top_stocks = self._select_top_technical_picks(prescreened_tickers, cutoff_ticker=cutoff_ticker)
        
        if top_stocks:
            print(f"Selected: {', '.join(top_stocks.keys())}")
        else:
            print("No stocks passed technical prescreening.")

        # 6. Get targeted news for top stocks
        print(f"\nFetching news for {limit_desc}...")
        if top_stocks:
            filtered_news = await self._fetch_filtered_news(top_stocks)
        else:
            filtered_news = {}

        # Create filtered news summary
        news_summary = self._create_filtered_news_summary(
            top_stocks,
            filtered_news
        )

        # 7. Local AI Analysis on top stocks with news
        print(f"\nRunning AI Analysis on {limit_desc} with News...")

        max_retries = self.settings.AI_MAX_RETRIES
        retry_delay = self.settings.AI_RETRY_DELAY_SECONDS
        analysis = {
            "analysis_summary": "Analysis incomplete",
            "recommendations": []
        }

        if self.settings.REMOTE_ONLY_MODE:
            print("REMOTE_ONLY_MODE enabled - skipping local AI analysis")
            analysis = {
                "analysis_summary": "Remote-only mode: Skipped local AI analysis",
                "recommendations": []
            }
        else:
            for attempt in range(max_retries):
                try:
                    analysis = await self.decision_engine.startup_analysis_with_prescreening(
                        portfolio_summary=portfolio_summary,
                        market_status=str(market_status),
                        prescreened_tickers=top_stocks,
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

        # 7a. If no BUY recommendations, ask remote AI
        recommendations = analysis.get("recommendations", [])
        buy_recommendations = [rec for rec in recommendations if rec.get("action") == "BUY" and rec.get("confidence", 0) >= 0.8]

        if not buy_recommendations:
            print("No BUY recommendations from local AI (with >= 80% confidence). Querying remote AI...")
            try:
                remote_analysis = await self.decision_engine.request_remote_recommendations(
                    portfolio_summary=portfolio_summary,
                    market_status=str(market_status),
                    prescreened_tickers=top_stocks,
                    rss_news_summary=news_summary
                )
                print("\n" + "=" * 50)
                print(f"{'REMOTE AI ANALYSIS RESULT':^50}")
                print("=" * 50)
                print(json.dumps(remote_analysis, indent=4))
                print("=" * 50 + "\n")

                remote_recommendations = remote_analysis.get("recommendations", [])
                if remote_recommendations:
                    # Mark recommendations as from_remote so they skip validation
                    for rec in remote_recommendations:
                        rec["from_remote"] = True
                    # Merge remote recommendations into local analysis
                    recommendations = recommendations + remote_recommendations
                    analysis["recommendations"] = recommendations
                    print(f"Added {len(remote_recommendations)} remote recommendations")

                    # Re-check for BUY recommendations after adding remote ones
                    buy_recommendations = [rec for rec in recommendations if rec.get("action") == "BUY" and rec.get("confidence", 0) >= 0.8]
                    print(f"Total BUY recommendations after remote merge: {len(buy_recommendations)}")
            except Exception as e:
                print(f"Failed to get remote recommendations: {e}")

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

                # Skip BUY if already bought today (BUY once per day rule)
                if action == "BUY" and await self.repo.was_bought_today(symbol):
                    print(f"Ignoring BUY for {symbol} (already bought today)")
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

                # For HOLD decisions on existing positions, mark as completed immediately
                if action == "HOLD":
                    await self.repo.update_decision_with_validation(
                        symbol=symbol,
                        remote_validation_decision="PROCEED",
                        remote_validation_comments="HOLD - no action required",
                        requires_manual_review=False
                    )
                    continue

                # Skip validation for recommendations already from remote AI
                if rec.get("from_remote"):
                    print(f"\nRemote AI recommendation: {rec['action']} for {rec['symbol']} (skipping additional validation)")
                    validation = {"decision": "PROCEED", "comments": "From remote AI - already validated"}

                    # Log validation results for remote AI recommendations
                    await self.repo.update_decision_with_validation(
                        symbol=rec["symbol"],
                        remote_validation_decision="PROCEED",
                        remote_validation_comments="From remote AI - already validated",
                        requires_manual_review=self.settings.TRADING_MODE == "live" and not self.settings.IGNORE_MARKET_HOURS,
                        new_confidence=rec.get("confidence")
                    )

                    if market_status.is_open or self.settings.IGNORE_MARKET_HOURS:
                        print(f"[DEBUG] Market open={market_status.is_open}, IGNORE_MARKET_HOURS={self.settings.IGNORE_MARKET_HOURS} - proceeding with trade")
                        # Re-fetch balance and positions for latest portfolio state
                        current_balance = await self.broker.get_account_balance()
                        current_positions = await self.broker.get_positions()

                        # Calculate total portfolio value for risk management
                        total_value = current_balance
                        for p in current_positions:
                            p_quote = await self.market_data.get_quote(p["symbol"])
                            if p_quote and p_quote.price:
                                total_value += p["quantity"] * p_quote.price

                        print(f"[DEBUG] Executing trade: balance={current_balance}, total_value={total_value}")
                        success = await self._execute_trade(rec, validation, total_value)
                        print(f"[DEBUG] Trade execution result: success={success}")
                        if success:
                            await self.repo.mark_decision_executed(rec["symbol"])
                    else:
                        print(f"Market CLOSED: Recommendation for {rec['symbol']} will be held as PLANNED.")
                        # Set manual review requirements for pending decision when market is closed
                        await self.repo.update_decision_with_validation(
                            symbol=rec["symbol"],
                            remote_validation_decision="PROCEED",
                            remote_validation_comments="Market closed - pending execution when market opens",
                            requires_manual_review=self.settings.TRADING_MODE == "live",
                            new_confidence=rec.get("confidence")
                        )

                elif rec["action"] in ["BUY", "SELL"]:
                    print(f"\nValidating {rec['action']} for {rec['symbol']} with remote AI...")

                    # Get reasoning from the recommendation
                    reasoning = rec.get("reasoning", "No reasoning provided")
                    size_pct = rec.get("size_pct", 0.05)

                    # Validate with remote AI instead of rule-based validation
                    validation = await self.decision_engine.validate_with_remote_ai(
                        action=rec["action"],
                        symbol=rec["symbol"],
                        reasoning=reasoning,
                        confidence=rec["confidence"],
                        size_pct=size_pct
                    )

                    print(f"Remote AI Validation: {validation['decision']} - {validation.get('comments', '')}")

                    # Update decision with validation results
                    await self.repo.update_decision_with_validation(
                        symbol=rec["symbol"],
                        remote_validation_decision=validation["decision"],
                        remote_validation_comments=validation.get("comments", ""),
                        requires_manual_review=self.settings.TRADING_MODE == "live" and validation["decision"] == "PROCEED" and not self.settings.IGNORE_MARKET_HOURS,
                        new_confidence=validation.get("new_confidence", rec["confidence"])
                    )

                    if validation["decision"] in ["PROCEED", "MODIFY"]:
                        target_rec = rec
                        if validation["decision"] == "MODIFY":
                            target_rec = rec.copy()
                            target_rec["confidence"] = validation.get("new_confidence", rec["confidence"])
                            target_rec["size_pct"] = validation.get("new_size_pct", rec.get("size_pct", 0.05))

                        if target_rec["confidence"] < 0.8:
                            print(f"Validation rejection for {rec['symbol']}: Confidence {target_rec['confidence']} < 0.8")
                            await self.repo.mark_decision_executed(rec["symbol"])
                            continue

                        if market_status.is_open or self.settings.IGNORE_MARKET_HOURS:
                            print(f"[DEBUG] Market open={market_status.is_open}, IGNORE_MARKET_HOURS={self.settings.IGNORE_MARKET_HOURS} - proceeding with trade")
                            # Re-fetch balance and positions for latest portfolio state
                            current_balance = await self.broker.get_account_balance()
                            current_positions = await self.broker.get_positions()

                            # Calculate total portfolio value for risk management
                            total_value = current_balance
                            for p in current_positions:
                                p_quote = await self.market_data.get_quote(p["symbol"])
                                if p_quote and p_quote.price:
                                    total_value += p["quantity"] * p_quote.price

                            print(f"[DEBUG] Executing trade: balance={current_balance}, total_value={total_value}")
                            success = await self._execute_trade(target_rec, validation, total_value)
                            print(f"[DEBUG] Trade execution result: success={success}")
                            if success:
                                await self.repo.mark_decision_executed(rec["symbol"])
                        else:
                            print(f"Market CLOSED: Recommendation for {rec['symbol']} will be held as PLANNED.")
                            # Set manual review requirements for pending decision when market is closed
                            if validation["decision"] in ["PROCEED", "MODIFY"]:
                                await self.repo.update_decision_with_validation(
                                    symbol=rec["symbol"],
                                    remote_validation_decision=validation["decision"],
                                    remote_validation_comments="Market closed - pending execution when market opens",
                                    requires_manual_review=self.settings.TRADING_MODE == "live",
                                    new_confidence=validation.get("new_confidence")
                                )
                    elif validation["decision"] == "REJECT":
                        # Mark rejected decisions as executed so they don't show as pending
                        await self.repo.mark_decision_executed(rec["symbol"])
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
                    if p_quote and p_quote.price:
                        total_value += p["quantity"] * p_quote.price

                # Reconstruct rec and validation from decision context
                rec = decision.context.get("rec") if decision.context else None
                if not rec:
                    continue

                # Skip BUY if already bought today (BUY once per day rule)
                if rec.get("action") == "BUY" and await self.repo.was_bought_today(rec.get("symbol")):
                    print(f"Ignoring pending BUY for {rec.get('symbol')} (already bought today)")
                    await self.repo.mark_decision_executed(decision.symbol)
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
                
                # 3. Use rule-based validation for hourly revaluation
                print(f"Validating {position.stock.symbol} with rule-based validation...")
                validation = self._apply_validation_rules(
                    action=decision["action"],
                    confidence=decision["confidence"]
                )

                print(f"Revaluation Decision: {validation['decision']} - {validation['comments']}")

                # 4. Act on validation decision
                if validation["decision"] == "PROCEED" and decision["action"] == "SELL":
                    print(f"Hourly Revaluation: Executing SELL for {position.stock.symbol}")
                    await self._execute_trade(
                        {"symbol": position.stock.symbol, "action": "SELL"},
                        validation,
                        0.0
                    )
                    await self.repo.mark_decision_executed(position.stock.symbol)
                elif validation["decision"] == "MODIFY" and validation.get("new_action") == "SELL":
                    print(f"Hourly Revaluation: OVERRIDE to SELL for {position.stock.symbol}")
                    await self._execute_trade(
                        {"symbol": position.stock.symbol, "action": "SELL"},
                        validation,
                        0.0
                    )
                    await self.repo.mark_decision_executed(position.stock.symbol)
                elif validation["decision"] == "REJECT":
                    # Mark rejected decisions as executed
                    await self.repo.mark_decision_executed(position.stock.symbol)
                    print(f"Hourly Revaluation: Decision for {position.stock.symbol} rejected and marked as completed")
                
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

                        # For HOLD decisions, mark as completed immediately (no validation needed)
                        if final_action == "HOLD":
                            await self.repo.update_decision_with_validation(
                                symbol=position.stock.symbol,
                                remote_validation_decision="PROCEED",
                                remote_validation_comments="HOLD - no action required",
                                requires_manual_review=False
                            )

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

                            print("\nValidating SELL with rule-based validation...")
                            validation = self._apply_validation_rules(
                                action="SELL",
                                confidence=decision["confidence"]
                            )

                            print(f"Validation: {validation['decision']} - {validation['comments']}")

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
                                    if p_quote and p_quote.price:
                                        total_value += p["quantity"] * p_quote.price

                                success = await self._execute_trade(sell_rec, validation, balance=total_value)
                                if success:
                                    await self.repo.mark_decision_executed(position.stock.symbol)
                            elif validation["decision"] == "REJECT":
                                # Mark rejected decisions as executed
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
