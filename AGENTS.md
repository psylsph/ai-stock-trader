# AGENTS.md - Guidelines for Agentic Coding

## IMPORTANT: Mandatory Code Quality Checks

**YOU MUST ALWAYS RUN LINTER AND ALL TESTS AFTER YOU DO ANY UPDATES**

Before completing any work, you MUST:
1. Run pylint on all source and test files
2. Run mypy for type checking
3. Run ALL tests (not just a subset)
4. Fix any failures before reporting completion
5. Update the DESIGN.md to match any design changes (ask user first)

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

# Run specific test file
pytest tests/test_database.py

# Run with coverage
pytest --cov=src --cov-report=term-missing
```

### Running the Application
```bash
# Run main bot (paper trading mode)
python -m src.main

# Run with database reset
python -m src.main --restart

# Start with web dashboard
python -m src.main --web
```

## Code Style Guidelines

### Imports
- Order: standard library → third-party → local imports
- Group imports with blank lines between groups
- Use absolute imports (e.g., `from src.config.settings import settings`)

### Type Hints & Naming
- Required for all function signatures
- Use `Optional[T]` instead of `T | None`
- Use `Dict[str, Any]`, `List[T]` for collections
- Classes: `PascalCase`, Functions/Variables: `snake_case`, Constants: `UPPER_SNAKE_CASE`

```python
async def analyze_position(
    symbol: str,
    price: float,
    indicators: Dict[str, Any]
) -> Dict[str, Any]:
    ...
```

### Async Patterns
- All database operations and external API calls must be async
- Use `async with` for context managers (sessions, HTTP clients)
- Use `asyncio.gather()` for parallel independent tasks

### Error Handling
- Use specific exceptions where possible
- For broad exceptions, use `# pylint: disable=broad-except`
- Log errors with `exc_info=True`
- Provide fallback responses for AI failures

```python
try:
    response = await self.api_call()
except Exception as e:  # pylint: disable=broad-except
    logger.error("API call failed: %s", e, exc_info=True)
    return {"decision": "HOLD", "confidence": 0.0}
```

### Database (SQLAlchemy 2.0+)
- Use `Mapped[T]` and `mapped_column()`
- Use async session maker pattern
- Always use `select()` with `execute()`

```python
class Stock(Base):
    __tablename__ = "stocks"
    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String, unique=True, index=True)
```

### Pydantic & Configuration
- Use `pydantic-settings.BaseSettings`
- Define `model_config = SettingsConfigDict(env_file=".env", extra="ignore")`

### Documentation & Comments
- Docstrings with `"""triple quotes"""` for all public members
- Describe params and return values
- Keep comments minimal; use `# TODO:` for future work
- Comment complex business logic only

### Testing
- Use `@pytest.mark.asyncio` and `@pytest_asyncio.fixture`
- Mock external dependencies (AI APIs, Market Data)
- Use in-memory SQLite for database tests: `sqlite+aiosqlite:///:memory:`

### Project Structure
- `src/ai/`: AI clients (Local, OpenRouter) and decision engine
- `src/config/`: Application settings and web mode configuration
- `src/database/`: SQLAlchemy models, repository pattern, and migrations
- `src/market/`: Data fetchers (Market prices, news, charts)
- `src/trading/`: Paper trader, position/risk managers, and pre-screening
- `src/orchestration/`: Workflow logic and agent coordination
- `src/web/`: FastAPI dashboard, templates, and web-specific logic
- `tests/`: Pytest suite covering unit and integration tests

### Trading Specifics
- **LSE Symbol format:** Always use `.L` suffix (e.g., `LLOY.L`, `TSCO.L`)
- **Market hours:** 08:00 - 16:30 GMT (Monday - Friday)
- **Currency:** Project uses GBP. Convert pence (GBp) to pounds: `price / 100`
- **Manual Review:** In 'Live' mode, trades require validation via `remote_validation_decision` in the database.

### Interaction Guidelines
- Be concise and direct in CLI outputs.
- Explain any commands that modify the filesystem or system state.
- Always verify changes with the project-specific build/test/lint commands.
- Do not make assumptions about library availability; check `requirements.txt`.
