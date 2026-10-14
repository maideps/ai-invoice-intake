import hashlib
import hmac
import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from invoice_intake.domain import (
    ActorKind,
    ActorNotPermittedError,
    AuditAction,
    Document,
    InvalidTransitionError,
    Invoice,
    InvoiceStatus,
)
from invoice_intake.infrastructure.export_webhook import HttpWebhookSender
from invoice_intake.services.export import (
    ExportDeliveryError,
    ExportRunner,
    ExportService,
    NotExportableError,
    export_payload,
)
from invoice_intake.services.extraction import AttemptResult
from invoice_intake.services.review import ReviewService

from .domain_helpers import ACTORS, READY_FIELDS, at, invoice_in
from .fakes import InMemoryInvoiceRepository, RecordingQueue
from .webhook_server import Webhook

S = InvoiceStatus
PDF = Document("application/pdf", b"%PDF-1.4")


class Clock:
    def __init__(self) -> None:
        self.minute = 100

    def __call__(self) -> datetime:
        self.minute += 1
        return at(self.minute)


class ScriptedSender:
    """Fails with the prepared errors in turn, then accepts; remembers every payload."""

    def __init__(self, *errors: ExportDeliveryError) -> None:
        self.errors = list(errors)
        self.sent: list[tuple[dict[str, Any], str]] = []

    def send(self, payload: dict[str, Any], *, idempotency_key: str) -> None:
        self.sent.append((payload, idempotency_key))
        if self.errors:
            raise self.errors.pop(0)


class World:
    def __init__(self, sender: ScriptedSender, max_attempts: int = 3) -> None:
        self.repository = InMemoryInvoiceRepository()
        self.queue = RecordingQueue()
        self.sender = sender
        clock = Clock()

        @contextmanager
        def services() -> Iterator[ExportService]:
            yield ExportService(self.repository, self.queue, clock=clock)

        self.services = services
        self.runner = ExportRunner(services, sender, max_attempts=max_attempts)

    def add(self, invoice: Invoice) -> Invoice:
        self.repository.add(invoice, PDF)
        return invoice

    def stored(self, invoice_id: UUID) -> Invoice:
        stored = self.repository.get(invoice_id)
        assert stored is not None
        return stored


# Payload and delivery over real HTTP ----------------------------------------------------------


def test_payload_carries_the_approved_values_and_who_approved_them() -> None:
    invoice = invoice_in(S.APPROVED)

    payload = export_payload(invoice)

    assert payload == {
        "payload_version": 1,
        "invoice_id": str(invoice.id),
        "filename": "acme-0001.pdf",
        "approved_at": invoice.events[-1].occurred_at.isoformat(),
        "approved_by": "reviewer@example.com",
        "audit_version": invoice.version,
        "fields": READY_FIELDS.to_json(),
    }
    json.dumps(payload)  # JSON-ready as it is


def test_delivery_is_a_signed_json_post_with_an_idempotency_key(webhook: Webhook) -> None:
    sender = HttpWebhookSender(webhook.url, secret="s3cret")
    payload = export_payload(invoice_in(S.APPROVED))

    sender.send(payload, idempotency_key="invoice-1")
    sender.send(payload, idempotency_key="invoice-1")

    first, second = webhook.deliveries
    assert first.path == "/hooks/invoices"
    assert json.loads(first.body) == payload
    assert first.headers["Content-Type"] == "application/json"
    assert first.headers["Idempotency-Key"] == "invoice-1"
    expected = "sha256=" + hmac.new(b"s3cret", first.body, hashlib.sha256).hexdigest()
    assert first.headers["X-Invoice-Intake-Signature"] == expected
    # One delivery id per attempt; the idempotency key stays the same.
    assert first.headers["X-Invoice-Intake-Delivery"] != second.headers["X-Invoice-Intake-Delivery"]
    assert second.headers["Idempotency-Key"] == "invoice-1"


def test_no_signature_without_a_secret(webhook: Webhook) -> None:
    HttpWebhookSender(webhook.url).send({"a": 1}, idempotency_key="k")

    assert "X-Invoice-Intake-Signature" not in webhook.deliveries[0].headers


def test_a_non_2xx_answer_is_a_failed_delivery_with_status_and_reason(webhook: Webhook) -> None:
    webhook.statuses = [503]

    with pytest.raises(ExportDeliveryError) as caught:
        HttpWebhookSender(webhook.url).send({}, idempotency_key="k")

    assert caught.value.status_code == 503
    assert str(caught.value) == "HTTP 503: temporarily unavailable"


def test_a_slow_webhook_times_out(webhook: Webhook) -> None:
    webhook.delay = 1.0

    with pytest.raises(ExportDeliveryError, match="did not answer in time") as caught:
        HttpWebhookSender(webhook.url, timeout_seconds=0.2).send({}, idempotency_key="k")

    assert caught.value.status_code is None


def test_an_unreachable_webhook_is_a_failed_delivery() -> None:
    # Refused at once on Linux; on Windows the connection attempt runs into the timeout instead.
    with pytest.raises(
        ExportDeliveryError, match="could not reach the webhook|did not answer"
    ) as caught:
        HttpWebhookSender("http://127.0.0.1:1/hook", timeout_seconds=1).send(
            {}, idempotency_key="k"
        )

    assert caught.value.status_code is None


# The runner -----------------------------------------------------------------------------------


def test_a_delivered_invoice_moves_to_exported() -> None:
    world = World(ScriptedSender())
    invoice = world.add(invoice_in(S.APPROVED))

    outcome = world.runner.run(invoice.id, attempt=1)

    assert outcome.result is AttemptResult.ACCEPTED
    stored = world.stored(invoice.id)
    assert stored.status is S.EXPORTED
    assert (stored.events[-1].actor.kind, stored.events[-1].actor.name) == (
        ActorKind.SYSTEM,
        "export-service",
    )
    payload, key = world.sender.sent[0]
    assert key == str(invoice.id)
    assert payload["fields"] == READY_FIELDS.to_json()
    assert stored.export_status is not None and stored.export_status.state == "exported"


def test_a_failed_delivery_is_recorded_and_retried_then_succeeds() -> None:
    world = World(ScriptedSender(ExportDeliveryError("HTTP 503: down", status_code=503)))
    invoice = world.add(invoice_in(S.APPROVED))

    first = world.runner.run(invoice.id, attempt=1)

    assert (first.result, first.detail) == (AttemptResult.RETRY, "delivery failed: HTTP 503: down")
    failing = world.stored(invoice.id)
    assert failing.status is S.APPROVED
    assert failing.events[-1].action is AuditAction.EXPORT_FAILED
    assert failing.events[-1].details == {
        "attempt": 1,
        "error": "HTTP 503: down",
        "final": False,
        "status_code": 503,
    }
    status = failing.export_status
    assert status is not None
    assert (status.state, status.attempts, status.last_error) == ("retrying", 1, "HTTP 503: down")

    assert world.runner.run(invoice.id, attempt=2).result is AttemptResult.ACCEPTED
    assert world.stored(invoice.id).status is S.EXPORTED


def test_the_last_attempt_marks_the_export_failed_and_a_person_can_retry() -> None:
    error = ExportDeliveryError("could not reach the webhook: refused")
    world = World(ScriptedSender(error, error), max_attempts=2)
    invoice = world.add(invoice_in(S.APPROVED))

    world.runner.run(invoice.id, attempt=1)
    outcome = world.runner.run(invoice.id, attempt=2)

    assert outcome.result is AttemptResult.FAILED
    status = world.stored(invoice.id).export_status
    assert status is not None and (status.state, status.attempts) == ("failed", 2)

    with world.services() as service:
        service.request(invoice.id)
    assert world.queue.exports == [invoice.id]


@pytest.mark.parametrize("status", [s for s in InvoiceStatus if s is not S.APPROVED])
def test_nothing_is_exported_before_approval(status: InvoiceStatus) -> None:
    world = World(ScriptedSender())
    invoice = world.add(invoice_in(status))

    outcome = world.runner.run(invoice.id, attempt=1)

    assert outcome.result is AttemptResult.SKIPPED
    assert world.sender.sent == []  # no HTTP request at all
    with pytest.raises(NotExportableError), world.services() as service:
        service.request(invoice.id)
    assert world.queue.exports == []


def test_unknown_invoices_are_skipped() -> None:
    world = World(ScriptedSender())

    assert world.runner.run(uuid4(), attempt=1).result is AttemptResult.SKIPPED


def test_approving_queues_an_export() -> None:
    repository, queue = InMemoryInvoiceRepository(), RecordingQueue()
    invoice = invoice_in(S.NEEDS_REVIEW)
    repository.add(invoice, PDF)
    review = ReviewService(repository, queue, clock=lambda: at(50))

    review.approve(invoice.id, version=invoice.version, reviewer=ACTORS[ActorKind.USER])

    assert queue.exports == [invoice.id]


def test_rejecting_queues_nothing() -> None:
    repository, queue = InMemoryInvoiceRepository(), RecordingQueue()
    invoice = invoice_in(S.NEEDS_REVIEW)
    repository.add(invoice, PDF)
    review = ReviewService(repository, queue, clock=lambda: at(50))

    review.reject(invoice.id, version=invoice.version, reviewer=ACTORS[ActorKind.USER], reason="no")

    assert queue.exports == []


def test_sweep_requeues_approvals_that_never_had_a_delivery() -> None:
    world = World(ScriptedSender())
    waiting = world.add(invoice_in(S.APPROVED))  # approved at minute 3
    failing = invoice_in(S.APPROVED)
    failing.record_export_failure(attempt=1, error="x", final=False, status_code=500, at=at(9))
    world.add(failing)

    with world.services() as service:
        queued = service.requeue_unsent(approved_before=at(10))

    assert (queued, world.queue.exports) == (1, [waiting.id])


# Domain rules ---------------------------------------------------------------------------------


def test_export_status_is_none_before_approval() -> None:
    assert invoice_in(S.NEEDS_REVIEW).export_status is None


def test_export_failures_are_only_recorded_for_approved_invoices_by_the_system() -> None:
    reviewed = invoice_in(S.NEEDS_REVIEW)
    with pytest.raises(InvalidTransitionError, match="export_failed"):
        reviewed.record_export_failure(
            attempt=1, error="x", final=False, status_code=None, at=at(9)
        )

    approved = invoice_in(S.APPROVED)
    with pytest.raises(ActorNotPermittedError):
        approved._note(
            AuditAction.EXPORT_FAILED, actor=ACTORS[ActorKind.USER], at=at(9), details={}
        )


def test_restore_replays_export_failures() -> None:
    invoice = invoice_in(S.APPROVED)
    invoice.record_export_failure(
        attempt=1, error="HTTP 500", final=True, status_code=500, at=at(9)
    )

    restored = Invoice.restore(
        id=invoice.id,
        filename=invoice.filename,
        uploaded_at=invoice.uploaded_at,
        fields=invoice.fields,
        events=list(invoice.events),
    )

    assert restored.events == invoice.events
    assert restored.export_status is not None and restored.export_status.state == "failed"
