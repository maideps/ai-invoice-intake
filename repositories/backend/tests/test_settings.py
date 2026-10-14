from pathlib import Path

import pytest
from pydantic import ValidationError

from invoice_intake.config import get_settings

from .helpers import IsolatedSettings


def test_defaults() -> None:
    settings = IsolatedSettings()

    assert settings.app_name == "AI Invoice Intake"
    assert settings.environment == "development"
    assert settings.log_level == "INFO"


def test_environment_variables_override_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INVOICE_INTAKE_ENVIRONMENT", "production")
    monkeypatch.setenv("INVOICE_INTAKE_LOG_LEVEL", "DEBUG")

    settings = IsolatedSettings()

    assert settings.environment == "production"
    assert settings.log_level == "DEBUG"


def test_invalid_environment_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INVOICE_INTAKE_ENVIRONMENT", "staging")

    with pytest.raises(ValidationError):
        IsolatedSettings()


def test_get_settings_is_cached() -> None:
    get_settings.cache_clear()

    assert get_settings() is get_settings()


def test_the_default_samples_folder_is_found_wherever_the_package_sits() -> None:
    # Found by searching upwards for samples/, not by counting folder levels: the package also
    # runs from site-packages and, under Alembic in the image, from /app/src.
    repository_samples = Path(__file__).resolve().parents[3] / "samples" / "invoices"

    assert IsolatedSettings().fake_samples_dir == repository_samples
    assert len(list(repository_samples.glob("*.pdf"))) == 12
