"""Typed application settings, read from ``INVOICE_INTAKE_*`` environment variables."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


def _samples_home() -> Path:
    """The nearest folder above this file that holds ``samples/``: the repository root in a
    checkout, ``/app`` in the image. Searching rather than counting levels keeps working
    wherever the package sits (a checkout, site-packages, or ``/app/src`` for Alembic)."""
    here = Path(__file__).resolve()
    return next((parent for parent in here.parents if (parent / "samples").is_dir()), here.parent)


SAMPLES_HOME = _samples_home()


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
    # AI extraction (D-005). The default needs no key and no network.
    extraction_provider: str = "fake"
    openai_api_key: SecretStr | None = None
    openai_model: str = "gpt-5.4-mini"
    openai_timeout_seconds: float = Field(default=60.0, gt=0)
    fake_samples_dir: Path = SAMPLES_HOME / "samples" / "invoices"
    # Background extraction (D-010).
    redis_url: str = "redis://localhost:6379/0"
    extraction_max_attempts: int = Field(default=3, ge=1)
    extraction_retry_base_seconds: float = Field(default=5.0, ge=0)
    worker_id: str = "worker"
    worker_sweep_seconds: float = Field(default=60.0, gt=0)
    # Export of approved invoices (feat-010). No URL: export is off and approved invoices wait.
    export_webhook_url: str | None = None
    export_webhook_secret: SecretStr | None = None
    export_max_attempts: int = Field(default=5, ge=1)
    export_retry_base_seconds: float = Field(default=10.0, ge=0)
    export_timeout_seconds: float = Field(default=10.0, gt=0)
    # Sign-in (D-019).
    session_ttl_hours: float = Field(default=12.0, gt=0)
    # Sign-in rate limiting (D-022): this many failures within the window lock a username, or a
    # client address, out until the oldest of them is older than the window.
    sign_in_max_failures: int = Field(default=5, ge=1)
    sign_in_max_failures_per_client: int = Field(default=20, ge=1)
    sign_in_lockout_minutes: float = Field(default=15.0, gt=0)
    # Send the session cookie over HTTPS only; turn on wherever the app is served over HTTPS.
    session_cookie_secure: bool = False
    # List the demo accounts on the sign-in page (the Docker demo). Their passwords are public.
    demo_accounts: bool = False


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings, created once on first use."""
    return Settings()
