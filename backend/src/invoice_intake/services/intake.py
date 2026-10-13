"""Use cases for taking invoices in and reading them back."""

from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import datetime
from uuid import UUID

from invoice_intake.domain import (
    Actor,
    Document,
    Invoice,
    InvoicePage,
    InvoiceRepository,
    InvoiceStatus,
)

from .queue import ExtractionQueue

# Accepted uploads, recognised by their first bytes; the client's content type is not trusted.
SIGNATURES: tuple[tuple[bytes, str], ...] = (
    (b"%PDF-", "application/pdf"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
)
MAX_FILENAME_LENGTH = 255


class UploadRejectedError(Exception):
    """The upload cannot become an invoice."""


class EmptyUploadError(UploadRejectedError):
    pass


class UploadTooLargeError(UploadRejectedError):
    pass


class UnsupportedFileTypeError(UploadRejectedError):
    pass


class InvoiceNotFoundError(LookupError):
    pass


def detect_content_type(content: bytes) -> str | None:
    return next((kind for magic, kind in SIGNATURES if content.startswith(magic)), None)


def clean_filename(raw: str | None) -> str:
    """Keep only the last path component, trimmed and length-limited."""
    name = (raw or "").replace("\\", "/").rsplit("/", 1)[-1].strip()
    return name[:MAX_FILENAME_LENGTH] or "unnamed"


class IntakeService:
    def __init__(
        self,
        invoices: InvoiceRepository,
        queue: ExtractionQueue,
        *,
        clock: Callable[[], datetime],
        max_upload_bytes: int,
    ) -> None:
        self._invoices = invoices
        self._queue = queue
        self._clock = clock
        self._max_upload_bytes = max_upload_bytes

    def upload(self, *, filename: str | None, content: bytes, uploaded_by: Actor) -> Invoice:
        """Validate the file, store it as a new invoice in ``uploaded`` status, and queue it
        for extraction."""
        if not content:
            raise EmptyUploadError("the file is empty")
        if len(content) > self._max_upload_bytes:
            raise UploadTooLargeError(f"the file is larger than {self._max_upload_bytes} bytes")
        content_type = detect_content_type(content)
        if content_type is None:
            raise UnsupportedFileTypeError("only PDF, PNG and JPEG files are accepted")

        invoice = Invoice(
            filename=clean_filename(filename), uploaded_by=uploaded_by, uploaded_at=self._clock()
        )
        self._invoices.add(invoice, Document(content_type=content_type, content=content))
        self._queue.enqueue(invoice.id)
        return invoice

    def get(self, invoice_id: UUID) -> Invoice:
        invoice = self._invoices.get(invoice_id)
        if invoice is None:
            raise InvoiceNotFoundError(f"invoice {invoice_id} not found")
        return invoice

    def list_page(self, *, status: InvoiceStatus | None, limit: int, offset: int) -> InvoicePage:
        return self._invoices.list_page(status=status, limit=limit, offset=offset)

    def document(self, invoice_id: UUID) -> Document:
        document = self._invoices.get_document(invoice_id)
        if document is None:
            raise InvoiceNotFoundError(f"invoice {invoice_id} not found")
        return document


# Builds a service whose changes are committed when the context exits without an error.
IntakeServiceFactory = Callable[[], AbstractContextManager[IntakeService]]
