"""Placeholder for AutoGen agent integration.

In the current implementation, we use TradingDecisionEngine directly
for deterministic control. If we were to use AutoGen agents,
we would define them here.
"""


class MarketAnalystAgent:
    """Wrapper for future AutoGen based market analyst.

    Currently logic is handled by OpenRouterClient + TradingDecisionEngine.
    """


class PositionMonitorAgent:
    """Wrapper for future AutoGen based position monitor.

    Currently logic is handled by OllamaClient + TradingDecisionEngine.
    """
