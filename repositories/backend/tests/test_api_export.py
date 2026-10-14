"""Export through the API against a real, migrated PostgreSQL."""

from collections.abc import Iterator
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from .app_helpers import SAMPLES, extract_now, make_app, sign_in
from .fakes import RecordingQueue

pytestmark = pytest.mark.postgres


@pytest.fixture
def queue() -> RecordingQueue:
    return RecordingQueue()


@pytest.fixture
def client(engine: Engine, queue: RecordingQueue) -> Iterator[TestClient]:
    with TestClient(make_app(engine, queue)) as client:
        sign_in(client, engine)
        yield client


def _in_review(client: TestClient, engine: Engine) -> dict[str, Any]:
    pdf = SAMPLES / "invoice-001.pdf"
    invoice_id = client.post(
        "/invoices", files={"file": (pdf.name, pdf.read_bytes(), "x/y")}
    ).json()["id"]
    extract_now(engine, UUID(invoice_id))
    body: dict[str, Any] = client.get(f"/invoices/{invoice_id}").json()
    return body


def test_approval_queues_an_export_and_shows_it_pending(
    client: TestClient, engine: Engine, queue: RecordingQueue
) -> None:
    invoice = _in_review(client, engine)
    assert invoice["export"] is None  # nothing to export before approval

    approved = client.post(
        f"/invoices/{invoice['id']}/approve", json={"version": invoice["version"]}
    ).json()

    assert approved["export"] == {
        "state": "pending",
        "attempts": 0,
        "last_error": None,
        "exported_at": None,
    }
    assert [str(i) for i in queue.exports] == [invoice["id"]]


def test_export_can_be_requested_again_for_an_approved_invoice(
    client: TestClient, engine: Engine, queue: RecordingQueue
) -> None:
    invoice = _in_review(client, engine)
    client.post(f"/invoices/{invoice['id']}/approve", json={"version": invoice["version"]})
    queue.exports.clear()

    response = client.post(f"/invoices/{invoice['id']}/export")

    assert response.status_code == 202
    assert [str(i) for i in queue.exports] == [invoice["id"]]


def test_export_is_refused_before_approval(
    client: TestClient, engine: Engine, queue: RecordingQueue
) -> None:
    invoice = _in_review(client, engine)

    response = client.post(f"/invoices/{invoice['id']}/export")

    assert response.status_code == 409
    assert "only approved invoices are exported" in response.json()["detail"]
    assert queue.exports == []


def test_unknown_invoice_is_404(client: TestClient) -> None:
    assert client.post(f"/invoices/{uuid4()}/export").status_code == 404


def test_health_says_whether_export_is_configured(engine: Engine) -> None:
    with TestClient(make_app(engine, export_webhook_url="http://localhost:9/hook")) as client:
        assert client.get("/health").json()["export_configured"] is True
