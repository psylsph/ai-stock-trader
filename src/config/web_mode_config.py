"""Web mode configuration for AI Stock Trader application."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class WebModeSettings(BaseSettings):
    """Web mode configuration settings."""

    is_web_mode: bool = False
    """Whether the application is running in web server mode."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


web_mode = WebModeSettings()
