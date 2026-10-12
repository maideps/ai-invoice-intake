"""Application factory and ASGI entry point.

This is the composition root: the only module that connects the API to infrastructure.
"""

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timezone

from fastapi import FastAPI

from invoice_intake import __version__
from invoice_intake.api.health import router as health_router
from invoice_intake.api.invoices import router as invoices_router
from invoice_intake.config import Settings, get_settings
from invoice_intake.infrastructure.database import make_engine, make_session_factory
from invoice_intake.infrastructure.repository import SqlInvoiceRepository
from invoice_intake.services.intake import IntakeService, IntakeServiceFactory


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def create_app(
    settings: Settings | None = None, *, intake_service: IntakeServiceFactory | None = None
) -> FastAPI:
    """Build the app. Tests pass explicit settings, or their own service factory."""
    resolved = settings if settings is not None else get_settings()
    engine = make_engine(resolved.database_url)  # connects lazily, on first use
    sessions = make_session_factory(engine)

    @contextmanager
    def sql_intake_service() -> Iterator[IntakeService]:
        with sessions.begin() as session:  # commits on success, rolls back on error
            yield IntakeService(
                SqlInvoiceRepository(session),
                clock=utc_now,
                max_upload_bytes=resolved.max_upload_bytes,
            )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        engine.dispose()

    app = FastAPI(title=resolved.app_name, version=__version__, lifespan=lifespan)
    app.state.settings = resolved
    app.state.intake_service = intake_service or sql_intake_service
    app.include_router(health_router)
    app.include_router(invoices_router)
    return app


app = create_app()
