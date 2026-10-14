"""Request-scoped dependencies. The composition root (``main.py``) decides what they return."""

from collections.abc import Callable, Iterator
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, Request

from invoice_intake.domain import Account, Permission
from invoice_intake.services.accounts import AccountService, AccountServiceFactory
from invoice_intake.services.export import ExportService, ExportServiceFactory
from invoice_intake.services.extraction import ExtractionService, ExtractionServiceFactory
from invoice_intake.services.intake import IntakeService, IntakeServiceFactory
from invoice_intake.services.review import ReviewService, ReviewServiceFactory

SESSION_COOKIE = "invoice_intake_session"


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


def account_service(request: Request) -> Iterator[AccountService]:
    factory: AccountServiceFactory = request.app.state.account_service
    with factory() as service:
        yield service


def signed_in(
    request: Request,
    session: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> Account:
    """The account behind the session cookie; 401 without a valid session.

    Looked up in its own short transaction, before the request's service starts.
    """
    factory: AccountServiceFactory = request.app.state.account_service
    with factory() as service:
        account = service.account_for_session(session or "")
    if account is None:
        raise HTTPException(status_code=401, detail="sign in first")
    return account


def require(permission: Permission) -> Callable[[Account], Account]:
    """A dependency that lets the request through only if the account's role allows it."""

    def check(account: Annotated[Account, Depends(signed_in)]) -> Account:
        if not account.can(permission):
            raise HTTPException(
                status_code=403,
                detail=f"a {account.role.value} can't do that; ask an admin for another role",
            )
        return account

    return check


# scope="function": the service context (and its commit) closes before the response is sent,
# so a failed commit becomes an error response instead of a success the client already saw.
IntakeServiceDep = Annotated[IntakeService, Depends(intake_service, scope="function")]
ExtractionServiceDep = Annotated[ExtractionService, Depends(extraction_service, scope="function")]
ReviewServiceDep = Annotated[ReviewService, Depends(review_service, scope="function")]
ExportServiceDep = Annotated[ExportService, Depends(export_service, scope="function")]
AccountServiceDep = Annotated[AccountService, Depends(account_service, scope="function")]

# Who may call an endpoint (D-019): every invoice route declares one of these.
Reader = Annotated[Account, Depends(require(Permission.READ))]
Uploader = Annotated[Account, Depends(require(Permission.UPLOAD))]
Reviewer = Annotated[Account, Depends(require(Permission.REVIEW))]
Admin = Annotated[Account, Depends(require(Permission.MANAGE_ACCOUNTS))]
SignedIn = Annotated[Account, Depends(signed_in)]
