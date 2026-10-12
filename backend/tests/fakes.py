"""In-memory stand-ins for infrastructure, for tests that do not need PostgreSQL."""

from uuid import UUID

from invoice_intake.domain import (
    ConcurrentModificationError,
    Document,
    Invoice,
    InvoicePage,
    InvoiceStatus,
    RawExtraction,
)


def _copy(invoice: Invoice) -> Invoice:
    return Invoice.restore(
        id=invoice.id,
        filename=invoice.filename,
        uploaded_at=invoice.uploaded_at,
        fields=invoice.fields,
        events=list(invoice.events),
    )


class InMemoryInvoiceRepository:
    """Follows the ``InvoiceRepository`` contract, including append-only events.

    Like a database, it hands out and keeps copies: changes to a loaded invoice exist only
    after ``save``, so an operation that fails half-way leaves the stored invoice untouched.
    """

    def __init__(self) -> None:
        self._invoices: dict[UUID, Invoice] = {}
        self.documents: dict[UUID, Document] = {}

    @property
    def invoices(self) -> dict[UUID, Invoice]:
        return {invoice_id: _copy(invoice) for invoice_id, invoice in self._invoices.items()}

    def add(self, invoice: Invoice, document: Document) -> None:
        if invoice.id in self._invoices:
            raise ValueError(f"invoice {invoice.id} already exists")
        self._invoices[invoice.id] = _copy(invoice)
        self.documents[invoice.id] = document

    def get(self, invoice_id: UUID) -> Invoice | None:
        stored = self._invoices.get(invoice_id)
        return None if stored is None else _copy(stored)

    def list_page(self, *, status: InvoiceStatus | None, limit: int, offset: int) -> InvoicePage:
        matching = [i for i in self._invoices.values() if status is None or i.status is status]
        matching.sort(key=lambda invoice: (invoice.uploaded_at, invoice.id), reverse=True)
        return InvoicePage(
            items=tuple(_copy(i) for i in matching[offset : offset + limit]), total=len(matching)
        )

    def save(self, invoice: Invoice) -> None:
        stored = self._invoices[invoice.id].events
        if invoice.events[: len(stored)] != stored:
            raise ConcurrentModificationError(f"invoice {invoice.id} changed since it was loaded")
        self._invoices[invoice.id] = _copy(invoice)

    def get_document(self, invoice_id: UUID) -> Document | None:
        return self.documents.get(invoice_id)


class ScriptedProvider:
    """An extraction provider that returns prepared outputs, or raises, in order."""

    name = "scripted"

    def __init__(self, *outputs: object) -> None:
        self._outputs = list(outputs)
        self.calls = 0

    def extract(self, document: Document) -> RawExtraction:
        self.calls += 1
        output = self._outputs.pop(0)
        if isinstance(output, Exception):
            raise output
        return RawExtraction(self.name, "test-model", output)
