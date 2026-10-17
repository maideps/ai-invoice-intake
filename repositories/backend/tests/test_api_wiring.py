"""API behaviour that does not need a database: who acts, commit-before-response, docs."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import timedelta

from fastapi.testclient import TestClient

from invoice_intake.domain import Role
from invoice_intake.main import create_app
from invoice_intake.services.accounts import AccountService
from invoice_intake.services.intake import IntakeService

from .app_helpers import FAST_PASSWORD_COST, TEST_PASSWORD
from .domain_helpers import at
from .fakes import (
    InMemoryAccountRepository,
    InMemoryInvoiceRepository,
    InMemorySessionRepository,
    RecordingQueue,
)
from .helpers import IsolatedSettings

PDF = b"%PDF-1.4\n%test\n"


class CommitFailed(RuntimeError):
    pass


def _client(*, fail_commit: bool = False) -> tuple[TestClient, InMemoryInvoiceRepository]:
    repository = InMemoryInvoiceRepository()

    @contextmanager
    def factory() -> Iterator[IntakeService]:
        yield IntakeService(
            repository, RecordingQueue(), clock=lambda: at(0), max_upload_bytes=1000
        )
        if fail_commit:
            raise CommitFailed("database went away during commit")

    accounts, sessions = InMemoryAccountRepository(), InMemorySessionRepository()

    @contextmanager
    def account_factory() -> Iterator[AccountService]:
        yield AccountService(
            accounts,
            sessions,
            clock=lambda: at(0),
            session_ttl=timedelta(hours=1),
            password_cost=FAST_PASSWORD_COST,
        )

    with account_factory() as service:
        service.create_account(
            username="reviewer", display_name="Ria", role=Role.REVIEWER, password=TEST_PASSWORD
        )
    app = create_app(
        IsolatedSettings(environment="test"),
        intake_service=factory,
        account_service=account_factory,
        extraction_queue=RecordingQueue(),
    )
    client = TestClient(app, raise_server_exceptions=False)
    signed_in = client.post(
        "/auth/sign-in", json={"username": "reviewer", "password": TEST_PASSWORD}
    )
    assert signed_in.status_code == 200
    return client, repository


def test_the_uploader_is_the_signed_in_account() -> None:
    client, _ = _client()

    response = client.post(
        "/invoices",
        files={"file": ("a.pdf", PDF, "application/pdf")},
        headers={"X-User": "someone-else"},  # the old header is ignored now
    )

    assert response.status_code == 201
    assert response.json()["events"][0]["actor_name"] == "reviewer"
    assert response.json()["events"][0]["actor_kind"] == "user"


def test_signed_out_requests_are_refused() -> None:
    client, _ = _client()
    client.post("/auth/sign-out")

    response = client.post("/invoices", files={"file": ("a.pdf", PDF, "application/pdf")})

    assert response.status_code == 401


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
