# AI Stock Trading Bot - Implementation Plan

This document provides a detailed implementation plan for building an AI-powered stock trading bot that trades on the London Stock Exchange (LSE), using a two-tier AI decision system with AutoGen orchestration.

---

## Overview

Build a Python-based stock trading bot with:

- **Remote AI** (OpenRouter x-ai/grok-4): Primary decision-maker with internet access for market analysis
- **Local AI** (Ollama llama3.2:3b): Fast intraday monitoring, escalates sell signals to remote AI
- **SQLite Database**: Store market data, positions, and trade history
- **AutoGen**: Orchestrate AI agents and trading workflow

---

## Project Structure

```
ai-stock-trader/
├── src/
│   ├── __init__.py
│   ├── main.py                    # Entry point
│   ├── config.py                  # Configuration management
│   ├── database/
│   │   ├── __init__.py
│   │   ├── models.py              # SQLAlchemy/Pydantic models
│   │   ├── repository.py          # Database operations
│   │   └── migrations/            # Database migrations
│   ├── market/
│   │   ├── __init__.py
│   │   ├── data_fetcher.py        # Market data API integration
│   │   ├── stock.py               # Stock/ETF data models
│   │   └── lse_handler.py         # LSE-specific logic
│   ├── ai/
│   │   ├── __init__.py
│   │   ├── openrouter_client.py   # OpenRouter API client
│   │   ├── ollama_client.py       # Ollama local model client
│   │   ├── decision_engine.py     # Trading decision logic
│   │   └── prompts.py             # AI prompt templates
│   ├── trading/
│   │   ├── __init__.py
│   │   ├── broker.py              # Broker API interface (abstract)
│   │   ├── paper_trader.py        # Paper trading implementation
│   │   ├── position_manager.py    # Position tracking
│   │   └── risk_manager.py        # Risk limits and checks
│   └── orchestration/
│       ├── __init__.py
│       ├── agents.py              # AutoGen agent definitions
│       └── workflows.py           # Trading workflows
├── tests/
│   ├── __init__.py
│   ├── test_database.py
│   ├── test_market.py
│   ├── test_ai.py
│   ├── test_trading.py
│   └── test_orchestration.py
├── requirements.txt
├── config.example.yaml            # Example configuration
├── .env.example                   # Environment variables template
├── README.md
└── PLAN.md
```

---

## Component Specifications

### 1. Configuration (`src/config.py`)

Manage all configuration via environment variables and YAML file:

```python
# Required configuration
OPENROUTER_API_KEY: str
OLLAMA_HOST: str = "http://localhost:11434"
OLLAMA_MODEL: str = "llama3.2:3b"
OPENROUTER_MODEL: str = "x-ai/grok-4"
DATABASE_URL: str = "sqlite:///trading.db"
MARKET_DATA_API_KEY: str  # For Alpha Vantage, Yahoo Finance, or similar
TRADING_MODE: str = "paper"  # "paper" or "live"
CHECK_INTERVAL_SECONDS: int = 300  # 5 minutes for intraday checks
```

**Implementation Details:**

- Use `pydantic-settings` for environment variable loading
- Support YAML fallback for non-sensitive config
- Validate all config on startup

---

### 2. Database Layer (`src/database/`)

#### Models (`models.py`)

```python
class Stock(Base):
    """Stock or ETF tracked by the bot"""
    symbol: str          # e.g., "LLOY.L" for Lloyds
    name: str
    type: str            # "stock" or "etf"
    exchange: str = "LSE"
    is_active: bool = True

class Position(Base):
    """Current holdings"""
    stock_id: int
    quantity: float
    entry_price: float
    entry_date: datetime
    current_price: float
    unrealized_pnl: float

class Trade(Base):
    """Trade history"""
    stock_id: int
    action: str          # "BUY" or "SELL"
    quantity: float
    price: float
    timestamp: datetime
    ai_reasoning: str    # Store AI's decision rationale
    escalated: bool      # Was this escalated to remote AI?

class MarketSnapshot(Base):
    """Historical market data"""
    stock_id: int
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    
class AIDecision(Base):
    """Log of all AI decisions"""
    timestamp: datetime
    ai_type: str         # "local" or "remote"
    context: JSON        # Input data provided to AI
    response: JSON       # Full AI response
    decision: str        # "BUY", "SELL", "HOLD"
    confidence: float
```

**Implementation Details:**

- Use SQLAlchemy ORM with SQLite
- Create repository pattern for clean data access
- Include migration support via Alembic

---

### 3. Market Data (`src/market/`)

#### Data Fetcher (`data_fetcher.py`)

Interface for fetching LSE market data:

```python
class MarketDataFetcher(ABC):
    @abstractmethod
    async def get_quote(self, symbol: str) -> Quote: ...
    
    @abstractmethod
    async def get_historical(self, symbol: str, period: str) -> List[OHLCV]: ...
    
    @abstractmethod
    async def get_market_status(self) -> MarketStatus: ...

class YahooFinanceFetcher(MarketDataFetcher):
    """Yahoo Finance implementation (free, supports LSE)"""
    # Use yfinance library
    # LSE symbols use ".L" suffix (e.g., "LLOY.L")
```

**LSE-Specific Handling:**

- Market hours: 8:00 AM - 4:30 PM GMT
- Handle GBp (pence) vs GBP (pounds) pricing
- Support FTSE 100, FTSE 250 stocks and ETFs

**Recommended Free APIs:**

1. **Yahoo Finance** (via `yfinance`) - Best free option for LSE
2. **Alpha Vantage** - Free tier has rate limits
3. **Polygon.io** - Limited LSE support on free tier

---

### 4. AI Integration (`src/ai/`)

#### OpenRouter Client (`openrouter_client.py`)

```python
class OpenRouterClient:
    """Client for remote AI with internet access"""
    
    def __init__(self, api_key: str, model: str = "x-ai/grok-4"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://openrouter.ai/api/v1"
    
    async def analyze_market(self, context: MarketContext) -> TradingDecision:
        """
        Full market analysis with web search capability.
        The model has internet access and can search for:
        - Current news about stocks
        - Market sentiment
        - Economic indicators
        - Company financials
        """
        pass
    
    async def confirm_sell(self, position: Position, local_analysis: str) -> bool:
        """Confirm sell decision escalated from local AI"""
        pass
```

#### Ollama Client (`ollama_client.py`)

```python
class OllamaClient:
    """Client for local AI (no internet access)"""
    
    def __init__(self, host: str = "http://localhost:11434", model: str = "llama3.2:3b"):
        self.host = host
        self.model = model
    
    async def analyze_position(self, data: PositionData) -> LocalDecision:
        """
        Analyze a position with provided data only.
        
        Data provided must include:
        - Current price and recent price history
        - Entry price and P&L
        - Technical indicators (pre-calculated)
        - Volume data
        - Any relevant context from last remote analysis
        """
        pass
    
    def should_escalate(self, decision: LocalDecision) -> bool:
        """Determine if decision should be escalated to remote AI"""
        return decision.action == "SELL" or decision.confidence < 0.6
```

#### Decision Engine (`decision_engine.py`)

```python
class TradingDecisionEngine:
    """Orchestrates AI decision making"""
    
    async def startup_analysis(self) -> List[TradingAction]:
        """
        Full market analysis at bot startup:
        1. Fetch current market state
        2. Analyze existing positions
        3. Scan for opportunities
        4. Use remote AI for decisions
        """
        pass
    
    async def intraday_check(self, position: Position) -> TradingAction:
        """
        Regular position monitoring:
        1. Get latest price data
        2. Calculate technical indicators
        3. Query local AI
        4. Escalate to remote AI if needed
        """
        pass
```

#### Prompt Templates (`prompts.py`)

```python
REMOTE_MARKET_ANALYSIS_PROMPT = """
You are an AI trading analyst for the London Stock Exchange.

Current Portfolio:
{portfolio_summary}

Market Context:
- Date/Time: {timestamp}
- Market Status: {market_status}

Task: Analyze the current market conditions and provide trading recommendations.
You have internet access - search for relevant news, sentiment, and financial data.

For each recommendation, provide:
1. Action (BUY/SELL/HOLD)
2. Symbol
3. Reasoning
4. Confidence (0-1)
5. Suggested position size (percentage of portfolio)
"""

LOCAL_POSITION_CHECK_PROMPT = """
You are a local AI monitoring a trading position. You do NOT have internet access.
Base your decision ONLY on the data provided below.

Position Details:
- Symbol: {symbol}
- Entry Price: {entry_price}
- Current Price: {current_price}
- P&L: {pnl_percent}%
- Holding Period: {holding_days} days

Recent Price History (last 20 candles):
{price_history}

Technical Indicators:
- RSI (14): {rsi}
- MACD: {macd}
- 20-day SMA: {sma_20}
- 50-day SMA: {sma_50}

Volume Analysis:
- Current Volume: {current_volume}
- Average Volume: {avg_volume}
- Volume Ratio: {volume_ratio}

Task: Recommend HOLD, SELL, or ESCALATE (if uncertain).
Provide reasoning and confidence score (0-1).
"""
```

---

### 5. Trading Logic (`src/trading/`)

#### Broker Interface (`broker.py`)

```python
class Broker(ABC):
    """Abstract broker interface"""
    
    @abstractmethod
    async def buy(self, symbol: str, quantity: float) -> Order: ...
    
    @abstractmethod
    async def sell(self, symbol: str, quantity: float) -> Order: ...
    
    @abstractmethod
    async def get_account_balance(self) -> float: ...
    
    @abstractmethod
    async def get_positions(self) -> List[Position]: ...
```

#### Paper Trader (`paper_trader.py`)

```python
class PaperTrader(Broker):
    """Simulated trading for testing"""
    
    def __init__(self, initial_balance: float = 10000.0):
        self.balance = initial_balance
        self.positions = {}
    
    async def buy(self, symbol: str, quantity: float) -> Order:
        """Simulate buy order at current market price"""
        pass
    
    async def sell(self, symbol: str, quantity: float) -> Order:
        """Simulate sell order at current market price"""
        pass
```

#### Risk Manager (`risk_manager.py`)

```python
class RiskManager:
    """Enforce trading risk limits"""
    
    MAX_POSITION_SIZE_PCT = 0.20      # Max 20% in single position
    MAX_DAILY_TRADES = 10
    STOP_LOSS_PCT = 0.05              # 5% stop loss
    TAKE_PROFIT_PCT = 0.15            # 15% take profit
    
    def validate_trade(self, action: TradingAction, portfolio: Portfolio) -> bool:
        """Check if trade meets risk requirements"""
        pass
    
    def check_stop_loss(self, position: Position) -> bool:
        """Check if position should be stopped out"""
        pass
```

---

### 6. AutoGen Orchestration (`src/orchestration/`)

#### Agent Definitions (`agents.py`)

```python
from autogen import AssistantAgent, UserProxyAgent

def create_market_analyst_agent(openrouter_client):
    """Remote AI agent for market analysis"""
    return AssistantAgent(
        name="MarketAnalyst",
        llm_config={
            "model": "x-ai/grok-4",
            "api_key": openrouter_api_key,
            "base_url": "https://openrouter.ai/api/v1"
        },
        system_message="You are a market analyst for LSE trading..."
    )

def create_position_monitor_agent(ollama_client):
    """Local AI agent for position monitoring"""
    return AssistantAgent(
        name="PositionMonitor",
        llm_config={
            "model": "llama3.2:3b",
            "base_url": "http://localhost:11434/v1"
        },
        system_message="You monitor positions using only provided data..."
    )

def create_trading_executor_agent():
    """Agent that executes validated trades"""
    return UserProxyAgent(
        name="TradingExecutor",
        human_input_mode="NEVER",
        code_execution_config=False
    )
```

#### Workflows (`workflows.py`)

```python
class TradingWorkflow:
    """Main trading workflow orchestration"""
    
    async def run_startup_analysis(self):
        """
        Startup workflow:
        1. Initialize database connection
        2. Load existing positions
        3. Run remote AI market analysis
        4. Generate and execute initial trades
        """
        pass
    
    async def run_monitoring_loop(self):
        """
        Continuous monitoring workflow:
        1. Every CHECK_INTERVAL_SECONDS:
           a. For each position, run local AI check
           b. If SELL suggested, escalate to remote AI
           c. If confirmed, execute trade
        2. Log all decisions to database
        """
        pass
    
    async def run_daily_rebalance(self):
        """
        Daily rebalance (e.g., at market open):
        1. Run full remote AI analysis
        2. Identify rebalancing opportunities
        3. Execute trades
        """
        pass
```

---

### 7. Main Entry Point (`src/main.py`)

```python
import asyncio
from src.config import Settings
from src.database import init_db
from src.orchestration import TradingWorkflow

async def main():
    # Load configuration
    settings = Settings()
    
    # Initialize database
    await init_db(settings.database_url)
    
    # Create workflow
    workflow = TradingWorkflow(settings)
    
    # Run startup analysis
    await workflow.run_startup_analysis()
    
    # Start monitoring loop
    await workflow.run_monitoring_loop()

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Implementation Order

### Phase 1: Foundation (Days 1-2)

1. **Project setup**: Create directory structure, `requirements.txt`, config system
2. **Database layer**: Models, migrations, repository
3. **Market data fetcher**: Yahoo Finance integration for LSE

### Phase 2: AI Integration (Days 3-4)

4. **Ollama client**: Local AI queries with structured prompts
2. **OpenRouter client**: Remote AI with proper API integration
3. **Decision engine**: Logic for routing decisions between local/remote AI

### Phase 3: Trading Logic (Days 5-6)

7. **Paper trader**: Simulated trading implementation
2. **Position manager**: Track and update positions
3. **Risk manager**: Enforce trading limits

### Phase 4: Orchestration (Days 7-8)

10. **AutoGen agents**: Configure agent definitions
2. **Workflows**: Implement startup analysis and monitoring loop
3. **Main entry point**: Wire everything together

### Phase 5: Testing & Polish (Days 9-10)

13. **Unit tests**: Test individual components
2. **Integration tests**: Test full workflows
3. **Documentation**: README, usage instructions

---

## Dependencies (`requirements.txt`)

```
# Core
python>=3.10
asyncio
pydantic>=2.0
pydantic-settings
pyyaml

# Database
sqlalchemy>=2.0
alembic
aiosqlite

# Market Data
yfinance
pandas
numpy

# AI
autogen-agentchat>=0.2
ollama
httpx
openai  # For OpenRouter compatibility

# Technical Analysis
ta-lib  # Or pandas-ta if ta-lib install is problematic
pandas-ta

# Utilities
python-dotenv
structlog
schedule
```

---

## Environment Variables (`.env.example`)

```bash
# Required
OPENROUTER_API_KEY=your_openrouter_api_key

# Optional (defaults shown)
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3.2:3b
OPENROUTER_MODEL=x-ai/grok-4
DATABASE_URL=sqlite:///trading.db
TRADING_MODE=paper
CHECK_INTERVAL_SECONDS=300
INITIAL_BALANCE=10000
```

---

## Verification Plan

### Automated Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html

# Run specific test modules
pytest tests/test_database.py -v
pytest tests/test_ai.py -v
pytest tests/test_trading.py -v
```

**Test Coverage:**

1. **Database Tests** (`test_database.py`)
   - Create/read/update/delete operations for all models
   - Repository pattern functionality
   - Migration tests

2. **Market Data Tests** (`test_market.py`)
   - Mock Yahoo Finance responses
   - LSE symbol handling (`.L` suffix)
   - Market hours detection
   - GBp to GBP conversion

3. **AI Tests** (`test_ai.py`)
   - Mock Ollama responses
   - Mock OpenRouter responses
   - Decision escalation logic
   - Prompt formatting

4. **Trading Tests** (`test_trading.py`)
   - Paper trading buy/sell execution
   - Position tracking
   - Risk limit enforcement
   - Stop loss/take profit triggers

5. **Orchestration Tests** (`test_orchestration.py`)
   - Agent creation
   - Workflow execution (mocked AIs)
   - Full integration test with paper trading

### Manual Verification

1. **Ollama Setup Verification**

   ```bash
   # Verify Ollama is running
   curl http://localhost:11434/api/tags
   
   # Verify llama3.2:3b is available
   ollama list
   
   # Test model response
   ollama run llama3.2:3b "Say hello"
   ```

2. **OpenRouter API Verification**

   ```bash
   # Test API key validity
   curl https://openrouter.ai/api/v1/models \
     -H "Authorization: Bearer $OPENROUTER_API_KEY"
   ```

3. **Market Data Verification**

   ```python
   # Test script to verify LSE data
   import yfinance as yf
   ticker = yf.Ticker("LLOY.L")  # Lloyds Banking Group
   print(ticker.info)
   print(ticker.history(period="5d"))
   ```

4. **Full System Test (Paper Trading)**

   ```bash
   # Start the bot with paper trading
   python -m src.main
   
   # Observe:
   # - Startup analysis runs
   # - Initial trades are logged
   # - Monitoring loop starts
   # - Positions are checked at intervals
   ```

---

## Error Handling & Edge Cases

1. **API Rate Limits**: Implement exponential backoff for all API calls
2. **Market Closed**: Detect when LSE is closed, pause trading operations
3. **AI Unavailable**: Fall back gracefully if Ollama/OpenRouter are unreachable
4. **Database Corruption**: Regular backups, transaction rollback on errors
5. **Network Issues**: Retry logic with circuit breaker pattern

---

## Future Enhancements (Out of Scope)

- Live trading with real broker integration
- Web dashboard for monitoring
- Telegram/Discord notifications
- Portfolio optimization algorithms
- Backtesting framework
- Multi-exchange support
