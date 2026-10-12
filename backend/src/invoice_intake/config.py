"""Typed application settings, read from ``INVOICE_INTAKE_*`` environment variables."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Secrets belong in the environment, never in the repository."""

    model_config = SettingsConfigDict(
        env_prefix="INVOICE_INTAKE_",
        env_file=".env",
        extra="ignore",
    )

    app_name: str = "AI Invoice Intake"
    environment: Literal["development", "test", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    # Port 5433 so a local development database does not clash with a PostgreSQL on 5432.
    database_url: str = (
        "postgresql+psycopg://invoice_intake:invoice_intake@localhost:5433/invoice_intake"
    )
    max_upload_bytes: int = Field(default=10 * 1024 * 1024, gt=0)


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings, created once on first use."""
    return Settings()
