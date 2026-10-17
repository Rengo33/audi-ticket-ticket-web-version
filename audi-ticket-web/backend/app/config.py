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

    # Web Push (VAPID). Generate once with `python -m scripts.generate_vapid_keys`
    # and paste into the .env. The contact is sent to push services for abuse
    # reports; a plain email works (no mailto: prefix needed, pywebpush adds it).
    vapid_public_key: str = ""
    vapid_private_key: str = ""
    vapid_contact_email: str = ""

    # Base URL for external links (checkout, Discord messages)
    base_url: str = "http://localhost"

    # Upstream Audi site — single source of truth for all bot components
    audi_base_url: str = "https://audidefuehrungen2.regiondo.de"
    audi_host: str = "audidefuehrungen2.regiondo.de"

    # Bot Settings
    default_scan_interval: float = 1.0  # seconds
    cart_hold_time: int = 1020  # 17 minutes in seconds

    # Auto-checkout: use pure-HTTP Stripe confirm path (no Chromium).
    # On any exception the code falls back to the Playwright path, so a regression
    # still ends with a working checkout.
    use_pure_http_confirm: bool = False
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Every default that ships in the repo (pydantic defaults AND docker-compose's
# `${VAR:-default}` fallbacks) — any of them means the secret is public.
_DEFAULT_SECRETS = {
    "secret_key": {"your-secret-key-change-in-production", "change-this-secret"},
    "app_password": {"changeme"},
}


@lru_cache()
def get_settings() -> Settings:
    """Cached settings instance. Refuses to start if required secrets are
    still at their defaults — Fernet card encryption is keyed off SECRET_KEY,
    so booting with the published default would mean every encrypted card in
    the DB is decryptable from the repo source."""
    s = Settings()
    leaked = [k for k, v in _DEFAULT_SECRETS.items() if getattr(s, k) in v]
    if leaked:
        raise RuntimeError(
            f"Refusing to start: {', '.join(leaked)} still at hardcoded default. "
            "Set them via environment variables or .env before deploying."
        )
    return s
