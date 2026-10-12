import json
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pytest
from samplegen.ground_truth import load_ground_truth

from invoice_intake.domain import (
    FIELD_NAMES,
    ActorKind,
    AuditAction,
    ExtractionProvider,
    ExtractionProviderError,
    Invoice,
    InvoiceFields,
    InvoiceStatus,
    empty_output,
)
from invoice_intake.infrastructure.extraction import FakeExtractionProvider
from invoice_intake.services.extraction import ExtractionService, NotExtractableError
from invoice_intake.services.intake import IntakeService, InvoiceNotFoundError

from .domain_helpers import ACTORS, at
from .fakes import InMemoryInvoiceRepository, ScriptedProvider

SAMPLES = Path(__file__).resolve().parents[2] / "samples" / "invoices"
S = InvoiceStatus


class Clock:
    """Each call is one minute later, so audit times are distinct and ordered."""

    def __init__(self) -> None:
        self.minute = 0

    def __call__(self) -> datetime:
        self.minute += 1
        return at(self.minute)


def _setup(
    provider: ExtractionProvider,
) -> tuple[IntakeService, ExtractionService, InMemoryInvoiceRepository]:
    repository = InMemoryInvoiceRepository()
    clock = Clock()
    intake = IntakeService(repository, clock=clock, max_upload_bytes=10_000_000)
    extraction = ExtractionService(repository, provider, clock=clock)
    return intake, extraction, repository


def _upload(intake: IntakeService, content: bytes, name: str = "invoice.pdf") -> Invoice:
    return intake.upload(filename=name, content=content, uploaded_by=ACTORS[ActorKind.USER])


@pytest.mark.parametrize("pdf", sorted(SAMPLES.glob("*.pdf")), ids=lambda path: path.stem)
def test_fake_extraction_of_every_sample_matches_its_ground_truth(pdf: Path) -> None:
    truth = load_ground_truth(json.loads(pdf.with_suffix(".json").read_text(encoding="utf-8")))
    intake, extraction, repository = _setup(FakeExtractionProvider(SAMPLES))
    invoice = _upload(intake, pdf.read_bytes(), pdf.name)

    outcome = extraction.extract(invoice.id)

    assert outcome.accepted and outcome.errors == ()
    stored = repository.get(invoice.id)
    assert stored is not None
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


def test_rejected_output_is_recorded_and_a_retry_can_succeed() -> None:
    good = empty_output()
    good["fields"]["vendor_name"] = "Acme"
    provider = ScriptedProvider({"fields": "garbage"}, good)
    intake, extraction, repository = _setup(provider)
    invoice = _upload(intake, b"%PDF-1.4 test")

    first = extraction.extract(invoice.id)

    assert not first.accepted
    assert first.errors == ("output is missing confidence",)
    stored = repository.get(invoice.id)
    assert stored is not None
    assert stored.status is S.EXTRACTING  # waiting for another attempt
    assert stored.fields == InvoiceFields()
    rejected = stored.events[-1]
    assert rejected.action is AuditAction.EXTRACTION_REJECTED
    assert rejected.details is not None
    assert rejected.details["output"] == {"fields": "garbage"}
    assert rejected.details["errors"] == ["output is missing confidence"]

    second = extraction.extract(invoice.id)

    assert second.accepted
    final = repository.get(invoice.id)
    assert final is not None and final.status is S.NEEDS_REVIEW
    assert final.fields.vendor_name == "Acme"
    assert [e.action for e in final.events].count(AuditAction.EXTRACTION_REJECTED) == 1


def test_provider_failure_changes_nothing() -> None:
    intake, extraction, repository = _setup(ScriptedProvider(ExtractionProviderError("down")))
    invoice = _upload(intake, b"%PDF-1.4 test")

    with pytest.raises(ExtractionProviderError):
        extraction.extract(invoice.id)

    stored = repository.get(invoice.id)
    assert stored is not None
    assert stored.status is S.UPLOADED
    assert len(stored.events) == 1


def test_finished_invoices_cannot_be_extracted_again() -> None:
    provider = ScriptedProvider(empty_output(), empty_output())
    intake, extraction, _ = _setup(provider)
    invoice = _upload(intake, b"%PDF-1.4 test")
    extraction.extract(invoice.id)

    with pytest.raises(NotExtractableError, match="needs_review"):
        extraction.extract(invoice.id)
    assert provider.calls == 1


def test_unknown_invoice_is_not_found() -> None:
    _, extraction, _ = _setup(ScriptedProvider())

    with pytest.raises(InvoiceNotFoundError):
        extraction.extract(uuid4())
