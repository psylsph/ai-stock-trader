"""Client for interacting with OpenRouter AI models."""

import json
from typing import Dict, Any

from openai import AsyncOpenAI

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

        return await self._call_with_retry(prompt)

    async def _call_with_retry(self, prompt: str, retry_count: int = 0) -> Dict[str, Any]:
        """Make an API call with retry logic for token limit errors.

        If the request fails due to token limits, strips ":free" from model name and retries.

        Args:
            prompt: The prompt to send to the AI.
            retry_count: Number of retries attempted.

        Returns:
            Dictionary response from the AI.
        """
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
            if content is None:
                raise ValueError("No content in response")
            return json.loads(content)

        except Exception as e:  # pylint: disable=broad-except
            error_msg = str(e).lower()

            # Check if this is a token limit or context length error
            token_errors = ["context_length_exceeded", "too many tokens", "token limit", "context window", "max_tokens"]

            # Check if model has :free suffix and we haven't retried yet
            if retry_count == 0 and ":free" in self.model:
                for token_error in token_errors:
                    if token_error in error_msg:
                        print(f"[DEBUG] Token limit error with :free model, retrying without :free suffix...")
                        # Retry with model name without :free
                        original_model = self.model
                        self.model = self.model.replace(":free", "")
                        try:
                            result = await self._call_with_retry(prompt, retry_count=1)
                            # Restore original model for future calls
                            self.model = original_model
                            return result
                        except Exception:  # pylint: disable=broad-except
                            # Restore original model and fall through to error handling
                            self.model = original_model
                            break

            return {
                "analysis_summary": f"Error: {str(e)}",
                "recommendations": []
            }
