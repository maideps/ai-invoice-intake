"""API behaviour that does not need a database: headers, commit-before-response, docs."""

from collections.abc import Iterator
from contextlib import contextmanager

from fastapi.testclient import TestClient

from invoice_intake.main import create_app
from invoice_intake.services.intake import IntakeService

from .domain_helpers import at
from .fakes import InMemoryInvoiceRepository
from .helpers import IsolatedSettings

PDF = b"%PDF-1.4\n%test\n"


class CommitFailed(RuntimeError):
    pass


def _client(*, fail_commit: bool = False) -> tuple[TestClient, InMemoryInvoiceRepository]:
    repository = InMemoryInvoiceRepository()

    @contextmanager
    def factory() -> Iterator[IntakeService]:
        yield IntakeService(repository, clock=lambda: at(0), max_upload_bytes=1000)
        if fail_commit:
            raise CommitFailed("database went away during commit")

    app = create_app(IsolatedSettings(environment="test"), intake_service=factory)
    return TestClient(app, raise_server_exceptions=False), repository


def test_uploader_comes_from_the_x_user_header() -> None:
    client, _ = _client()

    response = client.post(
        "/invoices",
        files={"file": ("a.pdf", PDF, "application/pdf")},
        headers={"X-User": "  reviewer@example.com  "},
    )

    assert response.status_code == 201
    assert response.json()["events"][0]["actor_name"] == "reviewer@example.com"
    assert response.json()["events"][0]["actor_kind"] == "user"


def test_missing_user_header_is_recorded_as_anonymous() -> None:
    client, _ = _client()

    response = client.post("/invoices", files={"file": ("a.pdf", PDF, "application/pdf")})

    assert response.json()["events"][0]["actor_name"] == "anonymous"


def test_a_failed_commit_is_an_error_not_a_success() -> None:
    # The service context closes (and commits) before the response is sent, so a commit
    # failure reaches the client instead of a 201 for data that was never stored.
    client, _ = _client(fail_commit=True)

    response = client.post("/invoices", files={"file": ("a.pdf", PDF, "application/pdf")})

    assert response.status_code == 500


def test_openapi_documents_the_invoice_endpoints() -> None:
    client, _ = _client()

    paths = client.get("/openapi.json").json()["paths"]

    assert {"/invoices", "/invoices/{invoice_id}", "/invoices/{invoice_id}/events"} <= set(paths)
    assert "/invoices/{invoice_id}/document" in paths
