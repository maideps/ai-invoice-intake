import dataclasses
from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from invoice_intake.domain import (
    TRANSITIONS,
    Actor,
    ActorKind,
    ActorNotPermittedError,
    AuditAction,
    InvalidInvoiceDataError,
    InvalidTransitionError,
    Invoice,
    InvoiceStatus,
)

from .domain_helpers import ACTORS, actor_for, at, invoice_in, new_invoice

S = InvoiceStatus

ALLOWED = [(source, target) for source, targets in TRANSITIONS.items() for target in targets]
FORBIDDEN = [
    (source, target)
    for source in InvoiceStatus
    for target in InvoiceStatus
    if target not in TRANSITIONS[source]
]
WRONG_ACTORS = [
    (source, target, kind)
    for source, target in ALLOWED
    for kind in ActorKind
    if kind is not TRANSITIONS[source][target]
]


def _reason(target: InvoiceStatus) -> str | None:
    return {S.REJECTED: "not our vendor", S.FAILED: "provider kept failing"}.get(target)


def test_status_pairs_cover_the_whole_grid() -> None:
    assert len(ALLOWED) == 8
    assert len(FORBIDDEN) == 41
    assert len(WRONG_ACTORS) == 16


def test_new_invoice_is_uploaded_with_one_audit_event() -> None:
    invoice = new_invoice()

    assert invoice.status is S.UPLOADED
    (event,) = invoice.events
    assert event.invoice_id == invoice.id
    assert event.sequence == 1
    assert event.action is AuditAction.STATUS_CHANGED
    assert (event.from_status, event.to_status) == (None, S.UPLOADED)
    assert event.actor == ACTORS[ActorKind.USER]
    assert event.occurred_at == at(0)


def test_explicit_id_is_kept() -> None:
    invoice_id = uuid4()

    invoice = Invoice(
        id=invoice_id,
        filename="a.pdf",
        uploaded_by=ACTORS[ActorKind.USER],
        uploaded_at=at(0),
    )

    assert invoice.id == invoice_id
    assert invoice.events[0].invoice_id == invoice_id


def test_full_lifecycle_to_exported_is_audited_in_order() -> None:
    invoice = invoice_in(S.EXPORTED)

    assert invoice.status is S.EXPORTED
    assert [event.sequence for event in invoice.events] == [1, 2, 3, 4, 5]
    assert [(event.from_status, event.to_status) for event in invoice.events] == [
        (None, S.UPLOADED),
        (S.UPLOADED, S.EXTRACTING),
        (S.EXTRACTING, S.NEEDS_REVIEW),
        (S.NEEDS_REVIEW, S.APPROVED),
        (S.APPROVED, S.EXPORTED),
    ]
    assert invoice.events[3].actor.kind is ActorKind.USER
    assert [event.occurred_at for event in invoice.events] == [at(minute) for minute in range(5)]


@pytest.mark.parametrize(("source", "target"), ALLOWED)
def test_allowed_transition_moves_and_records_an_event(
    source: InvoiceStatus, target: InvoiceStatus
) -> None:
    invoice = invoice_in(source)
    before = len(invoice.events)

    event = invoice.transition_to(
        target, actor=actor_for(source, target), at=at(30), reason=_reason(target)
    )

    assert invoice.status is target
    assert invoice.events[-1] == event
    assert event.sequence == before + 1
    assert (event.from_status, event.to_status) == (source, target)
    assert event.reason == _reason(target)


@pytest.mark.parametrize(("source", "target"), FORBIDDEN)
def test_forbidden_transition_raises_and_changes_nothing(
    source: InvoiceStatus, target: InvoiceStatus
) -> None:
    invoice = invoice_in(source)
    events = invoice.events

    for kind in ActorKind:
        with pytest.raises(InvalidTransitionError, match=f"from {source.value} to {target.value}"):
            invoice.transition_to(target, actor=ACTORS[kind], at=at(30), reason="any reason")

    assert invoice.status is source
    assert invoice.events == events


@pytest.mark.parametrize(("source", "target", "kind"), WRONG_ACTORS)
def test_wrong_actor_kind_is_refused_and_changes_nothing(
    source: InvoiceStatus, target: InvoiceStatus, kind: ActorKind
) -> None:
    invoice = invoice_in(source)
    events = invoice.events

    with pytest.raises(ActorNotPermittedError):
        invoice.transition_to(target, actor=ACTORS[kind], at=at(30), reason=_reason(target))

    assert invoice.status is source
    assert invoice.events == events


def test_ai_cannot_approve() -> None:
    invoice = invoice_in(S.NEEDS_REVIEW)

    with pytest.raises(ActorNotPermittedError, match="only a user actor"):
        invoice.transition_to(S.APPROVED, actor=ACTORS[ActorKind.AI], at=at(30))


@pytest.mark.parametrize("reason", [None, "", "   "])
def test_rejection_needs_a_reason(reason: str | None) -> None:
    invoice = invoice_in(S.NEEDS_REVIEW)

    with pytest.raises(InvalidInvoiceDataError, match="reason"):
        invoice.transition_to(S.REJECTED, actor=ACTORS[ActorKind.USER], at=at(30), reason=reason)

    assert invoice.status is S.NEEDS_REVIEW


def test_reason_is_trimmed_and_blank_becomes_none() -> None:
    invoice = invoice_in(S.NEEDS_REVIEW)

    rejected = invoice.transition_to(
        S.REJECTED, actor=ACTORS[ActorKind.USER], at=at(30), reason="  wrong vendor  "
    )
    assert rejected.reason == "wrong vendor"

    other = invoice_in(S.UPLOADED)
    moved = other.transition_to(
        S.EXTRACTING, actor=ACTORS[ActorKind.SYSTEM], at=at(30), reason="   "
    )
    assert moved.reason is None


def test_naive_timestamp_is_rejected() -> None:
    invoice = new_invoice()

    with pytest.raises(InvalidInvoiceDataError, match="timezone-aware"):
        invoice.transition_to(
            S.EXTRACTING, actor=ACTORS[ActorKind.SYSTEM], at=datetime(2026, 10, 12, 10, 0)
        )

    assert invoice.status is S.UPLOADED


def test_a_clock_a_little_behind_is_recorded_at_the_previous_event_time() -> None:
    # The API and the worker stamp events with their own clocks, which can step back slightly.
    invoice = invoice_in(S.EXTRACTING)
    previous = invoice.events[-1].occurred_at

    event = invoice.transition_to(
        S.NEEDS_REVIEW, actor=ACTORS[ActorKind.SYSTEM], at=previous - timedelta(seconds=2)
    )

    assert event.occurred_at == previous
    assert invoice.status is S.NEEDS_REVIEW


def test_events_cannot_go_back_in_time() -> None:
    invoice = invoice_in(S.EXTRACTING)

    with pytest.raises(InvalidInvoiceDataError, match="back in time"):
        invoice.transition_to(S.NEEDS_REVIEW, actor=ACTORS[ActorKind.SYSTEM], at=at(0))

    assert invoice.status is S.EXTRACTING
    assert len(invoice.events) == 2


def test_events_at_the_same_instant_are_allowed() -> None:
    invoice = new_invoice()

    invoice.transition_to(S.EXTRACTING, actor=ACTORS[ActorKind.SYSTEM], at=at(0))

    assert invoice.status is S.EXTRACTING


def test_audit_trail_is_read_only() -> None:
    invoice = invoice_in(S.NEEDS_REVIEW)

    assert isinstance(invoice.events, tuple)
    with pytest.raises(dataclasses.FrozenInstanceError):
        invoice.events[0].to_status = S.APPROVED  # type: ignore[misc]


@pytest.mark.parametrize("filename", ["", "   "])
def test_blank_filename_is_rejected(filename: str) -> None:
    with pytest.raises(InvalidInvoiceDataError, match="filename"):
        Invoice(filename=filename, uploaded_by=ACTORS[ActorKind.USER], uploaded_at=at(0))


def test_naive_upload_time_is_rejected() -> None:
    with pytest.raises(InvalidInvoiceDataError, match="uploaded_at"):
        Invoice(
            filename="a.pdf",
            uploaded_by=ACTORS[ActorKind.USER],
            uploaded_at=datetime(2026, 10, 12, 9, 0),
        )


def test_blank_actor_name_is_rejected() -> None:
    with pytest.raises(InvalidInvoiceDataError, match="actor name"):
        Actor(ActorKind.USER, " ")
