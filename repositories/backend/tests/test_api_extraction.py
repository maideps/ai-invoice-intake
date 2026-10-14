"""Extraction through the API (queueing) and the worker's steps, against a real PostgreSQL."""

import json
from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from invoice_intake.domain import FIELD_NAMES, ExtractionProviderError
from invoice_intake.services.extraction import AttemptResult

from .app_helpers import SAMPLES, extract_now, make_app, sign_in
from .fakes import RecordingQueue, ScriptedProvider

pytestmark = pytest.mark.postgres


@pytest.fixture
def queue() -> RecordingQueue:
    return RecordingQueue()


@pytest.fixture
def client(engine: Engine, queue: RecordingQueue) -> Iterator[TestClient]:
    with TestClient(make_app(engine, queue)) as client:
        sign_in(client, engine)
        yield client


def _upload(client: TestClient, sample: str = "invoice-007.pdf") -> UUID:
    pdf = SAMPLES / sample
    response = client.post("/invoices", files={"file": (pdf.name, pdf.read_bytes(), "x/y")})
    assert response.status_code == 201
    return UUID(response.json()["id"])


def test_worker_result_is_visible_through_the_api(client: TestClient, engine: Engine) -> None:
    truth = json.loads((SAMPLES / "invoice-007.json").read_text(encoding="utf-8"))
    invoice_id = _upload(client)

    assert extract_now(engine, invoice_id).result is AttemptResult.ACCEPTED

    invoice = client.get(f"/invoices/{invoice_id}").json()
    assert invoice["status"] == "needs_review"
    assert invoice["fields"] == truth["fields"]
    assert set(invoice["confidence"]) == set(FIELD_NAMES)
    recorded = invoice["events"][2]
    assert (recorded["action"], recorded["actor_kind"]) == ("extraction_recorded", "ai")
    assert recorded["details"]["fields"] == truth["fields"]


def test_failed_extraction_then_a_retry_requested_by_a_person(
    client: TestClient, engine: Engine, queue: RecordingQueue
) -> None:
    invoice_id = _upload(client)
    queue.queued.clear()
    down = ScriptedProvider(ExtractionProviderError("OpenAI request failed: timeout"))

    outcome = extract_now(engine, invoice_id, max_attempts=1, provider=down)

    assert outcome.result is AttemptResult.FAILED
    failed = client.get(f"/invoices/{invoice_id}").json()
    assert failed["status"] == "failed"
    assert "provider error: OpenAI request failed: timeout" in failed["events"][-1]["reason"]

    sign_in(client, engine, "alice")
    response = client.post(f"/invoices/{invoice_id}/extract")

    assert response.status_code == 202
    retried = response.json()
    assert retried["status"] == "extracting"
    last = retried["events"][-1]
    assert (last["from_status"], last["to_status"], last["actor_name"]) == (
        "failed",
        "extracting",
        "alice",
    )
    assert queue.queued == [invoice_id]  # handed to the queue after the commit
    assert client.get(f"/invoices/{invoice_id}").json() == retried


def test_requesting_extraction_for_a_waiting_invoice_only_queues_it(
    client: TestClient, queue: RecordingQueue
) -> None:
    invoice_id = _upload(client)
    queue.queued.clear()

    response = client.post(f"/invoices/{invoice_id}/extract")

    assert response.status_code == 202
    assert response.json()["status"] == "uploaded"
    assert len(response.json()["events"]) == 1
    assert queue.queued == [invoice_id]


def test_extraction_is_refused_once_done(
    client: TestClient, engine: Engine, queue: RecordingQueue
) -> None:
    invoice_id = _upload(client)
    extract_now(engine, invoice_id)
    queue.queued.clear()

    response = client.post(f"/invoices/{invoice_id}/extract")

    assert response.status_code == 409
    assert "needs_review" in response.json()["detail"]
    assert queue.queued == []


def test_unknown_invoice_is_404(client: TestClient) -> None:
    assert client.post(f"/invoices/{uuid4()}/extract").status_code == 404


def test_rejected_output_is_recorded_in_the_trail(client: TestClient, engine: Engine) -> None:
    invoice_id = _upload(client)

    outcome = extract_now(engine, invoice_id, provider=ScriptedProvider("not json at all"))

    assert outcome.result is AttemptResult.RETRY
    stored = client.get(f"/invoices/{invoice_id}").json()
    assert stored["status"] == "extracting"
    assert stored["confidence"] is None
    rejected = stored["events"][-1]
    assert rejected["action"] == "extraction_rejected"
    assert rejected["details"]["output"] == "not json at all"
    assert rejected["details"]["errors"] == ["output must be a JSON object"]
