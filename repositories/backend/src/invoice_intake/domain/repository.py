"""Storage interface for invoices. Infrastructure implements it; the domain and services use it."""

import hashlib
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from .errors import InvalidInvoiceDataError
from .invoice import Invoice
from .status import InvoiceStatus


@dataclass(frozen=True)
class Document:
    """The original uploaded file."""

    content_type: str
    content: bytes

    def __post_init__(self) -> None:
        if not self.content:
            raise InvalidInvoiceDataError("a document must not be empty")

    @property
    def size(self) -> int:
        return len(self.content)

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.content).hexdigest()


@dataclass(frozen=True)
class InvoicePage:
    items: tuple[Invoice, ...]
    total: int


class InvoiceRepository(Protocol):
    def add(self, invoice: Invoice, document: Document) -> None:
        """Store a new invoice, its audit trail so far and its original document."""

    def get(self, invoice_id: UUID) -> Invoice | None: ...

    def list_page(self, *, status: InvoiceStatus | None, limit: int, offset: int) -> InvoicePage:
        """Invoices newest first, optionally only those in ``status``."""
        ...

    def save(self, invoice: Invoice) -> None:
        """Store status and field changes and append new audit events; never rewrite old ones.

        Raises ``ConcurrentModificationError`` if the stored trail moved on since ``invoice``
        was loaded.
        """

    def get_document(self, invoice_id: UUID) -> Document | None: ...

    def count_by_status(self) -> dict[InvoiceStatus, int]:
        """How many invoices are in each status (statuses with none may be left out)."""
        ...
