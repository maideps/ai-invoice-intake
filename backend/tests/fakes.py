"""In-memory stand-ins for infrastructure, for tests that do not need PostgreSQL."""

from uuid import UUID

from invoice_intake.domain import (
    ConcurrentModificationError,
    Document,
    Invoice,
    InvoicePage,
    InvoiceStatus,
)


class InMemoryInvoiceRepository:
    """Follows the ``InvoiceRepository`` contract, including append-only events."""

    def __init__(self) -> None:
        self.invoices: dict[UUID, Invoice] = {}
        self.documents: dict[UUID, Document] = {}
        self._stored_events: dict[UUID, int] = {}

    def add(self, invoice: Invoice, document: Document) -> None:
        if invoice.id in self.invoices:
            raise ValueError(f"invoice {invoice.id} already exists")
        self.invoices[invoice.id] = invoice
        self.documents[invoice.id] = document
        self._stored_events[invoice.id] = len(invoice.events)

    def get(self, invoice_id: UUID) -> Invoice | None:
        return self.invoices.get(invoice_id)

    def list_page(self, *, status: InvoiceStatus | None, limit: int, offset: int) -> InvoicePage:
        matching = [i for i in self.invoices.values() if status is None or i.status is status]
        matching.sort(key=lambda invoice: (invoice.uploaded_at, invoice.id), reverse=True)
        return InvoicePage(items=tuple(matching[offset : offset + limit]), total=len(matching))

    def save(self, invoice: Invoice) -> None:
        stored = self.invoices[invoice.id]
        count = self._stored_events[invoice.id]
        if invoice.events[:count] != stored.events[:count]:
            raise ConcurrentModificationError(f"invoice {invoice.id} changed since it was loaded")
        self.invoices[invoice.id] = invoice
        self._stored_events[invoice.id] = len(invoice.events)

    def get_document(self, invoice_id: UUID) -> Document | None:
        return self.documents.get(invoice_id)
