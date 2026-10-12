from uuid import uuid4

import pytest

from invoice_intake.domain import ActorKind, InvoiceRepository, InvoiceStatus
from invoice_intake.services.intake import (
    EmptyUploadError,
    IntakeService,
    InvoiceNotFoundError,
    UnsupportedFileTypeError,
    UploadTooLargeError,
    clean_filename,
    detect_content_type,
)

from .domain_helpers import ACTORS, at
from .fakes import InMemoryInvoiceRepository

PDF = b"%PDF-1.4\n%fake but starts like a PDF\n"
PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 16
JPEG = b"\xff\xd8\xff\xe0" + b"\0" * 16
USER = ACTORS[ActorKind.USER]


def _service(limit: int = 1000) -> tuple[IntakeService, InMemoryInvoiceRepository]:
    repository = InMemoryInvoiceRepository()
    _: InvoiceRepository = repository  # the fake must satisfy the domain interface
    return IntakeService(repository, clock=lambda: at(0), max_upload_bytes=limit), repository


def test_upload_stores_an_uploaded_invoice_with_its_document() -> None:
    service, repository = _service()

    invoice = service.upload(filename="acme.pdf", content=PDF, uploaded_by=USER)

    assert invoice.status is InvoiceStatus.UPLOADED
    assert invoice.filename == "acme.pdf"
    assert invoice.uploaded_at == at(0)
    assert invoice.events[0].actor == USER
    stored = repository.get(invoice.id)
    assert stored is not None and stored.events == invoice.events
    document = service.document(invoice.id)
    assert (document.content_type, document.content) == ("application/pdf", PDF)


@pytest.mark.parametrize(
    ("content", "kind"),
    [(PDF, "application/pdf"), (PNG, "image/png"), (JPEG, "image/jpeg")],
)
def test_accepted_types_are_detected_from_content(content: bytes, kind: str) -> None:
    assert detect_content_type(content) == kind


@pytest.mark.parametrize(
    "content",
    [b"GIF89a....", b"plain text", b"PK\x03\x04 a zip", b"%PDF", b"\x89PNG"],
)
def test_other_content_is_refused(content: bytes) -> None:
    service, repository = _service()

    with pytest.raises(UnsupportedFileTypeError):
        service.upload(filename="invoice.pdf", content=content, uploaded_by=USER)

    assert repository.invoices == {}


def test_empty_upload_is_refused() -> None:
    with pytest.raises(EmptyUploadError):
        _service()[0].upload(filename="a.pdf", content=b"", uploaded_by=USER)


def test_size_limit_is_inclusive() -> None:
    service, _ = _service(limit=len(PDF))

    service.upload(filename="a.pdf", content=PDF, uploaded_by=USER)
    with pytest.raises(UploadTooLargeError):
        service.upload(filename="a.pdf", content=PDF + b"x", uploaded_by=USER)


@pytest.mark.parametrize(
    ("raw", "cleaned"),
    [
        ("invoice.pdf", "invoice.pdf"),
        ("  spaced name.pdf  ", "spaced name.pdf"),
        ("C:\\Users\\someone\\invoice.pdf", "invoice.pdf"),
        ("../../etc/passwd", "passwd"),
        ("folder/", "unnamed"),
        ("", "unnamed"),
        (None, "unnamed"),
        ("x" * 300 + ".pdf", "x" * 255),
    ],
)
def test_filenames_are_cleaned(raw: str | None, cleaned: str) -> None:
    assert clean_filename(raw) == cleaned


def test_unknown_invoice_is_not_found() -> None:
    service, _ = _service()

    with pytest.raises(InvoiceNotFoundError):
        service.get(uuid4())
    with pytest.raises(InvoiceNotFoundError):
        service.document(uuid4())


def test_list_page_filters_and_pages() -> None:
    service, _ = _service()
    for name in ("a.pdf", "b.pdf", "c.pdf"):
        service.upload(filename=name, content=PDF, uploaded_by=USER)

    page = service.list_page(status=InvoiceStatus.UPLOADED, limit=2, offset=0)

    assert page.total == 3
    assert len(page.items) == 2
    assert service.list_page(status=InvoiceStatus.APPROVED, limit=10, offset=0).total == 0
