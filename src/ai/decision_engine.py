"""Decision engine for AI-based trading decisions."""

import json
from datetime import datetime, timezone
from typing import Dict, Any

from src.ai.local_ai_client import LocalAIClient
from src.ai.openrouter_client import OpenRouterClient
from src.database.models import Position
from src.ai.tools import TradingTools


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
                        "content": "You are a senior UK market trader with deep expertise in LSE stocks."
                    },
                    {
                        "role": "user",
                        "content": validation_prompt
                    }
                ],
                response_format={"type": "json_object"}
            )

            content = completion.choices[0].message.content
            return json.loads(content)

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
        holding_days = (datetime.utcnow() - position.entry_date).days

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
            # For now, we will treat ESCALATE as HOLD but return the flag
            # In a full impl, we would call self.remote_ai.confirm_sell(...)
            return {
                "action": "HOLD",  # Default to hold if unsure and can't escalate yet
                "reasoning": f"Escalated from local AI: {local_decision.get('reasoning')}",
                "confidence": confidence,
                "escalated": True
            }

        return {
            "action": action,
            "reasoning": local_decision.get("reasoning"),
            "confidence": confidence,
            "escalated": False
        }
