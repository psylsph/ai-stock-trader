"""Client for interacting with LM Studio via OpenAI-compatible API."""

import json
import base64
from datetime import datetime, timezone
from typing import Dict, Any, List, TYPE_CHECKING

if TYPE_CHECKING:
    from .tools import TradingTools

try:
    from openai import AsyncOpenAI  # pylint: disable=import-error
except ImportError:
    AsyncOpenAI = None

from .prompts import (
    SYSTEM_PROMPT,
    LOCAL_POSITION_CHECK_PROMPT,
    LOCAL_MARKET_ANALYSIS_WITH_TOOLS_PROMPT
)


class LocalAIClient:
    """Client for interacting with local LM Studio AI models with tools and vision."""

    def __init__(self, api_url: str, model: str):
        """Initialize LM Studio client.

        Args:
            api_url: The LM Studio API URL (e.g., http://localhost:1234/v1)
            model: The model identifier shown in LM Studio.
        """
        if AsyncOpenAI is None:
            raise ImportError("openai library is required. Install with: pip install openai")
        self.client = AsyncOpenAI(
            base_url=api_url,
            api_key="lm-studio"  # LM Studio doesn't require API key
        )
        self.model = model

    async def analyze_market_with_tools(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        portfolio_summary: str,
        market_status: str,
        rss_news_summary: str,
        tools: 'TradingTools',
        max_tool_calls: int = 10
    ) -> Dict[str, Any]:
        """Analyze market using local AI with tools.

        Args:
            portfolio_summary: Summary of current portfolio.
            market_status: Current market status.
            rss_news_summary: Summary from RSS feeds.
            tools: TradingTools instance with tool execution capabilities.
            max_tool_calls: Maximum number of tool iterations.

        Returns:
            Dictionary containing analysis and recommendations.
        """
        messages = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": LOCAL_MARKET_ANALYSIS_WITH_TOOLS_PROMPT.format(
                    portfolio_summary=portfolio_summary,
                    market_status=market_status,
                    rss_news_summary=rss_news_summary
                )
            }
        ]

        tool_schemas = tools.get_tool_schemas()

        tool_call_count = 0
        reasoning_chain = []

        while tool_call_count < max_tool_calls:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tool_schemas
            )

            message = response.choices[0].message
            content = message.content or ""
            tool_calls = message.tool_calls or []

            if not tool_calls:
                break

            reasoning_chain.append(f"AI reasoning: {content}")

            for tool_call in tool_calls:
                function_name = tool_call.function.name
                arguments = json.loads(tool_call.function.arguments)

                tool_result = await tools.execute_tool(function_name, arguments)

                if "chart_path" in tool_result and tool_result.get("analysis_needed"):
                    chart_path = tool_result["chart_path"]
                    chart_base64 = tools.chart_fetcher.image_to_base64(chart_path)
                    
                    # Vision analysis using LM Studio's multimodal support
                    vision_response = await self.client.chat.completions.create(
                        model=self.model,
                        messages=[{
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": "Analyze this stock chart for trading signals, trends, support/resistance levels, and potential entry/exit points."
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {"url": chart_base64}
                                }
                            ]
                        }]
                    )
                    tool_result["vision_analysis"] = vision_response.choices[0].message.content

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(tool_result)
                })

            tool_call_count += 1

        # Final call to get structured response
        final_response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages
        )

        try:
            return json.loads(final_response.choices[0].message.content)
        except json.JSONDecodeError:
            return {
                "analysis_summary": final_response.choices[0].message.content,
                "recommendations": [],
                "reasoning_chain": reasoning_chain
            }

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
        """Analyze a position using local AI."""
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
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": SYSTEM_PROMPT,
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ]
            )

            content = response.choices[0].message.content
            return json.loads(content)

        except Exception as e:  # pylint: disable=broad-except
            return {
                "decision": "ESCALATE",
                "reasoning": f"Local AI error: {str(e)}",
                "confidence": 0.0
            }
