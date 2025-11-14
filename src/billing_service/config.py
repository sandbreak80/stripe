"""Configuration management using Pydantic Settings."""

import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    # Database
    database_url: str = os.getenv(
        "DATABASE_URL", "postgresql://billing_user:billing_pass@postgres:5432/billing_db"
    )

    # Redis
    redis_url: str = os.getenv("REDIS_URL", "redis://redis:6379/0")

    # Stripe
    stripe_secret_key: str = os.getenv(
        "STRIPE_SECRET_KEY",
        "",  # Must be set via environment variable
    )
    stripe_publishable_key: str = os.getenv(
        "STRIPE_PUBLISHABLE_KEY",
        "",  # Must be set via environment variable
    )
    stripe_webhook_secret: str | None = os.getenv("STRIPE_WEBHOOK_SECRET")

    # API Keys
    admin_api_key: str | None = os.getenv("ADMIN_API_KEY")

    # Application
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    environment: str = os.getenv("ENVIRONMENT", "development")

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)


settings = Settings()
