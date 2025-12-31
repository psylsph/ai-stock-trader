# AGENTS.md - Guidelines for Agentic Coding

## IMPORTANT: Mandatory Code Quality Checks

**YOU MUST ALWAYS RUN LINTER AND ALL TESTS AFTER YOU DO ANY UPDATES**

Before completing any work, you MUST:
1. Run pylint on all source and test files
2. Run mypy for type checking
3. Run ALL tests (not just a subset)
4. Fix any failures before reporting completion
5. Update the DESIGN.md to match any design changes, the user MUST be asked if the design is to be updated.

```bash
# Run linter
.venv/bin/pylint src/ tests/ --max-line-length=120 --disable=C0114,C0115,C0116

# Run type checker
mypy src/ tests/

# Run ALL tests
python -m pytest tests/ -v
```

## Build/Lint/Test Commands

### Running Tests
```bash
# Run all tests
pytest

# Run single test
pytest tests/test_database.py::test_create_stock

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_database.py
pytest tests/test_trading.py

# Run with coverage (if coverage.py is installed)
pytest --cov=src --cov-report=html
```

### Running the Application
```bash
# Run main bot (paper trading mode)
python -m src.main

# Run with database reset
python -m src.main --restart

# Run verification scripts
python verify_av.py    # Verify Alpha Vantage connection
python verify_news.py  # Verify news fetching
```

## Code Style Guidelines

### Imports
- Order: standard library → third-party → local imports
- Group imports with blank lines between groups
- Use `from typing import ...` for type hints
- Prefer absolute imports over relative imports

```python
# Correct order
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional

import aiohttp
from sqlalchemy import select

from src.config import settings
from src.database.models import Stock
```

### Type Hints
- Required for all function signatures
- Use `Optional[T]` instead of `T | None` for compatibility
- Use `Dict[str, Any]`, `List[T]` instead of `dict[str, any]`
- Specify return types explicitly

```python
async def analyze_position(
    symbol: str,
    entry_price: float,
    indicators: Dict[str, Any]
) -> Dict[str, Any]:
    ...
```

### Naming Conventions
- Classes: `PascalCase` (e.g., `TradingDecisionEngine`, `MarketDataFetcher`)
- Functions/variables: `snake_case` (e.g., `get_positions`, `current_price`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `MAX_POSITION_PCT`)
- Private members: `_leading_underscore`
- Database models: `PascalCase` but tables use `snake_case`

### Async Patterns
- All database operations and external API calls must be async
- Use `async def` for all async functions
- Use `async with` for context managers (database sessions, HTTP clients)
- Return types should specify the type, not just `Coroutine`

```python
async def get_quote(self, symbol: str) -> Quote:
    async with aiohttp.ClientSession() as session:
        ...
```

### Error Handling
- Use specific exceptions where possible (`ValueError`, `KeyError`)
- For broad exception handling in production code, use `# pylint: disable=broad-except`
- Log errors with `exc_info=True` for debugging
- Provide fallback responses for external AI failures

```python
try:
    response = await self.api_call()
except Exception as e:  # pylint: disable=broad-except
    logger.error("API call failed", exc_info=True)
    return {"decision": "HOLD", "confidence": 0.0}
```

### Database (SQLAlchemy 2.0+)
- Use `Mapped[T]` type hints for columns
- Use `mapped_column()` instead of `Column()`
- Use async session maker pattern
- Always use `select()` with `execute()`

```python
class Stock(Base):
    __tablename__ = "stocks"
    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String, unique=True, index=True)
```

### Pydantic/Configuration
- Use `pydantic-settings.BaseSettings` for configuration
- Use `model_config = SettingsConfigDict(...)` for settings config
- Mark optional fields with `Optional[T]`
- Default values can be provided directly

### Documentation
- Docstrings with `"""triple quotes"""` for all public classes and methods
- Describe parameters and return values
- Keep descriptions concise but informative

```python
async def analyze_position(self, symbol: str, price: float) -> Dict[str, Any]:
    """
    Analyze a trading position using AI.

    Args:
        symbol: The stock symbol to analyze.
        price: Current market price.

    Returns:
        Dictionary containing decision, reasoning, and confidence score.
    """
```

### Testing
- Use `@pytest.mark.asyncio` for async test functions
- Use `@pytest_asyncio.fixture` for async fixtures
- Mock external dependencies (ollama, openrouter, APIs)
- Use `AsyncMock` for mocking async methods
- Use in-memory SQLite for database tests (`sqlite+aiosqlite:///:memory:`)

```python
@pytest.mark.asyncio
async def test_paper_buy():
    repo = MockRepo()
    fetcher = MockFetcher()
    trader = PaperTrader(repo, fetcher, initial_balance=1000.0)
    ...
```

### Project Structure
- `src/ai/`: AI clients and decision engine
- `src/database/`: Models and repository pattern
- `src/market/`: Data fetchers and news
- `src/trading/`: Paper trader, position/risk managers
- `src/orchestration/`: Workflows and agents

### Linting (if added in future)
- If black is configured: format with `black src/`
- If ruff is configured: lint with `ruff check src/`
- If mypy is configured: type check with `mypy src/`

### Common Patterns
- Use `datetime.utcnow()` for database timestamps
- Use LSE symbol format: `SYMBOL.L` (e.g., `LLOY.L`)
- Market hours: 8:00 AM - 4:30 PM GMT
- All currency values in GBP (convert GBp to GBP when needed)

### Comments
- Use `# TODO:` for future work items
- Keep comments minimal, let code be self-documenting
- Comment complex business logic only
- Use `# pylint: disable=...` for justified lint exceptions
