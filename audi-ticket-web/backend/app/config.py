import os
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # App
    app_name: str = "Audi Ticket Bot"
    debug: bool = False
    
    # Auth - Simple shared password
    app_password: str = "changeme"
    secret_key: str = "your-secret-key-change-in-production"
    
    # Database
    database_url: str = "sqlite:///./data/tickets.db"
    
    # Discord
    discord_webhook_url: str = ""
    
    # Bot Settings
    default_scan_interval: float = 0.1  # seconds
    cart_hold_time: int = 1020  # 17 minutes in seconds
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Cached settings instance."""
    return Settings()
