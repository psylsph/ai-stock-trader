from datetime import datetime
from typing import List, Dict, Any, Optional
from src.ai.ollama_client import OllamaClient
from src.ai.openrouter_client import OpenRouterClient
from src.database.models import Position, AIDecision

class TradingDecisionEngine:
    def __init__(self, ollama_client: OllamaClient, openrouter_client: OpenRouterClient):
        self.local_ai = ollama_client
        self.remote_ai = openrouter_client

    async def startup_analysis(self, portfolio_summary: str, market_status: str, news_summary: str) -> Dict[str, Any]:
        """Run full market analysis using remote AI"""
        timestamp = datetime.now().isoformat()
        
        analysis = await self.remote_ai.analyze_market(
            portfolio_summary=portfolio_summary,
            timestamp=timestamp,
            market_status=market_status,
            news_summary=news_summary
        )
        
        return analysis

    async def intraday_check(self, 
                           position: Position, 
                           price_history: str,
                           indicators: Dict[str, float],
                           volume_data: Dict[str, float]) -> Dict[str, Any]:
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
            (action == "SELL" and confidence < 0.8) # Require high confidence for local sell
        )
        
        if should_escalate:
            # TODO: Implement specific escalation logic (e.g., confirm sell with remote AI)
            # For now, we will treat ESCALATE as HOLD but return the flag
            # In a full impl, we would call self.remote_ai.confirm_sell(...)
            return {
                "action": "HOLD", # Default to hold if unsure and can't escalate yet
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
