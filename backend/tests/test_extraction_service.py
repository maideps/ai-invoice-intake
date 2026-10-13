import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pytest
from samplegen.ground_truth import load_ground_truth

from invoice_intake.domain import (
    FIELD_NAMES,
    ActorKind,
    AuditAction,
    Document,
    ExtractionProvider,
    ExtractionProviderError,
    Invoice,
    InvoiceStatus,
    empty_output,
)
from invoice_intake.infrastructure.extraction import FakeExtractionProvider
from invoice_intake.services.extraction import (
    AttemptResult,
    ExtractionRunner,
    ExtractionService,
    NotExtractableError,
)
from invoice_intake.services.intake import IntakeService, InvoiceNotFoundError

from .domain_helpers import ACTORS, at, invoice_in
from .fakes import InMemoryInvoiceRepository, RecordingQueue, ScriptedProvider

SAMPLES = Path(__file__).resolve().parents[2] / "samples" / "invoices"
S = InvoiceStatus
USER = ACTORS[ActorKind.USER]
PDF = Document("application/pdf", b"%PDF-1.4 test")


class Clock:
    """Each call is one minute later, so audit times are distinct and ordered."""

    def __init__(self) -> None:
        self.minute = 100  # after anything the domain helpers create (minutes 0-10)

    def __call__(self) -> datetime:
        self.minute += 1
        return at(self.minute)


class World:
    """An in-memory backend: intake, the per-transaction extraction steps, and a runner."""

    def __init__(self, provider: ExtractionProvider, max_attempts: int = 3) -> None:
        self.repository = InMemoryInvoiceRepository()
        self.queue = RecordingQueue()
        clock = Clock()
        self.intake = IntakeService(
            self.repository, self.queue, clock=clock, max_upload_bytes=10**7
        )

        @contextmanager
        def services() -> Iterator[ExtractionService]:
            yield ExtractionService(self.repository, self.queue, clock=clock)

        self.services = services
        self.runner = ExtractionRunner(services, provider, max_attempts=max_attempts)

    def upload(self, content: bytes = b"%PDF-1.4 test", name: str = "invoice.pdf") -> Invoice:
        return self.intake.upload(filename=name, content=content, uploaded_by=USER)

    def stored(self, invoice: Invoice) -> Invoice:
        stored = self.repository.get(invoice.id)
        assert stored is not None
        return stored


def _good_output() -> dict[str, object]:
    output = empty_output()
    output["fields"]["vendor_name"] = "Acme"
    return output


@pytest.mark.parametrize("pdf", sorted(SAMPLES.glob("*.pdf")), ids=lambda path: path.stem)
def test_fake_extraction_of_every_sample_matches_its_ground_truth(pdf: Path) -> None:
    truth = load_ground_truth(json.loads(pdf.with_suffix(".json").read_text(encoding="utf-8")))
    world = World(FakeExtractionProvider(SAMPLES))
    invoice = world.upload(pdf.read_bytes(), pdf.name)

    outcome = world.runner.run(invoice.id, attempt=1)

    assert outcome.result is AttemptResult.ACCEPTED
    stored = world.stored(invoice)
    assert stored.fields == truth.fields
    assert stored.status is S.NEEDS_REVIEW
    assert [(e.action, e.to_status) for e in stored.events] == [
        (AuditAction.STATUS_CHANGED, S.UPLOADED),
        (AuditAction.STATUS_CHANGED, S.EXTRACTING),
        (AuditAction.EXTRACTION_RECORDED, None),
        (AuditAction.STATUS_CHANGED, S.NEEDS_REVIEW),
    ]
    assert stored.events[2].actor.name == "fake:ground-truth"
    assert set(stored.extraction_confidence or {}) == set(FIELD_NAMES)


def test_provider_error_asks_for_a_retry_and_leaves_the_invoice_extracting() -> None:
    world = World(ScriptedProvider(ExtractionProviderError("timeout")))
    invoice = world.upload()

    outcome = world.runner.run(invoice.id, attempt=1)

    assert (outcome.result, outcome.detail) == (AttemptResult.RETRY, "provider error: timeout")
    assert world.stored(invoice).status is S.EXTRACTING  # visible as in progress


def test_rejected_output_is_recorded_then_retried_until_accepted() -> None:
    world = World(ScriptedProvider({"fields": "garbage"}, _good_output()))
    invoice = world.upload()

    first = world.runner.run(invoice.id, attempt=1)
    second = world.runner.run(invoice.id, attempt=2)

    assert first.result is AttemptResult.RETRY
    assert first.detail.startswith("output rejected: output is missing confidence")
    assert second.result is AttemptResult.ACCEPTED
    stored = world.stored(invoice)
    assert stored.status is S.NEEDS_REVIEW
    assert stored.fields.vendor_name == "Acme"
    actions = [e.action for e in stored.events]
    assert actions.count(AuditAction.EXTRACTION_REJECTED) == 1
    assert actions.count(AuditAction.EXTRACTION_RECORDED) == 1


@pytest.mark.parametrize(
    ("failure", "last"),
    [
        (ExtractionProviderError("timeout"), "last provider error: timeout"),
        ("not json", "last output rejected: output must be a JSON object"),
    ],
    ids=["provider-error", "rejected-output"],
)
def test_the_last_allowed_attempt_marks_the_invoice_failed(failure: object, last: str) -> None:
    world = World(ScriptedProvider(failure, failure), max_attempts=2)
    invoice = world.upload()

    assert world.runner.run(invoice.id, attempt=1).result is AttemptResult.RETRY
    outcome = world.runner.run(invoice.id, attempt=2)

    assert outcome.result is AttemptResult.FAILED
    stored = world.stored(invoice)
    assert stored.status is S.FAILED
    failed = stored.events[-1]
    assert (failed.to_status, failed.actor.kind) == (S.FAILED, ActorKind.SYSTEM)
    assert failed.reason == f"extraction failed after 2 attempt(s); {last}"


def test_a_duplicate_job_for_a_finished_invoice_is_skipped() -> None:
    provider = ScriptedProvider(_good_output())
    world = World(provider)
    invoice = world.upload()
    world.runner.run(invoice.id, attempt=1)

    outcome = world.runner.run(invoice.id, attempt=1)

    assert outcome.result is AttemptResult.SKIPPED
    assert "needs_review" in outcome.detail
    assert provider.calls == 1  # the model was not asked again


def test_a_job_for_an_unknown_invoice_is_skipped() -> None:
    world = World(ScriptedProvider())

    assert world.runner.run(uuid4(), attempt=1).result is AttemptResult.SKIPPED


def test_max_attempts_must_be_positive() -> None:
    world = World(ScriptedProvider())

    with pytest.raises(ValueError):
        ExtractionRunner(world.services, ScriptedProvider(), max_attempts=0)


# Requests from the API ---------------------------------------------------------------------


def test_requesting_extraction_for_a_failed_invoice_records_who_asked() -> None:
    world = World(ScriptedProvider())
    failed = invoice_in(S.FAILED)
    world.repository.add(failed, PDF)

    with world.services() as service:
        service.request(failed.id, requested_by=USER)

    stored = world.stored(failed)
    assert stored.status is S.EXTRACTING
    assert (stored.events[-1].from_status, stored.events[-1].actor) == (S.FAILED, USER)
    assert world.queue.queued == [failed.id]


@pytest.mark.parametrize("status", [S.UPLOADED, S.EXTRACTING])
def test_requesting_extraction_while_waiting_only_queues(status: InvoiceStatus) -> None:
    world = World(ScriptedProvider())
    invoice = invoice_in(status)
    world.repository.add(invoice, PDF)

    with world.services() as service:
        service.request(invoice.id, requested_by=USER)

    assert world.stored(invoice).events == invoice.events
    assert world.queue.queued == [invoice.id]


@pytest.mark.parametrize("status", [S.NEEDS_REVIEW, S.APPROVED, S.REJECTED, S.EXPORTED])
def test_requesting_extraction_after_it_is_done_is_refused(status: InvoiceStatus) -> None:
    world = World(ScriptedProvider())
    invoice = invoice_in(status)
    world.repository.add(invoice, PDF)

    with pytest.raises(NotExtractableError), world.services() as service:
        service.request(invoice.id, requested_by=USER)

    assert world.queue.queued == []


def test_requesting_extraction_for_an_unknown_invoice_is_not_found() -> None:
    with pytest.raises(InvoiceNotFoundError), World(ScriptedProvider()).services() as service:
        service.request(uuid4(), requested_by=USER)


def test_sweep_requeues_only_old_uploads() -> None:
    world = World(ScriptedProvider())
    old = world.upload()  # uploaded at minute 101
    world.queue.queued.clear()  # pretend its job was lost
    young = world.upload()  # uploaded at minute 102
    world.queue.queued.clear()

    with world.services() as service:
        queued = service.requeue_stale_uploads(older_than=at(102))

    assert (queued, world.queue.queued) == (1, [old.id])
    assert young.id not in world.queue.queued
