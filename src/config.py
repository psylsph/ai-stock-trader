"""Configuration settings for the AI Stock Trader application."""

from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # AI Configuration
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = "x-ai/grok-4"

    # LM Studio Configuration
    LM_STUDIO_API_URL: str = "http://localhost:1234/v1"
    LM_STUDIO_MODEL: str = "zai-org/GLM-4.6V-Flash"
    ENABLE_TOOLS: bool = True
    ENABLE_VISION: bool = True

    # Database Configuration
    DATABASE_URL: str = "sqlite+aiosqlite:///trading.db"

    # Trading Configuration
    TRADING_MODE: str = "paper"  # "paper" or "live"
    CHECK_INTERVAL_SECONDS: int = 300
    INITIAL_BALANCE: float = 10000.0

    # Market Data
    MARKET_DATA_API_KEY: Optional[str] = None
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
