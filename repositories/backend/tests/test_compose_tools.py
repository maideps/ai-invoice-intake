"""The helper tools behind docker compose: the demo accounting receiver and the sample seeder."""

import threading
from collections.abc import Iterator
from typing import Any

import httpx2 as httpx
import pytest
from demo_receiver import Receiver, make_server
from fastapi.testclient import TestClient
from seed_samples import seed, sign_in, wait_for_api
from sqlalchemy import Engine

from invoice_intake.infrastructure.export_webhook import HttpWebhookSender, signature
from invoice_intake.services.export import ExportDeliveryError

from .app_helpers import SAMPLES, TEST_PASSWORD, add_account, make_app

PAYLOAD: dict[str, Any] = {
    "payload_version": 1,
    "invoice_id": "00000000-0000-4000-8000-000000000001",
    "filename": "invoice-001.pdf",
    "approved_by": "maide",
    "fields": {"vendor_name": "Acme", "currency": "CAD", "total": "10.00"},
}


@pytest.fixture
def receiver() -> Iterator[tuple[Receiver, str]]:
    state = Receiver(secret="s3cret")
    server = make_server(state, "127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield state, f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()


def test_the_receiver_books_a_delivery_signed_by_the_real_sender(
    receiver: tuple[Receiver, str],
) -> None:
    state, url = receiver
    sender = HttpWebhookSender(f"{url}/invoices", secret="s3cret")
    try:
        sender.send(PAYLOAD, idempotency_key=PAYLOAD["invoice_id"])
    finally:
        sender.close()

    listed = httpx.get(f"{url}/deliveries").json()
    assert listed == state.deliveries
    [delivery] = listed
    assert delivery["path"] == "/invoices"
    assert delivery["idempotency_key"] == PAYLOAD["invoice_id"]
    assert delivery["signed"] is True
    assert delivery["payload"] == PAYLOAD


def test_the_receiver_refuses_a_wrong_signature(receiver: tuple[Receiver, str]) -> None:
    state, url = receiver
    sender = HttpWebhookSender(url, secret="not-the-secret")
    try:
        with pytest.raises(ExportDeliveryError) as error:
            sender.send(PAYLOAD, idempotency_key="x")
    finally:
        sender.close()

    assert error.value.status_code == 401
    assert state.deliveries == []


def test_the_receiver_refuses_an_unsigned_delivery_when_it_has_a_secret(
    receiver: tuple[Receiver, str],
) -> None:
    state, url = receiver

    assert httpx.post(url, json=PAYLOAD).status_code == 401
    assert state.deliveries == []


def test_without_a_secret_the_receiver_accepts_unsigned_json() -> None:
    state = Receiver()

    assert state.signature_ok(b"{}", None)
    state.record("/", {}, b'{"a": 1}')
    assert state.deliveries[0]["signed"] is False


def test_the_receiver_rejects_a_body_that_is_not_json(receiver: tuple[Receiver, str]) -> None:
    state, url = receiver
    body = b"not json"
    headers = {"X-Invoice-Intake-Signature": signature(state.secret or "", body)}

    assert httpx.post(url, content=body, headers=headers).status_code == 400


def test_waiting_for_the_api_gives_up_with_a_clear_message() -> None:
    down = httpx.Client(
        base_url="http://api",
        transport=httpx.MockTransport(lambda request: httpx.Response(503)),
    )

    with pytest.raises(TimeoutError, match="did not answer within 0 s"):
        wait_for_api(down, timeout_seconds=0)


@pytest.mark.postgres
def test_seeding_signs_in_and_uploads_every_sample_once(engine: Engine) -> None:
    add_account(engine, "seeder")
    with TestClient(make_app(engine)) as client:
        sign_in(client, "seeder", TEST_PASSWORD)
        first = seed(client, SAMPLES)
        second = seed(client, SAMPLES)
        listed = client.get("/invoices", params={"limit": 50}).json()
        detail = client.get(f"/invoices/{listed['items'][0]['id']}").json()

    assert first == sorted(path.name for path in SAMPLES.glob("*.pdf"))
    assert len(first) == 12
    assert second == []  # an instance with invoices is left alone
    assert listed["total"] == 12
    assert detail["events"][0]["actor_name"] == "seeder"  # recorded as the signed-in account


@pytest.mark.postgres
def test_seeding_with_a_wrong_password_says_so(engine: Engine) -> None:
    add_account(engine, "seeder")
    with TestClient(make_app(engine)) as client, pytest.raises(PermissionError, match="seeder"):
        sign_in(client, "seeder", "not the password")
