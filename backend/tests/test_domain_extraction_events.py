import dataclasses
from decimal import Decimal

import pytest

from invoice_intake.domain import (
    FIELD_NAMES,
    ActorKind,
    ActorNotPermittedError,
    AuditAction,
    AuditEvent,
    InvalidInvoiceDataError,
    InvalidTransitionError,
    Invoice,
    InvoiceFields,
    InvoiceStatus,
)
from invoice_intake.domain.invoice import MAX_RECORDED_OUTPUT_CHARS

from .domain_helpers import ACTORS, at, invoice_in

S = InvoiceStatus
FIELDS = InvoiceFields(vendor_name="Acme", currency="EUR", total=Decimal("12.50"))
CONFIDENCE = {name: 0.8 for name in FIELD_NAMES}


def _record(invoice: Invoice, minute: int = 10) -> AuditEvent:
    return invoice.record_extraction(
        provider="fake", model="m", fields=FIELDS, confidence=CONFIDENCE, at=at(minute)
    )


def test_recording_an_extraction_sets_fields_and_keeps_the_output() -> None:
    invoice = invoice_in(S.EXTRACTING)

    event = _record(invoice)

    assert invoice.fields == FIELDS
    assert invoice.status is S.EXTRACTING  # the service moves it on separately
    assert event.action is AuditAction.EXTRACTION_RECORDED
    assert (event.from_status, event.to_status) == (None, None)
    assert (event.actor.kind, event.actor.name) == (ActorKind.AI, "fake:m")
    assert event.details == {
        "provider": "fake",
        "model": "m",
        "fields": FIELDS.to_json(),
        "confidence": CONFIDENCE,
    }
    assert invoice.extraction_confidence == CONFIDENCE


def test_confidence_comes_from_the_latest_accepted_extraction() -> None:
    invoice = invoice_in(S.EXTRACTING)
    assert invoice.extraction_confidence is None

    _record(invoice, 10)
    invoice.record_extraction(
        provider="fake",
        model="m2",
        fields=FIELDS,
        confidence={name: 0.1 for name in FIELD_NAMES},
        at=at(11),
    )

    assert invoice.extraction_confidence == {name: 0.1 for name in FIELD_NAMES}


@pytest.mark.parametrize("status", [s for s in InvoiceStatus if s is not S.EXTRACTING])
def test_extraction_can_only_be_recorded_while_extracting(status: InvoiceStatus) -> None:
    invoice = invoice_in(status)

    with pytest.raises(InvalidTransitionError, match="extraction_recorded"):
        _record(invoice)
    with pytest.raises(InvalidTransitionError, match="extraction_rejected"):
        invoice.record_rejected_extraction(
            provider="fake", model="m", output={}, errors=["x"], at=at(10)
        )


def test_only_an_ai_actor_may_record_extraction_notes() -> None:
    invoice = invoice_in(S.EXTRACTING)
    events = invoice.events

    with pytest.raises(ActorNotPermittedError):
        invoice._note(
            AuditAction.EXTRACTION_RECORDED, actor=ACTORS[ActorKind.USER], at=at(10), details={}
        )

    assert invoice.events == events


def test_rejected_output_is_kept_without_touching_fields() -> None:
    invoice = invoice_in(S.EXTRACTING)

    event = invoice.record_rejected_extraction(
        provider="openai",
        model="m",
        output={"fields": "nope"},
        errors=["fields must be a JSON object"],
        at=at(10),
    )

    assert invoice.fields == InvoiceFields()
    assert event.action is AuditAction.EXTRACTION_REJECTED
    assert event.details == {
        "provider": "openai",
        "model": "m",
        "errors": ["fields must be a JSON object"],
        "output": {"fields": "nope"},
    }


def test_huge_or_odd_output_is_truncated_when_recorded() -> None:
    invoice = invoice_in(S.EXTRACTING)
    huge = "x" * (MAX_RECORDED_OUTPUT_CHARS + 500)

    event = invoice.record_rejected_extraction(
        provider="p", model="m", output=huge, errors=["not JSON"], at=at(10)
    )
    odd = invoice.record_rejected_extraction(
        provider="p", model="m", output=object(), errors=["not JSON"], at=at(11)
    )

    assert event.details is not None and odd.details is not None
    recorded = event.details["output"]
    assert len(recorded["truncated"]) == MAX_RECORDED_OUTPUT_CHARS
    assert recorded["original_length"] == len(huge)
    assert odd.details["output"]["truncated"].startswith("<object object")


def test_restore_replays_extraction_notes() -> None:
    invoice = invoice_in(S.EXTRACTING)
    invoice.record_rejected_extraction(
        provider="p", model="m", output="garbage", errors=["bad"], at=at(9)
    )
    _record(invoice, 10)
    invoice.transition_to(S.NEEDS_REVIEW, actor=ACTORS[ActorKind.SYSTEM], at=at(11))

    restored = Invoice.restore(
        id=invoice.id,
        filename=invoice.filename,
        uploaded_at=invoice.uploaded_at,
        fields=invoice.fields,
        events=list(invoice.events),
    )

    assert restored.events == invoice.events
    assert restored.status is S.NEEDS_REVIEW
    assert restored.extraction_confidence == CONFIDENCE


def test_restore_rejects_a_note_written_in_the_wrong_status() -> None:
    source = invoice_in(S.EXTRACTING)
    note = _record(source)
    reviewed = invoice_in(S.NEEDS_REVIEW)
    # Pretend the note came after needs_review, where it is not allowed.
    events = [*reviewed.events, dataclasses.replace(note, invoice_id=reviewed.id, sequence=4)]

    with pytest.raises(InvalidInvoiceDataError, match="event 4 breaks the lifecycle"):
        Invoice.restore(
            id=reviewed.id,
            filename=reviewed.filename,
            uploaded_at=reviewed.uploaded_at,
            fields=InvoiceFields(),
            events=events,
        )


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"action": AuditAction.STATUS_CHANGED, "to_status": None}, "needs to_status"),
        ({"action": AuditAction.EXTRACTION_RECORDED}, "has no status change"),
        ({"details": {"score": float("nan")}}, "JSON-safe"),
        ({"details": {"when": at(0)}}, "JSON-safe"),
        ({"details": ["not", "an", "object"]}, "JSON object"),
    ],
)
def test_audit_event_shape_is_enforced(changes: dict[str, object], message: str) -> None:
    base = invoice_in(S.EXTRACTING).events[1]
    values = {**base.__dict__, **changes}

    with pytest.raises(InvalidInvoiceDataError, match=message):
        AuditEvent(**values)


def test_details_are_a_detached_json_copy() -> None:
    details = {"rows": (1, 2), "nested": {"a": 1}}
    event = AuditEvent(
        invoice_id=invoice_in(S.UPLOADED).id,
        sequence=2,
        occurred_at=at(1),
        actor=ACTORS[ActorKind.AI],
        action=AuditAction.EXTRACTION_REJECTED,
        from_status=None,
        to_status=None,
        details=details,
    )
    details["nested"]["a"] = 2  # type: ignore[index]

    assert event.details == {"rows": [1, 2], "nested": {"a": 1}}
