import json

from export_openapi import TARGET, openapi_document

from invoice_intake.domain import ActorKind, Document, InvoiceStatus
from invoice_intake.services.intake import IntakeService

from .domain_helpers import ACTORS, at, invoice_in
from .fakes import InMemoryInvoiceRepository, RecordingQueue

PDF = b"%PDF-1.4 test"


def _service(repository: InMemoryInvoiceRepository) -> IntakeService:
    return IntakeService(repository, RecordingQueue(), clock=lambda: at(0), max_upload_bytes=100)


def test_stats_list_every_status_even_when_empty() -> None:
    service = _service(InMemoryInvoiceRepository())
    service.upload(filename="a.pdf", content=PDF, uploaded_by=ACTORS[ActorKind.USER])
    service.upload(filename="b.pdf", content=PDF, uploaded_by=ACTORS[ActorKind.USER])

    stats = service.stats()

    assert set(stats) == set(InvoiceStatus)
    assert stats[InvoiceStatus.UPLOADED] == 2
    assert sum(stats.values()) == 2


def test_stats_count_each_status() -> None:
    repository = InMemoryInvoiceRepository()
    for status in (InvoiceStatus.NEEDS_REVIEW, InvoiceStatus.NEEDS_REVIEW, InvoiceStatus.FAILED):
        repository.add(invoice_in(status), Document("application/pdf", PDF))

    stats = _service(repository).stats()

    assert stats[InvoiceStatus.NEEDS_REVIEW] == 2
    assert stats[InvoiceStatus.FAILED] == 1
    assert stats[InvoiceStatus.APPROVED] == 0


def test_openapi_documents_the_stats_endpoint() -> None:
    paths = json.loads(openapi_document())["paths"]

    assert "/invoices/stats" in paths


def test_committed_openapi_matches_the_api() -> None:
    assert TARGET.is_file(), "run: npm run api:types"
    assert TARGET.read_text(encoding="utf-8") == openapi_document(), (
        "contracts/openapi.json is out of date; run: npm run api:types"
    )
