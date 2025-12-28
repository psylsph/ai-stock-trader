from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    # AI Configuration
    OPENROUTER_API_KEY: str
    OPENROUTER_MODEL: str = "x-ai/grok-4"
    OLLAMA_HOST: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2:3b"
    
    # Database Configuration
    DATABASE_URL: str = "sqlite+aiosqlite:///trading.db"
    
    # Trading Configuration
    TRADING_MODE: str = "paper"  # "paper" or "live"
    CHECK_INTERVAL_SECONDS: int = 300
    INITIAL_BALANCE: float = 10000.0
    
    # Market Data
    MARKET_DATA_API_KEY: Optional[str] = None
    RSS_FEEDS: list[str] = [
        "https://www.ft.com/rss/home/international",
        "https://money.com/money/feed/"
    ]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
