"""Application configuration."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    database_url: str = "postgresql://billing_user:billing_pass@db:5432/billing_db"
    redis_url: str = "redis://redis:6379/0"
    stripe_secret_key: str = "sk_test_placeholder"
    stripe_webhook_secret: str = "whsec_placeholder"
    environment: str = "development"
    reconciliation_enabled: bool = True
    reconciliation_schedule_hour: int = 2  # Run at 2 AM UTC daily
    reconciliation_days_back: int = 7

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)


settings = Settings()
