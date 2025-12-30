"""Client for interacting with Ollama AI models."""

import json
from typing import Dict, Any

try:
    import ollama  # pylint: disable=import-error
except ImportError:
    ollama = None

from .prompts import LOCAL_POSITION_CHECK_PROMPT, SYSTEM_PROMPT


class OllamaClient:
    """Client for interacting with local Ollama AI models."""

    def __init__(self, host: str, model: str):
        """Initialize the Ollama client.

        Args:
            host: The Ollama host URL.
            model: The model name to use.
        """
        self.host = host
        self.model = model
        # ollama python client uses OLLAMA_HOST env var by default,
        # or we can assume it's running locally if standard port.
        # But the python client constructor is simple.

    async def analyze_position(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        symbol: str,
        entry_price: float,
        current_price: float,
        holding_days: int,
        price_history: str,
        indicators: Dict[str, float],
        volume_data: Dict[str, float]
    ) -> Dict[str, Any]:
        """Analyze a position using local Ollama AI.

        Args:
            symbol: The stock symbol.
            entry_price: The entry price of the position.
            current_price: The current price of the position.
            holding_days: Number of days holding the position.
            price_history: Historical price data as a string.
            indicators: Dictionary of technical indicators.
            volume_data: Dictionary of volume data.

        Returns:
            Dictionary containing the decision, reasoning, and confidence.
        """
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
                    'role': 'system',
                    'content': SYSTEM_PROMPT,
                },
                {
                    'role': 'user',
                    'content': prompt,
                },
            ], format='json')

            content = response['message']['content']
            return json.loads(content)

        except Exception as e:  # pylint: disable=broad-except
            # Fallback safe response
            return {
                "decision": "ESCALATE",
                "reasoning": f"Local AI error: {str(e)}",
                "confidence": 0.0
            }
