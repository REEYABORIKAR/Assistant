import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent
ENV_PATH = BASE_DIR / ".env"


class Settings(BaseSettings):
    app_env: str = "development"
    app_name: str = "refyne"
    log_level: str = "INFO"
    database_url: str = "postgresql+psycopg://postgres:Dp%401412@localhost:5432/refyne"
    redis_url: str | None = "redis://localhost:6379/0"
    access_token_ttl_seconds: int = 900
    refresh_token_ttl_days: int = 30
    password_reset_token_ttl_hours: int = 24
    auth_signing_secret: str = "dev_secret_key_refyne_2026_super_secure_signing_token"
    secret_key: str | None = None
    groq_api_key: str | None = None
    openai_api_key: str | None = None
    claude_api_key: str | None = None

    model_config = SettingsConfigDict(
        env_file=(".env", str(ENV_PATH)),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()

