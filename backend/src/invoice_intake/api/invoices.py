"""Invoice endpoints: upload, list, fetch, audit trail, original document and extraction.

Handlers are plain functions: FastAPI runs them in a worker thread, so the blocking database
calls do not stall the event loop.
"""

from collections.abc import Callable
from typing import Annotated, TypeVar
from uuid import UUID

from fastapi import APIRouter, File, HTTPException, Query, Request, Response, UploadFile

from invoice_intake.domain import ExtractionProviderError, InvoiceStatus
from invoice_intake.services.extraction import NotExtractableError
from invoice_intake.services.intake import (
    EmptyUploadError,
    InvoiceNotFoundError,
    UnsupportedFileTypeError,
    UploadRejectedError,
    UploadTooLargeError,
)

from .dependencies import CurrentUser, ExtractionServiceDep, IntakeServiceDep
from .schemas import AuditEventOut, ExtractionOut, InvoiceOut, InvoicePageOut

T = TypeVar("T")

router = APIRouter(prefix="/invoices", tags=["invoices"])

_UPLOAD_ERRORS: dict[type[UploadRejectedError], int] = {
    EmptyUploadError: 400,
    UploadTooLargeError: 413,
    UnsupportedFileTypeError: 415,
}


@router.post("", status_code=201, response_model=InvoiceOut)
def upload_invoice(
    request: Request,
    response: Response,
    service: IntakeServiceDep,
    user: CurrentUser,
    file: Annotated[UploadFile, File(description="Invoice as PDF, PNG or JPEG")],
) -> InvoiceOut:
    """Store an uploaded invoice in ``uploaded`` status and record who uploaded it."""
    limit: int = request.app.state.settings.max_upload_bytes
    content = file.file.read(limit + 1)  # one byte over the limit is enough to refuse it
    try:
        invoice = service.upload(filename=file.filename, content=content, uploaded_by=user)
    except UploadRejectedError as error:
        raise HTTPException(_UPLOAD_ERRORS[type(error)], str(error)) from error
    response.headers["Location"] = str(request.url_for("get_invoice", invoice_id=invoice.id))
    return InvoiceOut.of(invoice)


@router.get("", response_model=InvoicePageOut)
def list_invoices(
    service: IntakeServiceDep,
    status: InvoiceStatus | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> InvoicePageOut:
    """Invoices newest first, optionally filtered by status."""
    page = service.list_page(status=status, limit=limit, offset=offset)
    return InvoicePageOut.of(page, limit=limit, offset=offset)


@router.get("/{invoice_id}", response_model=InvoiceOut)
def get_invoice(invoice_id: UUID, service: IntakeServiceDep) -> InvoiceOut:
    return InvoiceOut.of(_found(service.get, invoice_id))


@router.get("/{invoice_id}/events", response_model=list[AuditEventOut])
def get_invoice_events(invoice_id: UUID, service: IntakeServiceDep) -> list[AuditEventOut]:
    """The invoice's audit trail, oldest first."""
    return [AuditEventOut.of(event) for event in _found(service.get, invoice_id).events]


@router.get(
    "/{invoice_id}/document",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}, "image/png": {}, "image/jpeg": {}}}},
)
def get_invoice_document(invoice_id: UUID, service: IntakeServiceDep) -> Response:
    """The original uploaded file, byte for byte."""
    document = _found(service.document, invoice_id)
    return Response(content=document.content, media_type=document.content_type)


@router.post(
    "/{invoice_id}/extract",
    response_model=ExtractionOut,
    responses={
        404: {"description": "Unknown invoice"},
        409: {"description": "The invoice is past extraction"},
        502: {"description": "The extraction provider failed; nothing was recorded"},
    },
)
def extract_invoice(invoice_id: UUID, service: ExtractionServiceDep) -> ExtractionOut:
    """Run AI extraction now. Valid output moves the invoice to ``needs_review``; invalid
    output is recorded in the audit trail (``accepted: false``) and the invoice stays in
    ``extracting``."""
    try:
        outcome = service.extract(invoice_id)
    except InvoiceNotFoundError as error:
        raise HTTPException(404, str(error)) from error
    except NotExtractableError as error:
        raise HTTPException(409, str(error)) from error
    except ExtractionProviderError as error:
        raise HTTPException(502, str(error)) from error
    return ExtractionOut(
        accepted=outcome.accepted,
        errors=list(outcome.errors),
        invoice=InvoiceOut.of(outcome.invoice),
    )


def _found(lookup: Callable[[UUID], T], invoice_id: UUID) -> T:
    try:
        return lookup(invoice_id)
    except InvoiceNotFoundError as error:
        raise HTTPException(404, str(error)) from error
