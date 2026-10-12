"""Builders for domain tests: actors, a fixed clock, and invoices already in a given status."""

from datetime import datetime, timedelta, timezone

from invoice_intake.domain import TRANSITIONS, Actor, ActorKind, Invoice, InvoiceStatus

START = datetime(2026, 10, 12, 9, 0, tzinfo=timezone.utc)

ACTORS = {
    ActorKind.SYSTEM: Actor(ActorKind.SYSTEM, "worker"),
    ActorKind.AI: Actor(ActorKind.AI, "fake-model"),
    ActorKind.USER: Actor(ActorKind.USER, "reviewer@example.com"),
}

# The moves that lead from a new invoice to each status.
PATHS: dict[InvoiceStatus, list[InvoiceStatus]] = {
    InvoiceStatus.UPLOADED: [],
    InvoiceStatus.EXTRACTING: [InvoiceStatus.EXTRACTING],
    InvoiceStatus.NEEDS_REVIEW: [InvoiceStatus.EXTRACTING, InvoiceStatus.NEEDS_REVIEW],
    InvoiceStatus.APPROVED: [
        InvoiceStatus.EXTRACTING,
        InvoiceStatus.NEEDS_REVIEW,
        InvoiceStatus.APPROVED,
    ],
    InvoiceStatus.REJECTED: [
        InvoiceStatus.EXTRACTING,
        InvoiceStatus.NEEDS_REVIEW,
        InvoiceStatus.REJECTED,
    ],
    InvoiceStatus.EXPORTED: [
        InvoiceStatus.EXTRACTING,
        InvoiceStatus.NEEDS_REVIEW,
        InvoiceStatus.APPROVED,
        InvoiceStatus.EXPORTED,
    ],
}


def at(minutes: int) -> datetime:
    return START + timedelta(minutes=minutes)


def actor_for(source: InvoiceStatus, target: InvoiceStatus) -> Actor:
    """The actor allowed to make this move."""
    return ACTORS[TRANSITIONS[source][target]]


def new_invoice() -> Invoice:
    return Invoice(filename="acme-0001.pdf", uploaded_by=ACTORS[ActorKind.USER], uploaded_at=at(0))


def invoice_in(status: InvoiceStatus) -> Invoice:
    """A new invoice moved, by the allowed actors, into ``status``."""
    invoice = new_invoice()
    for minute, target in enumerate(PATHS[status], start=1):
        invoice.transition_to(
            target,
            actor=actor_for(invoice.status, target),
            at=at(minute),
            reason="duplicate of an earlier invoice" if target is InvoiceStatus.REJECTED else None,
        )
    return invoice
