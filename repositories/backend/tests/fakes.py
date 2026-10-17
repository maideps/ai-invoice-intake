"""In-memory stand-ins for infrastructure, for tests that do not need PostgreSQL."""

from datetime import datetime
from uuid import UUID

from invoice_intake.domain import (
    Account,
    ConcurrentModificationError,
    Document,
    DuplicateUsernameError,
    Invoice,
    InvoicePage,
    InvoiceStatus,
    RawExtraction,
    Role,
)
from invoice_intake.services.queue import JobKind


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

    def count_by_status(self) -> dict[InvoiceStatus, int]:
        counts: dict[InvoiceStatus, int] = {}
        for invoice in self._invoices.values():
            counts[invoice.status] = counts.get(invoice.status, 0) + 1
        return counts


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


class RecordingQueue:
    """An ``ExtractionQueue`` that only remembers what was queued (``queued``: extraction jobs,
    ``exports``: export jobs)."""

    def __init__(self) -> None:
        self.queued: list[UUID] = []
        self.exports: list[UUID] = []

    def enqueue(self, invoice_id: UUID, kind: JobKind = "extract") -> None:
        (self.exports if kind == "export" else self.queued).append(invoice_id)


class InMemoryAccountRepository:
    def __init__(self) -> None:
        self.accounts: dict[UUID, Account] = {}

    def get(self, account_id: UUID) -> Account | None:
        return self.accounts.get(account_id)

    def get_by_username(self, username: str) -> Account | None:
        return next((a for a in self.accounts.values() if a.username == username), None)

    def list_all(self) -> list[Account]:
        return sorted(self.accounts.values(), key=lambda account: account.username)

    def add(self, account: Account) -> None:
        if self.get_by_username(account.username):
            raise DuplicateUsernameError(f"the username {account.username!r} is taken")
        self.accounts[account.id] = account

    def update(self, account: Account) -> None:
        self.accounts[account.id] = account

    def count_active_admins(self) -> int:
        return sum(1 for a in self.accounts.values() if a.active and a.role is Role.ADMIN)


class InMemorySessionRepository:
    def __init__(self) -> None:
        self.sessions: dict[str, tuple[UUID, datetime]] = {}

    def add(
        self, token_hash: str, account_id: UUID, *, created_at: datetime, expires_at: datetime
    ) -> None:
        self.sessions[token_hash] = (account_id, expires_at)

    def account_for(self, token_hash: str, *, now: datetime) -> UUID | None:
        found = self.sessions.get(token_hash)
        return found[0] if found and found[1] > now else None

    def delete(self, token_hash: str) -> None:
        self.sessions.pop(token_hash, None)

    def delete_for_account(self, account_id: UUID) -> None:
        for key in [key for key, (owner, _) in self.sessions.items() if owner == account_id]:
            del self.sessions[key]

    def delete_expired(self, *, now: datetime) -> None:
        for key in [key for key, (_, expires) in self.sessions.items() if expires <= now]:
            del self.sessions[key]
