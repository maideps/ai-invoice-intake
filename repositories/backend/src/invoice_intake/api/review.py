"""Human review endpoints: correct fields, approve, reject. Every call is audited.

Each request sends the invoice ``version`` the reviewer last saw; a stale version is a 409.
Validation problems are a 422 whose ``detail`` is ``{"message": ..., "errors": [...]}``.
"""

from collections.abc import Callable
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException

from invoice_intake.domain import (
    ActorNotPermittedError,
    ApprovalBlockedError,
    ConcurrentModificationError,
    FieldValuesError,
    InvalidInvoiceDataError,
    InvalidTransitionError,
    Invoice,
)
from invoice_intake.services.intake import InvoiceNotFoundError
from invoice_intake.services.review import VersionConflictError

from .dependencies import CurrentUser, ReviewServiceDep
from .schemas import ApproveIn, EditFieldsIn, InvoiceOut, ProblemOut, RejectIn

router = APIRouter(prefix="/invoices", tags=["review"])

_ERRORS: dict[int | str, dict[str, Any]] = {
    404: {"description": "Unknown invoice"},
    409: {"description": "Stale version, or the invoice is not in needs_review"},
    422: {"model": ProblemOut, "description": "Invalid values, or a decision rule not met"},
}


@router.patch("/{invoice_id}/fields", response_model=InvoiceOut, responses=_ERRORS)
def edit_fields(
    invoice_id: UUID, body: EditFieldsIn, service: ReviewServiceDep, user: CurrentUser
) -> InvoiceOut:
    """Correct extracted values. Only the fields sent change; each change is audited with
    its old and new value. Sending values equal to the current ones records nothing."""
    return _handle(
        lambda: service.edit_fields(
            invoice_id, version=body.version, patch=body.fields, reviewer=user
        )
    )


@router.post("/{invoice_id}/approve", response_model=InvoiceOut, responses=_ERRORS)
def approve(
    invoice_id: UUID, body: ApproveIn, service: ReviewServiceDep, user: CurrentUser
) -> InvoiceOut:
    """Approve for export. Needs vendor name, invoice number, issue date, currency and total."""
    return _handle(lambda: service.approve(invoice_id, version=body.version, reviewer=user))


@router.post("/{invoice_id}/reject", response_model=InvoiceOut, responses=_ERRORS)
def reject(
    invoice_id: UUID, body: RejectIn, service: ReviewServiceDep, user: CurrentUser
) -> InvoiceOut:
    """Reject with a reason. Rejected invoices are final."""
    return _handle(
        lambda: service.reject(invoice_id, version=body.version, reviewer=user, reason=body.reason)
    )


def _handle(call: Callable[[], Invoice]) -> InvoiceOut:
    try:
        return InvoiceOut.of(call())
    except InvoiceNotFoundError as error:
        raise HTTPException(404, str(error)) from error
    except (VersionConflictError, InvalidTransitionError, ConcurrentModificationError) as error:
        raise HTTPException(409, str(error)) from error
    except ActorNotPermittedError as error:
        raise HTTPException(403, str(error)) from error
    except FieldValuesError as error:
        raise _problem("invalid field values", error.errors) from error
    except ApprovalBlockedError as error:
        raise _problem("cannot approve until these fields are filled", error.missing) from error
    except InvalidInvoiceDataError as error:  # e.g. a rejection without a reason
        raise _problem(str(error), [str(error)]) from error


def _problem(message: str, errors: list[str]) -> HTTPException:
    return HTTPException(422, ProblemOut(message=message, errors=errors).model_dump())
