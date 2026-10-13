"""Liveness endpoint."""

from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel

from invoice_intake import __version__
from invoice_intake.config import Settings

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str
    environment: str
    export_configured: bool  # is an export webhook set (INVOICE_INTAKE_EXPORT_WEBHOOK_URL)?


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    """Report that the service is up, with its version and environment."""
    settings: Settings = request.app.state.settings
    return HealthResponse(
        status="ok",
        version=__version__,
        environment=settings.environment,
        export_configured=bool(settings.export_webhook_url),
    )
