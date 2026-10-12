from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker

from invoice_intake.domain import (
    ActorKind,
    ConcurrentModificationError,
    Document,
    Invoice,
    InvoiceFields,
    InvoiceStatus,
    LineItem,
)
from invoice_intake.infrastructure.repository import SqlInvoiceRepository

from .domain_helpers import ACTORS, PATHS, actor_for, at, invoice_in

pytestmark = pytest.mark.postgres

S = InvoiceStatus
PDF = Document(content_type="application/pdf", content=b"%PDF-1.4\n%test\n")
FIELDS = InvoiceFields(
    vendor_name="Kestrel Analytik GmbH",
    invoice_number="RE-20260042",
    issue_date=date(2026, 3, 1),
    due_date=date(2026, 3, 15),
    currency="EUR",
    subtotal=Decimal("1190.00"),
    tax=Decimal("226.10"),
    total=Decimal("1416.10"),
    line_items=(
        LineItem("Datenanalyse", Decimal("7.5"), Decimal("120.00"), Decimal("900.00")),
        LineItem("Workshop", Decimal("2"), Decimal("145.00"), Decimal("290.00")),
    ),
)


def _store(sessions: sessionmaker[Session], *invoices: Invoice) -> None:
    with sessions.begin() as session:
        repository = SqlInvoiceRepository(session)
        for invoice in invoices:
            repository.add(invoice, PDF)


def _load(sessions: sessionmaker[Session], invoice: Invoice) -> Invoice:
    with sessions() as session:
        loaded = SqlInvoiceRepository(session).get(invoice.id)
    assert loaded is not None
    return loaded


@pytest.mark.parametrize("status", list(InvoiceStatus))
def test_round_trip_in_every_status(sessions: sessionmaker[Session], status: S) -> None:
    # Every status and actor kind passes the database's CHECK constraints and comes back.
    invoice = invoice_in(status)
    _store(sessions, invoice)

    loaded = _load(sessions, invoice)

    assert loaded.status is status
    assert loaded.events == invoice.events
    assert (loaded.filename, loaded.uploaded_at) == (invoice.filename, invoice.uploaded_at)


def test_fields_and_line_items_round_trip_exactly(sessions: sessionmaker[Session]) -> None:
    invoice = Invoice(
        filename="kestrel.pdf", uploaded_by=ACTORS[ActorKind.USER], uploaded_at=at(0), fields=FIELDS
    )
    _store(sessions, invoice)

    loaded = _load(sessions, invoice)

    assert loaded.fields == FIELDS
    # numeric keeps the stored scale, so "900.00" does not come back as "900" or "900.0000"
    assert [str(item.amount) for item in loaded.fields.line_items] == ["900.00", "290.00"]
    assert str(loaded.fields.line_items[0].quantity) == "7.5"


def test_document_is_stored_byte_for_byte(sessions: sessionmaker[Session]) -> None:
    invoice = invoice_in(S.UPLOADED)
    _store(sessions, invoice)

    with sessions() as session:
        document = SqlInvoiceRepository(session).get_document(invoice.id)
        size, digest = session.execute(
            text("SELECT size, sha256 FROM invoice_documents WHERE invoice_id = :id"),
            {"id": invoice.id},
        ).one()

    assert document == PDF
    assert (size, digest) == (PDF.size, PDF.sha256)


def test_unknown_invoice_is_none(sessions: sessionmaker[Session]) -> None:
    with sessions() as session:
        repository = SqlInvoiceRepository(session)
        assert repository.get(invoice_in(S.UPLOADED).id) is None
        assert repository.get_document(invoice_in(S.UPLOADED).id) is None


def test_save_appends_new_events_and_updates_status(sessions: sessionmaker[Session]) -> None:
    invoice = invoice_in(S.UPLOADED)
    _store(sessions, invoice)

    with sessions.begin() as session:
        repository = SqlInvoiceRepository(session)
        loaded = repository.get(invoice.id)
        assert loaded is not None
        for minute, target in enumerate(PATHS[S.EXPORTED], start=1):
            loaded.transition_to(target, actor=actor_for(loaded.status, target), at=at(minute))
        repository.save(loaded)

    reloaded = _load(sessions, invoice)
    assert reloaded.status is S.EXPORTED
    assert [event.sequence for event in reloaded.events] == [1, 2, 3, 4, 5]
    assert reloaded.events[0] == invoice.events[0]  # the stored upload event is untouched


def test_save_replaces_fields_and_line_items(sessions: sessionmaker[Session]) -> None:
    original = Invoice(
        filename="k.pdf", uploaded_by=ACTORS[ActorKind.USER], uploaded_at=at(0), fields=FIELDS
    )
    _store(sessions, original)
    changed_fields = InvoiceFields(
        vendor_name="Kestrel Analytik GmbH",
        line_items=(LineItem("Workshop", Decimal("1"), Decimal("145.00"), Decimal("145.00")),),
    )
    changed = Invoice.restore(
        id=original.id,
        filename=original.filename,
        uploaded_at=original.uploaded_at,
        fields=changed_fields,
        events=list(original.events),
    )

    with sessions.begin() as session:
        SqlInvoiceRepository(session).save(changed)

    assert _load(sessions, original).fields == changed_fields


def test_a_stale_save_is_refused(sessions: sessionmaker[Session]) -> None:
    invoice = invoice_in(S.UPLOADED)
    _store(sessions, invoice)
    first, second = _load(sessions, invoice), _load(sessions, invoice)
    system = ACTORS[ActorKind.SYSTEM]

    first.transition_to(S.EXTRACTING, actor=system, at=at(1))
    with sessions.begin() as session:
        SqlInvoiceRepository(session).save(first)

    # ``second`` was loaded before ``first`` was saved; its event 2 would contradict history.
    second.transition_to(S.EXTRACTING, actor=system, at=at(2))
    with pytest.raises(ConcurrentModificationError), sessions.begin() as session:
        SqlInvoiceRepository(session).save(second)

    assert _load(sessions, invoice).events == first.events


def test_list_page_filters_orders_and_pages(sessions: sessionmaker[Session]) -> None:
    # Different upload times, so newest-first order is defined: 1.pdf is the newest.
    uploaded = [
        Invoice(filename=f"{n}.pdf", uploaded_by=ACTORS[ActorKind.USER], uploaded_at=at(-n))
        for n in (1, 2, 3)
    ]
    _store(sessions, *uploaded, invoice_in(S.APPROVED))

    with sessions() as session:
        repository = SqlInvoiceRepository(session)
        everything = repository.list_page(status=None, limit=10, offset=0)
        first_two = repository.list_page(status=S.UPLOADED, limit=2, offset=0)
        last = repository.list_page(status=S.UPLOADED, limit=2, offset=2)
        none = repository.list_page(status=S.REJECTED, limit=10, offset=0)

    assert everything.total == 4
    assert [i.filename for i in first_two.items] == ["1.pdf", "2.pdf"]  # newest first
    assert (first_two.total, [i.filename for i in last.items]) == (3, ["3.pdf"])
    assert (none.total, none.items) == (0, ())


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE audit_events SET reason = 'rewritten'",
        "UPDATE audit_events SET actor_name = 'someone else'",
        "DELETE FROM audit_events",
    ],
)
def test_database_refuses_to_change_the_audit_trail(
    sessions: sessionmaker[Session], statement: str
) -> None:
    invoice = invoice_in(S.NEEDS_REVIEW)
    _store(sessions, invoice)

    with pytest.raises(DBAPIError, match="append-only"), sessions.begin() as session:
        session.execute(text(statement))

    assert _load(sessions, invoice).events == invoice.events


def test_database_rejects_values_outside_the_enums(sessions: sessionmaker[Session]) -> None:
    invoice = invoice_in(S.UPLOADED)
    _store(sessions, invoice)

    with pytest.raises(DBAPIError, match="ck_invoices_status"), sessions.begin() as session:
        session.execute(text("UPDATE invoices SET status = 'paid'"))
