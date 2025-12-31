"""Decision engine for AI-based trading decisions."""

import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from src.ai.local_ai_client import LocalAIClient
from src.ai.openrouter_client import OpenRouterClient
from src.database.models import Position
from src.ai.tools import TradingTools
from .prompts import SYSTEM_PROMPT


class TradingDecisionEngine:
    """Engine for making trading decisions using local and remote AI."""
    def __init__(self, local_ai: LocalAIClient, openrouter_client: OpenRouterClient):
        self.local_ai = local_ai
        self.remote_ai = openrouter_client

    async def startup_analysis(
        self,
        portfolio_summary: str,
        market_status: str,
        rss_news_summary: str,
        tools: 'TradingTools'
    ) -> Dict[str, Any]:
        """Run full market analysis using local AI with tools."""
        analysis = await self.local_ai.analyze_market_with_tools(
            portfolio_summary=portfolio_summary,
            market_status=market_status,
            rss_news_summary=rss_news_summary,
            tools=tools
        )

        return analysis

    async def validate_with_remote_ai(
        self,
        action: str,
        symbol: str,
        reasoning: str,
        confidence: float,
        size_pct: float
    ) -> Dict[str, Any]:
        """Validate a trading decision with remote AI before execution.

        Args:
            action: Proposed action (BUY/SELL)
            symbol: Stock symbol
            reasoning: Local AI's reasoning
            confidence: Local AI's confidence score
            size_pct: Suggested position size

        Returns:
            Validation decision from remote AI.
        """
        validation_prompt = f"""
        You are a senior trader validating a trading decision proposed by an AI system.

        Proposed Trade:
        - Action: {action}
        - Symbol: {symbol}
        - Confidence: {confidence}
        - Position Size: {size_pct * 100:.1f}% of portfolio

        Reasoning from Local AI:
        {reasoning}

        Task: Validate this trade decision. Consider:
        1. Is reasoning sound?
        2. Are there risks that local AI missed?
        3. Should we proceed, modify, or reject?

        Return your response in strict JSON format:
        {{
            "decision": "PROCEED"|"MODIFY"|"REJECT",
            "new_confidence": 0.85,
            "new_size_pct": 0.1,
            "comments": "Your validation comments here"
        }}
        """

        try:
            completion = await self.remote_ai.client.chat.completions.create(
                model=self.remote_ai.model,
                messages=[
                    {
                        "role": "system",
                        "content": SYSTEM_PROMPT
                    },
                    {
                        "role": "user",
                        "content": validation_prompt
                    }
                ],
                response_format={"type": "json_object"}
            )

            content = completion.choices[0].message.content
            if content is None:
                raise ValueError("No content in response")

            validation_result = json.loads(content)

            return validation_result

        except Exception as e:  # pylint: disable=broad-except
            return {
                "decision": "PROCEED",
                "comments": f"Validation failed, proceeding with original: {str(e)}"
            }

    async def intraday_check(
        self,
        position: Position,
        price_history: str,
        indicators: Dict[str, float],
        volume_data: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        Check position with local AI, escalate if needed.
        Returns a decision dict: {"action": "HOLD"|"SELL", "reasoning": "...", "escalated": bool}
        """
        holding_days = (datetime.now(timezone.utc) - position.entry_date).days

        # 1. Local Check
        local_decision = await self.local_ai.analyze_position(
            symbol=position.stock.symbol,
            entry_price=position.entry_price,
            current_price=position.current_price,
            holding_days=holding_days,
            price_history=price_history,
            indicators=indicators,
            volume_data=volume_data
        )

        action = local_decision.get("decision", "HOLD").upper()
        confidence = local_decision.get("confidence", 0.0)

        # 2. Escalation Checks
        should_escalate = (
            action == "ESCALATE" or
            (action == "SELL" and confidence < 0.8)  # Require high confidence for local sell
        )

        if should_escalate:
            # TODO: Implement specific escalation logic (e.g., confirm sell with remote AI)  # pylint: disable=fixme
            # For now, we will treat ESCALATE as HOLD but return a flag
            # In a full impl, we would call self.remote_ai.confirm_sell(...)
            result = {
                "action": "HOLD",  # Default to hold if unsure and can't escalate yet
                "reasoning": f"Escalated from local AI: {local_decision.get('reasoning')}",
                "confidence": confidence,
                "escalated": True
            }

            return result

        result = {
            "action": action,
            "reasoning": local_decision.get("reasoning"),
            "confidence": confidence,
            "escalated": False
        }

        return result

    async def startup_analysis_with_prescreening(
        self,
        portfolio_summary: str,
        market_status: str,
        prescreened_tickers: Dict[str, Dict[str, Any]],
        rss_news_summary: str,
        tools: Optional['TradingTools'] = None
    ) -> Dict[str, Any]:
        """
        Run analysis on prescreened stocks with targeted news data.

        Args:
            prescreened_tickers: Dict of ticker to indicator results
            rss_news_summary: News data for prescreened stocks only
        """
        prompt = f"""
You are analyzing the TOP 10 technically strongest FTSE 100 stocks based on pre-filtering.

Technical Leaders ({len(prescreened_tickers)} stocks):
{', '.join(prescreened_tickers.keys())}

Indicator Results:
"""
        for ticker, indicators in prescreened_tickers.items():
            prompt += f"""
{ticker}:
  - RSI (14): {indicators['rsi']:.1f}
  - MACD: {indicators['macd']:.2f} (Signal: {'Bullish' if indicators['signal'] > 0 else 'Bearish'})
  - SMA 50: £{indicators['sma_50']:.2f}
  - SMA 200: £{indicators['sma_200']:.2f}
  - Current Price: £{indicators['current_price']:.2f}
  - Passed Prescreening: {indicators['passed']}
"""

        prompt += f"""

Portfolio Status:
{portfolio_summary}

Market Status:
{market_status}

News Summary for Prescreened Stocks:
{rss_news_summary}

Task: Analyze the prescreened stocks with their news data and provide trading recommendations.
Consider each stock's technical setup and sentiment from their news.

CRITICAL OUTPUT INSTRUCTIONS:
1. ALL trading recommendations (BUY/SELL/HOLD) MUST be included in the "recommendations" JSON list.
2. The "analysis_summary" field should provide high-level market context ONLY.
3. DO NOT put actionable recommendations inside "analysis_summary".
4. If there are no stocks to recommend, return an empty list for "recommendations".
5. Return ONLY the raw JSON object. No preamble, no postamble, no markdown blocks.

Return your response in strict JSON format:
{{
    "analysis_summary": "High level market overview...",
    "recommendations": [
        {{
            "action": "BUY"|"SELL"|"HOLD",
            "symbol": "...",
            "reasoning": "...",
            "confidence": 0.85,
            "size_pct": 0.1
        }}
    ]
}}
"""

        messages = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": prompt
            }
        ]

        full_content, _ = await self.local_ai._stream_chat_completion(
            messages=messages,
            print_tokens=True
        )

        # Helper to clean AI output
        def clean_json_response(text: str) -> str:
            # Remove [THINK] blocks
            import re
            text = re.sub(r'\[THINK\].*?\[/THINK\]', '', text, flags=re.DOTALL)
            # Find the first { and last }
            start = text.find('{')
            end = text.rfind('}')
            if start != -1 and end != -1:
                return text[start:end+1]
            return text

        cleaned_content = clean_json_response(full_content)

        try:
            return json.loads(cleaned_content)
        except json.JSONDecodeError:
            return {
                "analysis_summary": full_content,
                "recommendations": []
            }
