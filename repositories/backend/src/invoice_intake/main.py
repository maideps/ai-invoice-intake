"""Application factory and ASGI entry point.

This is the composition root: the only module that connects the API to infrastructure. (The
extraction worker has its own, ``worker.py``.)
"""

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI

from invoice_intake import __version__
from invoice_intake.api.accounts import router as accounts_router
from invoice_intake.api.auth import router as auth_router
from invoice_intake.api.health import router as health_router
from invoice_intake.api.invoices import router as invoices_router
from invoice_intake.api.review import router as review_router
from invoice_intake.config import Settings, get_settings
from invoice_intake.infrastructure.accounts import SqlAccountRepository, SqlSessionRepository
from invoice_intake.infrastructure.database import make_engine, make_session_factory
from invoice_intake.infrastructure.queue import RedisExtractionQueue
from invoice_intake.infrastructure.repository import SqlInvoiceRepository
from invoice_intake.services.accounts import AccountService, AccountServiceFactory
from invoice_intake.services.export import ExportService, ExportServiceFactory
from invoice_intake.services.extraction import ExtractionService, ExtractionServiceFactory
from invoice_intake.services.intake import IntakeService, IntakeServiceFactory
from invoice_intake.services.queue import AfterCommitQueue, ExtractionQueue
from invoice_intake.services.review import ReviewService, ReviewServiceFactory


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def create_app(
    settings: Settings | None = None,
    *,
    intake_service: IntakeServiceFactory | None = None,
    extraction_service: ExtractionServiceFactory | None = None,
    review_service: ReviewServiceFactory | None = None,
    export_service: ExportServiceFactory | None = None,
    account_service: AccountServiceFactory | None = None,
    extraction_queue: ExtractionQueue | None = None,
) -> FastAPI:
    """Build the app. Tests pass explicit settings, their own service factories or queue.

    Extraction itself runs in the worker; the API only queues invoices for it, after the
    transaction that stored them has committed.
    """
    resolved = settings if settings is not None else get_settings()
    queue = extraction_queue or RedisExtractionQueue.from_url(resolved.redis_url)
    engine = make_engine(resolved.database_url)  # connects lazily, on first use
    sessions = make_session_factory(engine)

    @contextmanager
    def sql_intake_service() -> Iterator[IntakeService]:
        pending = AfterCommitQueue()
        with sessions.begin() as session:  # commits on success, rolls back on error
            yield IntakeService(
                SqlInvoiceRepository(session),
                pending,
                clock=utc_now,
                max_upload_bytes=resolved.max_upload_bytes,
            )
        pending.flush_to(queue)  # only reached after a successful commit

    @contextmanager
    def sql_extraction_service() -> Iterator[ExtractionService]:
        pending = AfterCommitQueue()
        with sessions.begin() as session:
            yield ExtractionService(SqlInvoiceRepository(session), pending, clock=utc_now)
        pending.flush_to(queue)

    @contextmanager
    def sql_review_service() -> Iterator[ReviewService]:
        pending = AfterCommitQueue()  # approvals queue an export, after the commit
        with sessions.begin() as session:
            yield ReviewService(SqlInvoiceRepository(session), pending, clock=utc_now)
        pending.flush_to(queue)

    @contextmanager
    def sql_export_service() -> Iterator[ExportService]:
        pending = AfterCommitQueue()
        with sessions.begin() as session:
            yield ExportService(SqlInvoiceRepository(session), pending, clock=utc_now)
        pending.flush_to(queue)

    @contextmanager
    def sql_account_service() -> Iterator[AccountService]:
        with sessions.begin() as session:
            yield AccountService(
                SqlAccountRepository(session),
                SqlSessionRepository(session),
                clock=utc_now,
                session_ttl=timedelta(hours=resolved.session_ttl_hours),
            )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        engine.dispose()

    app = FastAPI(title=resolved.app_name, version=__version__, lifespan=lifespan)
    app.state.settings = resolved
    app.state.intake_service = intake_service or sql_intake_service
    app.state.extraction_service = extraction_service or sql_extraction_service
    app.state.review_service = review_service or sql_review_service
    app.state.export_service = export_service or sql_export_service
    app.state.account_service = account_service or sql_account_service
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(accounts_router)
    app.include_router(invoices_router)
    app.include_router(review_router)
    return app


app = create_app()
