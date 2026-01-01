"""Configuration settings for the AI Stock Trader application."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # AI Configuration
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = "x-ai/grok-4"

    # LM Studio Configuration
    LM_STUDIO_API_URL: str = "http://localhost:1234/v1"
    LM_STUDIO_MODEL: str = "mistralai/ministral-3-14b-reasoning"
    ENABLE_TOOLS: bool = True
    ENABLE_VISION: bool = True
    REMOTE_ONLY_MODE: bool = False  # Skip local AI, use remote AI directly

    # Streaming & Retry Configuration
    USE_STREAMING: bool = True
    AI_MAX_RETRIES: int = 3
    AI_RETRY_DELAY_SECONDS: float = 1.0

    # Database Configuration
    DATABASE_URL: str = "sqlite+aiosqlite:///trading.db"

    # Trading Configuration
    TRADING_MODE: str = "paper"  # "paper" or "live"
    IGNORE_MARKET_HOURS: bool = False
    CHECK_INTERVAL_SECONDS: int = 300
    INITIAL_BALANCE: float = 10000.0
    MAX_POSITIONS: int = 5  # Maximum number of open positions
    MAX_POSITION_SIZE_PCT: float = 0.20  # Max size of a single position (20%)

    # Market Data
    RSS_FEEDS: list[str] = [
        "https://news.yahoo.com/rss/uk",
        "https://finance.yahoo.com/news/rssindex",
        "https://feeds.bbci.co.uk/news/uk/rss.xml",
        "https://feeds.bbci.co.uk/news/business/rss.xml"
    ]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
