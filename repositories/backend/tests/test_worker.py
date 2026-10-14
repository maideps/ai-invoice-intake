"""The worker end to end: API, PostgreSQL, Redis queue and worker loop together."""

import json
import threading
import time
from collections.abc import Callable, Iterator
from datetime import timedelta
from typing import Any
from uuid import UUID

import pytest
import redis
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from invoice_intake.domain import Document, ExtractionProvider, ExtractionProviderError
from invoice_intake.infrastructure.extraction import FakeExtractionProvider
from invoice_intake.infrastructure.queue import RedisExtractionQueue
from invoice_intake.main import create_app
from invoice_intake.worker import STALE_UPLOAD_GRACE, Worker, backoff_seconds, build_worker

from .app_helpers import SAMPLES, database_url, sign_in
from .fakes import ScriptedProvider
from .helpers import IsolatedSettings
from .webhook_server import Webhook

pytestmark = [pytest.mark.postgres, pytest.mark.redis]


def _settings(engine: Engine, redis_url: str, **overrides: Any) -> IsolatedSettings:
    values: dict[str, Any] = {
        "environment": "test",
        "database_url": database_url(engine),
        "redis_url": redis_url,
        "extraction_retry_base_seconds": 0,  # retry at once: tests should not sleep
        **overrides,
    }
    return IsolatedSettings(**values)


@pytest.fixture
def run_worker(
    engine: Engine, redis_url: str, redis_client: redis.Redis
) -> Iterator[Callable[..., Worker]]:
    """Start a worker in a background thread; it is stopped when the test ends."""
    stops: list[tuple[threading.Event, threading.Thread, Worker]] = []

    def start(
        provider: ExtractionProvider,
        *,
        stale_upload_grace: timedelta = STALE_UPLOAD_GRACE,
        **overrides: Any,
    ) -> Worker:
        settings = _settings(engine, redis_url, **overrides)
        worker = build_worker(settings, provider=provider, stale_upload_grace=stale_upload_grace)
        stop = threading.Event()
        thread = threading.Thread(target=worker.run, args=(stop,), kwargs={"poll_seconds": 0.1})
        thread.start()
        stops.append((stop, thread, worker))
        return worker

    yield start
    for stop, thread, worker in stops:
        stop.set()
        thread.join(timeout=10)
        worker.close()


@pytest.fixture
def client(engine: Engine, redis_url: str) -> Iterator[TestClient]:
    with TestClient(create_app(_settings(engine, redis_url))) as client:  # the real Redis queue
        sign_in(client, engine)
        yield client


def _upload(client: TestClient, sample: str = "invoice-002.pdf") -> dict[str, Any]:
    pdf = SAMPLES / sample
    response = client.post("/invoices", files={"file": (pdf.name, pdf.read_bytes(), "x/y")})
    assert response.status_code == 201
    body: dict[str, Any] = response.json()
    return body


def _wait_for(
    client: TestClient, invoice_id: str, status: str, timeout: float = 15
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        body: dict[str, Any] = client.get(f"/invoices/{invoice_id}").json()
        if body["status"] == status:
            return body
        time.sleep(0.1)
    raise AssertionError(f"invoice {invoice_id} never reached {status}; last: {body['status']}")


def test_upload_returns_at_once_and_the_worker_finishes_extraction(
    client: TestClient, run_worker: Callable[..., Worker]
) -> None:
    created = _upload(client)
    assert created["status"] == "uploaded"  # the request did not wait for the model

    run_worker(FakeExtractionProvider(SAMPLES))
    done = _wait_for(client, created["id"], "needs_review")

    assert done["fields"]["vendor_name"] is not None
    statuses = [e["to_status"] for e in done["events"] if e["action"] == "status_changed"]
    assert statuses == ["uploaded", "extracting", "needs_review"]


def test_a_failing_provider_is_retried_then_the_invoice_fails(
    client: TestClient, run_worker: Callable[..., Worker]
) -> None:
    provider = ScriptedProvider(*[ExtractionProviderError("model unavailable")] * 3)
    created = _upload(client)

    run_worker(provider, extraction_max_attempts=3)
    failed = _wait_for(client, created["id"], "failed")

    assert provider.calls == 3
    assert failed["events"][-1]["reason"] == (
        "extraction failed after 3 attempt(s); last provider error: model unavailable"
    )
    assert failed["events"][-1]["actor_kind"] == "system"


def test_rejected_output_counts_as_a_failed_attempt(
    client: TestClient, run_worker: Callable[..., Worker]
) -> None:
    created = _upload(client)

    run_worker(ScriptedProvider("not json", "still not json"), extraction_max_attempts=2)
    failed = _wait_for(client, created["id"], "failed")

    actions = [e["action"] for e in failed["events"]]
    assert actions.count("extraction_rejected") == 2


def test_a_retry_requested_through_the_api_runs_again(
    client: TestClient, run_worker: Callable[..., Worker]
) -> None:
    pdf = SAMPLES / "invoice-002.pdf"
    good = FakeExtractionProvider(SAMPLES).extract(Document("application/pdf", pdf.read_bytes()))
    created = _upload(client)
    run_worker(
        ScriptedProvider(ExtractionProviderError("down"), good.output),
        extraction_max_attempts=1,
    )
    _wait_for(client, created["id"], "failed")

    client.post(f"/invoices/{created['id']}/extract")

    _wait_for(client, created["id"], "needs_review")


def test_the_sweep_queues_uploads_whose_job_was_lost(
    engine: Engine, redis_url: str, redis_client: redis.Redis, run_worker: Callable[..., Worker]
) -> None:
    # Upload while Redis is unreachable: the upload still succeeds, nothing is queued.
    offline = _settings(engine, "redis://127.0.0.1:1/0")
    with TestClient(create_app(offline)) as offline_client:
        sign_in(offline_client, engine)
        created = _upload(offline_client)
    assert created["status"] == "uploaded"

    worker = build_worker(_settings(engine, redis_url), provider=FakeExtractionProvider(SAMPLES))
    try:
        assert worker.sweep() == 0  # too recent: its job may still be on its way
    finally:
        worker.close()

    run_worker(FakeExtractionProvider(SAMPLES), stale_upload_grace=timedelta(0))  # sweeps on start
    with TestClient(create_app(_settings(engine, redis_url))) as client:
        sign_in(client, engine)
        _wait_for(client, created["id"], "needs_review")


def test_backoff_doubles() -> None:
    assert [backoff_seconds(5, attempt) for attempt in (1, 2, 3)] == [5, 10, 20]


def test_the_api_queue_is_redis(redis_url: str, redis_client: redis.Redis) -> None:
    queue = RedisExtractionQueue.from_url(redis_url)
    invoice_id = UUID(int=7)

    queue.enqueue(invoice_id)

    assert redis_client.lrange(queue.ready_key, 0, -1) == [
        '{"attempt": 1, "invoice_id": "00000000-0000-0000-0000-000000000007", "kind": "extract"}'
    ]


def _approve(client: TestClient, invoice_id: str) -> None:
    current = client.get(f"/invoices/{invoice_id}").json()
    response = client.post(f"/invoices/{invoice_id}/approve", json={"version": current["version"]})
    assert response.status_code == 200, response.text


def test_an_approved_invoice_is_delivered_once_and_marked_exported(
    client: TestClient, run_worker: Callable[..., Worker], webhook: Webhook
) -> None:
    created = _upload(client)
    run_worker(
        FakeExtractionProvider(SAMPLES),
        export_webhook_url=webhook.url,
        export_webhook_secret="s3cret",
    )
    _wait_for(client, created["id"], "needs_review")
    assert webhook.deliveries == []  # nothing goes out before approval

    _approve(client, created["id"])
    exported = _wait_for(client, created["id"], "exported")

    (delivery,) = webhook.deliveries
    payload = json.loads(delivery.body)
    assert payload["invoice_id"] == created["id"]
    assert payload["fields"] == exported["fields"]
    assert delivery.headers["Idempotency-Key"] == created["id"]
    assert delivery.headers["X-Invoice-Intake-Signature"].startswith("sha256=")
    assert exported["export"]["state"] == "exported"
    assert exported["events"][-1]["actor_name"] == "export-service"


def test_failed_deliveries_are_retried_and_recorded(
    client: TestClient, run_worker: Callable[..., Worker], webhook: Webhook
) -> None:
    webhook.statuses = [503, 503]
    created = _upload(client)
    run_worker(
        FakeExtractionProvider(SAMPLES),
        export_webhook_url=webhook.url,
        export_retry_base_seconds=0,
        export_max_attempts=5,
    )
    _wait_for(client, created["id"], "needs_review")

    _approve(client, created["id"])
    exported = _wait_for(client, created["id"], "exported")

    assert len(webhook.deliveries) == 3
    failures = [e for e in exported["events"] if e["action"] == "export_failed"]
    assert [f["details"]["attempt"] for f in failures] == [1, 2]
    assert failures[0]["details"]["error"] == "HTTP 503: temporarily unavailable"
    assert exported["export"]["attempts"] == 2


def test_without_a_webhook_approved_invoices_wait(
    client: TestClient, run_worker: Callable[..., Worker]
) -> None:
    created = _upload(client)
    run_worker(FakeExtractionProvider(SAMPLES))  # no export_webhook_url
    _wait_for(client, created["id"], "needs_review")

    _approve(client, created["id"])
    time.sleep(1.5)

    waiting = client.get(f"/invoices/{created['id']}").json()
    assert waiting["status"] == "approved"
    assert waiting["export"]["state"] == "pending"
