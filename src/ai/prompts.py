"""AI prompts for trading analysis."""

import os

SYSTEM_PROMPT_PATH = os.path.join(
    os.path.dirname(__file__), '..', 'prompts', 'system-prompt.md'
)

def _load_system_prompt() -> str:
    """Load the system prompt from the markdown file."""
    try:
        with open(SYSTEM_PROMPT_PATH, 'r', encoding='utf-8') as f:
            content = f.read()
            # Extract just the prompt content (remove the role/objective sections headers if needed)
            # For now, we'll use the full content as the system prompt
            return content
    except FileNotFoundError:
        return """You are a Chief UK Market Strategist & Senior Equity Trader with
        deep expertise in the London Stock Exchange (LSE)."""

SYSTEM_PROMPT = _load_system_prompt()

REMOTE_MARKET_ANALYSIS_PROMPT = """
You are an AI trading analyst for the London Stock Exchange.

Current Portfolio:
{portfolio_summary}

Market Context:
- Date/Time: {timestamp}
- Market Status: {market_status}

{news_summary}

Task: Analyze the current market conditions and provide trading recommendations.
You have internet access - search for relevant news, sentiment, and financial data for LSE stocks (FTSE 100/250).

CRITICAL OUTPUT INSTRUCTIONS:
1. ALL trading recommendations (BUY/SELL/HOLD) MUST be included in the "recommendations" JSON list.
2. The "analysis_summary" field should provide high-level market context ONLY. 
3. DO NOT put actionable recommendations inside "analysis_summary".
4. If there are no stocks to recommend, return an empty list for "recommendations".
5. Return ONLY the raw JSON object. No preamble, no postamble, no markdown blocks.

For each recommendation object in the list, include:
1. "action": (BUY/SELL/HOLD)
2. "symbol": (e.g., LLOY.L)
3. "reasoning": (cite news/data)
4. "confidence": (0.0-1.0)
5. "size_pct": (percentage of portfolio, max 20% / 0.20)

Return your response in strict JSON format:
{{
    "analysis_summary": "High level market overview...",
    "recommendations": [
        {{
            "action": "BUY",
            "symbol": "LLOY.L",
            "reasoning": "...",
            "confidence": 0.85,
            "size_pct": 0.1
        }}
    ]
}}
"""

LOCAL_POSITION_CHECK_PROMPT = """
You are a local AI monitoring a trading position. You do NOT have internet access.
Base your decision ONLY on the data provided below.

Position Details:
- Symbol: {symbol}
- Entry Price: {entry_price}
- Current Price: {current_price}
- P&L: {pnl_percent:.2f}%
- Holding Period: {holding_days} days

Recent Price History (last 20 candles):
{price_history}

Technical Indicators:
- RSI (14): {rsi}
- MACD: {macd}
- SMA 20: {sma_20}
- SMA 50: {sma_50}

Volume Analysis:
- Current Volume: {current_volume}
- Average Volume: {avg_volume}

Task: Recommend HOLD, SELL, or ESCALATE (if uncertain or significant negative news is suspected).
CRITICAL: If you detect a large sudden price drop, a breakdown below major support (SMA 50), or RSI dropping sharply from overbought, suggest a SELL to avoid further losses.
Provide reasoning and confidence score (0.0-1.0).

Return your response in strict JSON format:
{{
    "decision": "HOLD",
    "reasoning": "...",
    "confidence": 0.9
}}
"""

LOCAL_MARKET_ANALYSIS_WITH_TOOLS_PROMPT = """
You are an AI trading analyst for London Stock Exchange with access to real-time data tools.

Current Portfolio:
{portfolio_summary}

Market Context:
"""
