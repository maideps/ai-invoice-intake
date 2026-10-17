"""Build the API app and run extraction against a test database, without a real Redis."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from invoice_intake.domain import Account, ExtractionProvider, Role
from invoice_intake.infrastructure.accounts import SqlAccountRepository, SqlSessionRepository
from invoice_intake.infrastructure.database import make_session_factory
from invoice_intake.infrastructure.extraction import FakeExtractionProvider
from invoice_intake.infrastructure.repository import SqlInvoiceRepository
from invoice_intake.main import create_app
from invoice_intake.services.accounts import AccountService
from invoice_intake.services.extraction import (
    AttemptOutcome,
    ExtractionRunner,
    ExtractionService,
)

from .fakes import RecordingQueue
from .helpers import IsolatedSettings

SAMPLES = Path(__file__).resolve().parents[3] / "samples" / "invoices"


def database_url(engine: Engine) -> str:
    return engine.url.render_as_string(hide_password=False)


def make_app(engine: Engine, queue: RecordingQueue | None = None, **settings: Any) -> FastAPI:
    """The real app on the test database; queued invoices go to ``queue``, not Redis."""
    resolved = IsolatedSettings(environment="test", database_url=database_url(engine), **settings)
    return create_app(resolved, extraction_queue=queue or RecordingQueue())


def extract_now(
    engine: Engine,
    invoice_id: UUID,
    *,
    attempt: int = 1,
    max_attempts: int = 3,
    provider: ExtractionProvider | None = None,
) -> AttemptOutcome:
    """Run one extraction attempt the way the worker does (default: the fake provider)."""
    sessions = make_session_factory(engine)

    @contextmanager
    def services() -> Iterator[ExtractionService]:
        with sessions.begin() as session:
            yield ExtractionService(
                SqlInvoiceRepository(session),
                RecordingQueue(),
                clock=lambda: datetime.now(timezone.utc),
            )

    runner = ExtractionRunner(
        services, provider or FakeExtractionProvider(SAMPLES), max_attempts=max_attempts
    )
    return runner.run(invoice_id, attempt)


# Signing in (D-019)

TEST_PASSWORD = "correct horse battery"
# Production hashing takes tens of milliseconds by design; tests use a cheap cost instead.
FAST_PASSWORD_COST = 2**4


def add_account(engine: Engine, username: str = "maide", role: Role = Role.REVIEWER) -> Account:
    """Store an account with TEST_PASSWORD, directly in the test database (or return the
    existing one with that username)."""
    with make_session_factory(engine).begin() as session:
        existing = SqlAccountRepository(session).get_by_username(username)
        if existing is not None:
            return existing
        service = AccountService(
            SqlAccountRepository(session),
            SqlSessionRepository(session),
            clock=lambda: datetime.now(timezone.utc),
            session_ttl=timedelta(hours=1),
            password_cost=FAST_PASSWORD_COST,
        )
        return service.create_account(
            username=username, display_name=username.title(), role=role, password=TEST_PASSWORD
        )


def sign_in(
    client: TestClient, engine: Engine, username: str = "maide", role: Role = Role.REVIEWER
) -> Account:
    """Create the account and sign the client in as it; the client keeps the session cookie."""
    account = add_account(engine, username, role)
    response = client.post("/auth/sign-in", json={"username": username, "password": TEST_PASSWORD})
    assert response.status_code == 200, response.text
    return account
