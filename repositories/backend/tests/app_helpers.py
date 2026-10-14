"""Build the API app and run extraction against a test database, without a real Redis."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import FastAPI
from sqlalchemy import Engine

from invoice_intake.domain import ExtractionProvider
from invoice_intake.infrastructure.database import make_session_factory
from invoice_intake.infrastructure.extraction import FakeExtractionProvider
from invoice_intake.infrastructure.repository import SqlInvoiceRepository
from invoice_intake.main import create_app
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
