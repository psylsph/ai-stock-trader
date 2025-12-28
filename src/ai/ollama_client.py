import json
from typing import Dict, Any, Optional
import ollama
from .prompts import LOCAL_POSITION_CHECK_PROMPT

class OllamaClient:
    def __init__(self, host: str, model: str):
        self.host = host
        self.model = model
        # ollama python client uses OLLAMA_HOST env var by default, 
        # or we can assume it's running locally if standard port.
        # But the python client constructor is simple.
        
    async def analyze_position(self, 
                             symbol: str, 
                             entry_price: float, 
                             current_price: float, 
                             holding_days: int,
                             price_history: str,
                             indicators: Dict[str, float],
                             volume_data: Dict[str, float]) -> Dict[str, Any]:
        
        pnl_percent = ((current_price - entry_price) / entry_price) * 100
        
        prompt = LOCAL_POSITION_CHECK_PROMPT.format(
            symbol=symbol,
            entry_price=entry_price,
            current_price=current_price,
            pnl_percent=pnl_percent,
            holding_days=holding_days,
            price_history=price_history,
            rsi=indicators.get("rsi", 0),
            macd=indicators.get("macd", 0),
            sma_20=indicators.get("sma_20", 0),
            sma_50=indicators.get("sma_50", 0),
            current_volume=volume_data.get("current", 0),
            avg_volume=volume_data.get("average", 0)
        )
        
        try:
            response = ollama.chat(model=self.model, messages=[
                {
                    'role': 'user',
                    'content': prompt,
                },
            ], format='json')
            
            content = response['message']['content']
            return json.loads(content)
            
        except Exception as e:
            # Fallback safe response
            return {
                "decision": "ESCALATE",
                "reasoning": f"Local AI error: {str(e)}",
                "confidence": 0.0
            }
