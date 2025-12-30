"""Client for interacting with OpenRouter AI models."""

import json
from typing import Dict, Any

try:
    from openai import AsyncOpenAI  # pylint: disable=import-error
except ImportError:
    AsyncOpenAI = None

from .prompts import REMOTE_MARKET_ANALYSIS_PROMPT, SYSTEM_PROMPT


class OpenRouterClient:
    """Client for interacting with remote OpenRouter AI models."""

    def __init__(self, api_key: str, model: str):
        """Initialize the OpenRouter client.

        Args:
            api_key: The API key for OpenRouter.
            model: The model name to use.
        """
        self.client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
        )
        self.model = model

    async def analyze_market(
        self,
        portfolio_summary: str,
        timestamp: str,
        market_status: str,
        news_summary: str = "No news available."
    ) -> Dict[str, Any]:
        """Analyze the market using remote OpenRouter AI.

        Args:
            portfolio_summary: Summary of the current portfolio.
            timestamp: The current timestamp.
            market_status: Current market status information.
            news_summary: Summary of recent news.

        Returns:
            Dictionary containing the market analysis and recommendations.
        """
        prompt = REMOTE_MARKET_ANALYSIS_PROMPT.format(
            portfolio_summary=portfolio_summary,
            timestamp=timestamp,
            market_status=market_status,
            news_summary=news_summary
        )

        try:
            completion = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": SYSTEM_PROMPT
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                response_format={"type": "json_object"}
            )

            content = completion.choices[0].message.content
            return json.loads(content)

        except Exception as e:  # pylint: disable=broad-except
            return {
                "analysis_summary": f"Error: {str(e)}",
                "recommendations": []
            }
