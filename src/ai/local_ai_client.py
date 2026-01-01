import asyncio
import json
import random
from typing import Dict, Any, List, Tuple, TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .tools import TradingTools

from openai import AsyncOpenAI

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
        print(f"[DEBUG] Initializing LocalAIClient with URL: {api_url}")
        print(f"[DEBUG] Model: {model}")
        if AsyncOpenAI is None:
            raise ImportError("openai library is required. Install with: pip install openai")
        self.client = AsyncOpenAI(
            base_url=api_url,
            api_key="lm-studio"
        )
        self.model = model

    async def _call_with_retry(
        self,
        func,
        max_retries: int = 3,
        base_delay: float = 1.0
    ) -> Any:
        """Wrapper to retry API calls with exponential backoff."""
        for attempt in range(max_retries):
            try:
                if asyncio.iscoroutinefunction(func):
                    return await func()
                else:
                    result = func()
                    if asyncio.iscoroutine(result):
                        return await result
                    return result
            except Exception as e:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                    print(f"  [Retry {attempt + 1}/{max_retries} in {delay:.1f}s: {str(e)[:50]}...", end='', flush=True)
                    await asyncio.sleep(delay)
                else:
                    print()
                    raise

    async def _stream_chat_completion(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        print_tokens: bool = True
    ) -> Tuple[str, List]:
        """Stream chat completion and print tokens as they arrive."""
        kwargs = {
            "model": self.model,
            "messages": messages,
            "stream": True
        }
        if tools:
            kwargs["tools"] = tools

        stream = await self.client.chat.completions.create(**kwargs)  # type: ignore[arg-type]

        full_content = ""
        tool_calls_buffer = []
        tool_calls_dict = {}

        try:
            async for chunk in stream:
                if not chunk.choices:
                    continue

                delta = chunk.choices[0].delta

                if delta.content:
                    full_content += delta.content
                    if print_tokens:
                        print(delta.content, end='', flush=True)

                if delta.tool_calls:
                    for tool_call in delta.tool_calls:
                        if tool_call.id not in tool_calls_dict:
                            tool_calls_dict[tool_call.id] = {
                                "id": tool_call.id,
                                "type": "function",
                                "function": {
                                    "name": "",
                                    "arguments": ""
                                }
                            }

                        if tool_call.function:
                            if tool_call.function.name:
                                tool_calls_dict[tool_call.id]["function"]["name"] = tool_call.function.name
                            if tool_call.function.arguments:
                                tool_calls_dict[tool_call.id]["function"]["arguments"] += tool_call.function.arguments

        except Exception as e:
            print(f"  [Streaming Error: {e}]")

        tool_calls_buffer = list(tool_calls_dict.values())

        if print_tokens:
            print()
        return full_content, tool_calls_buffer

    def _clean_json_response(self, text: str) -> str:
        """Clean AI output to extract valid JSON."""
        import re
        # Remove code block markers (```json, ```)
        text = re.sub(r'```[a-zA-Z]*\n?', '', text)
        text = re.sub(r'```', '', text)
        # Remove [THINK] blocks
        text = re.sub(r'\[THINK\].*?\[/THINK\]', '', text, flags=re.DOTALL)
        # Remove any markdown-style explanations before/after JSON
        text = re.sub(r'^[^{]*', '', text)
        text = re.sub(r'[^}]*$', '', text)
        # Find the first { and last }
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1 and end > start:
            return text[start:end+1]
        return text

    async def analyze_market_with_tools(
        self,
        portfolio_summary: str,
        market_status: str,
        rss_news_summary: str,
        tools: 'TradingTools',
        max_tool_calls: int = 10
    ) -> Dict[str, Any]:
        """Analyze market using local AI with tools."""
        print("\n[Local AI Analyzing Market with Tools...]")

        output_instructions = """
CRITICAL OUTPUT INSTRUCTIONS:
1. ALL trading recommendations (BUY/SELL/HOLD) MUST be included in the "recommendations" JSON list.
2. The "analysis_summary" field should provide high-level market context ONLY.
3. DO NOT put actionable recommendations inside "analysis_summary".
4. If there are no stocks to recommend, return an empty list for "recommendations".
5. Return ONLY the raw JSON object. No markdown formatting (```json), no [THINK] blocks, no explanations outside JSON.
6. Begin with { and end with } - no preamble, no postamble.

Return your response in strict JSON format:
{
    "analysis_summary": "High level market overview...",
    "recommendations": [
        {
            "action": "BUY"|"SELL"|"HOLD",
            "symbol": "...",
            "reasoning": "...",
            "confidence": 0.85,
            "size_pct": 0.1
        }
    ]
}
"""

        messages = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT + "\n\n" + output_instructions
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
            print(f"\n[Iteration {tool_call_count + 1}]", end='', flush=True)

            full_content, tool_calls = await self._call_with_retry(
                lambda: self._stream_chat_completion(
                    messages=messages,
                    tools=tool_schemas,
                    print_tokens=True
                )
            )

            reasoning_chain.append(f"AI reasoning: {full_content}")

            if not tool_calls:
                break

            for tool_call in tool_calls:
                function_name = tool_call.function.name
                print(f"\n[Tool Call: {function_name}]", end='', flush=True)

                arguments = json.loads(tool_call.function.arguments)

                tool_result = await tools.execute_tool(function_name, arguments)

                if "chart_path" in tool_result and tool_result.get("analysis_needed"):
                    print("[Running vision analysis...]", end='', flush=True)
                    chart_path = tool_result["chart_path"]
                    chart_base64 = tools.chart_fetcher.image_to_base64(chart_path)

                    vision_response = await self.client.chat.completions.create(
                        model=self.model,
                        messages=[
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "text",
                                        "text": (
                                            "Analyze this stock chart for trading signals, "
                                            "trends, support/resistance levels, and potential "
                                            "entry/exit points."
                                        )
                                    },
                                    {
                                        "type": "image_url",
                                        "image_url": {"url": chart_base64}
                                    }
                                ]
                            }
                        ],
                        stream=True
                    )

                    vision_content = ""
                    try:
                        async for chunk in vision_response:  # type: ignore[attr-defined]
                            if chunk.choices and chunk.choices[0].delta.content:
                                vision_content += chunk.choices[0].delta.content
                                print(chunk.choices[0].delta.content, end='', flush=True)
                    except Exception:
                        pass

                    print()
                    tool_result["vision_analysis"] = vision_content

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(tool_result)
                })

            tool_call_count += 1

        print("\n[Finalizing recommendations...]", end='', flush=True)
        final_content, _ = await self._stream_chat_completion(
            messages=messages,
            print_tokens=True
        )

        cleaned_content = self._clean_json_response(final_content)

        try:
            return json.loads(cleaned_content)
        except json.JSONDecodeError:
            return {
                "analysis_summary": final_content,
                "recommendations": [],
                "reasoning_chain": reasoning_chain
            }

    async def analyze_position(
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
        print(f"[Checking position: {symbol}]", end='', flush=True)

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

        full_content, _ = await self._call_with_retry(
            lambda: self._stream_chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": SYSTEM_PROMPT
                    },
                    {
                        "role": "user",
                        "content": prompt
                    },
                ],
                print_tokens=True
            )
        )

        try:
            cleaned_content = self._clean_json_response(full_content)
            return json.loads(cleaned_content)
        except Exception:
            return {
                "decision": "HOLD",
                "reasoning": f"Error parsing response: {full_content[:100]}",
                "confidence": 0.0
            }
