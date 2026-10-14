"""Request-scoped dependencies. The composition root (``main.py``) decides what they return."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Header, Request

from invoice_intake.domain import Actor, ActorKind
from invoice_intake.services.export import ExportService, ExportServiceFactory
from invoice_intake.services.extraction import ExtractionService, ExtractionServiceFactory
from invoice_intake.services.intake import IntakeService, IntakeServiceFactory
from invoice_intake.services.review import ReviewService, ReviewServiceFactory

MAX_ACTOR_NAME = 100


def intake_service(request: Request) -> Iterator[IntakeService]:
    """One service per request; its changes commit only if the request handler succeeds."""
    factory: IntakeServiceFactory = request.app.state.intake_service
    with factory() as service:
        yield service


def extraction_service(request: Request) -> Iterator[ExtractionService]:
    factory: ExtractionServiceFactory = request.app.state.extraction_service
    with factory() as service:
        yield service


def review_service(request: Request) -> Iterator[ReviewService]:
    factory: ReviewServiceFactory = request.app.state.review_service
    with factory() as service:
        yield service


def export_service(request: Request) -> Iterator[ExportService]:
    factory: ExportServiceFactory = request.app.state.export_service
    with factory() as service:
        yield service


def current_user(x_user: Annotated[str | None, Header()] = None) -> Actor:
    """The person acting, from the ``X-User`` header.

    A placeholder until authentication exists (a non-goal for the first version): the header
    is trusted as-is and anyone without it is recorded as ``anonymous``.
    """
    name = (x_user or "").strip()[:MAX_ACTOR_NAME] or "anonymous"
    return Actor(ActorKind.USER, name)


# scope="function": the service context (and its commit) closes before the response is sent,
# so a failed commit becomes an error response instead of a success the client already saw.
IntakeServiceDep = Annotated[IntakeService, Depends(intake_service, scope="function")]
CurrentUser = Annotated[Actor, Depends(current_user)]
ExtractionServiceDep = Annotated[ExtractionService, Depends(extraction_service, scope="function")]
ReviewServiceDep = Annotated[ReviewService, Depends(review_service, scope="function")]
ExportServiceDep = Annotated[ExportService, Depends(export_service, scope="function")]
