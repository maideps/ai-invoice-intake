import dataclasses
from decimal import Decimal

import pytest

from invoice_intake.domain import (
    ActorKind,
    AuditEvent,
    InvalidInvoiceDataError,
    Invoice,
    InvoiceFields,
    InvoiceStatus,
    LineItem,
)

from .domain_helpers import ACTORS, at, invoice_in

S = InvoiceStatus


def _restore(invoice: Invoice, events: list[AuditEvent] | None = None) -> Invoice:
    return Invoice.restore(
        id=invoice.id,
        filename=invoice.filename,
        uploaded_at=invoice.uploaded_at,
        fields=invoice.fields,
        events=list(invoice.events) if events is None else events,
    )


@pytest.mark.parametrize("status", list(InvoiceStatus))
def test_restore_rebuilds_every_status(status: InvoiceStatus) -> None:
    original = invoice_in(status)

    restored = _restore(original)

    assert restored.status is status
    assert restored.events == original.events
    assert restored.id == original.id


def test_restored_invoice_keeps_working() -> None:
    restored = _restore(invoice_in(S.NEEDS_REVIEW))

    restored.transition_to(S.APPROVED, actor=ACTORS[ActorKind.USER], at=at(30))

    assert restored.status is S.APPROVED
    assert restored.events[-1].sequence == 4


def test_restore_keeps_fields() -> None:
    fields = InvoiceFields(
        vendor_name="Acme",
        total=Decimal("10.00"),
        line_items=(LineItem("x", Decimal("1"), Decimal("10.00"), Decimal("10.00")),),
    )
    original = Invoice(
        filename="a.pdf", uploaded_by=ACTORS[ActorKind.USER], uploaded_at=at(0), fields=fields
    )

    assert _restore(original).fields == fields


def test_empty_trail_is_rejected() -> None:
    with pytest.raises(InvalidInvoiceDataError, match="upload event"):
        _restore(invoice_in(S.UPLOADED), events=[])


def _tampered(status: InvoiceStatus, index: int, changes: dict[str, object]) -> list[AuditEvent]:
    events = list(invoice_in(status).events)
    events[index] = dataclasses.replace(events[index], **changes)  # type: ignore[arg-type]
    return events


@pytest.mark.parametrize(
    ("status", "index", "changes", "message"),
    [
        (S.UPLOADED, 0, {"to_status": S.EXTRACTING}, "first audit event"),
        (S.UPLOADED, 0, {"occurred_at": at(5)}, "first audit event"),
        (S.NEEDS_REVIEW, 2, {"to_status": S.EXPORTED}, "event 3 breaks the lifecycle"),
        (S.APPROVED, 3, {"actor": ACTORS[ActorKind.AI]}, "event 4 breaks the lifecycle"),
        (S.REJECTED, 3, {"reason": None}, "event 4 breaks the lifecycle"),
        (S.EXTRACTING, 1, {"occurred_at": at(-1)}, "event 2 breaks the lifecycle"),
        (S.EXTRACTING, 1, {"sequence": 7}, "event 7 does not continue the trail"),
        (S.EXTRACTING, 1, {"from_status": S.NEEDS_REVIEW}, "event 2 does not continue the trail"),
    ],
)
def test_invalid_trail_is_rejected(
    status: InvoiceStatus, index: int, changes: dict[str, object], message: str
) -> None:
    events = _tampered(status, index, changes)

    with pytest.raises(InvalidInvoiceDataError, match=message):
        Invoice.restore(
            id=events[0].invoice_id,
            filename="acme-0001.pdf",
            uploaded_at=at(0),
            fields=InvoiceFields(),
            events=events,
        )


def test_events_from_another_invoice_are_rejected() -> None:
    first, second = invoice_in(S.EXTRACTING), invoice_in(S.UPLOADED)

    with pytest.raises(InvalidInvoiceDataError, match="first audit event"):
        _restore(second, events=list(first.events))
