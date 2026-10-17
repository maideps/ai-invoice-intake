"""The intake API against a real, migrated PostgreSQL."""

from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from .app_helpers import make_app, sign_in
from .fakes import RecordingQueue

pytestmark = pytest.mark.postgres

SAMPLE = Path(__file__).resolve().parents[3] / "samples" / "invoices" / "invoice-001.pdf"
PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 32


@pytest.fixture
def queue() -> RecordingQueue:
    return RecordingQueue()


@pytest.fixture
def client(engine: Engine, queue: RecordingQueue) -> Iterator[TestClient]:
    with TestClient(make_app(engine, queue, max_upload_bytes=64 * 1024)) as client:
        sign_in(client, engine)
        yield client


def test_upload_is_queued_for_extraction_and_returns_at_once(
    client: TestClient, queue: RecordingQueue
) -> None:
    created = client.post(
        "/invoices", files={"file": (SAMPLE.name, SAMPLE.read_bytes(), "application/pdf")}
    ).json()
    client.post("/invoices", files={"file": ("bad.txt", b"not an invoice", "text/plain")})

    assert created["status"] == "uploaded"  # extraction happens later, in the worker
    assert [str(invoice_id) for invoice_id in queue.queued] == [created["id"]]


def test_upload_a_sample_then_read_it_back_with_its_audit_event(client: TestClient) -> None:
    pdf = SAMPLE.read_bytes()

    created = client.post(
        "/invoices",
        files={"file": (SAMPLE.name, pdf, "application/pdf")},
    )

    assert created.status_code == 201
    body = created.json()
    invoice_id = body["id"]
    assert created.headers["location"].endswith(f"/invoices/{invoice_id}")
    assert body["status"] == "uploaded"
    assert body["filename"] == "invoice-001.pdf"

    fetched = client.get(f"/invoices/{invoice_id}")
    assert fetched.status_code == 200
    assert fetched.json() == body  # what was returned is what was stored

    (event,) = client.get(f"/invoices/{invoice_id}/events").json()
    assert event["sequence"] == 1
    assert event["action"] == "status_changed"
    assert (event["from_status"], event["to_status"]) == (None, "uploaded")
    assert (event["actor_kind"], event["actor_name"]) == ("user", "maide")  # signed in

    document = client.get(f"/invoices/{invoice_id}/document")
    assert document.status_code == 200
    assert document.headers["content-type"] == "application/pdf"
    assert document.content == pdf


def test_content_type_comes_from_the_bytes_not_the_client(client: TestClient) -> None:
    created = client.post("/invoices", files={"file": ("scan.pdf", PNG, "application/pdf")}).json()

    document = client.get(f"/invoices/{created['id']}/document")

    assert document.headers["content-type"] == "image/png"


def test_fields_are_empty_until_extraction(client: TestClient) -> None:
    body = client.post(
        "/invoices", files={"file": ("a.pdf", SAMPLE.read_bytes(), "application/pdf")}
    ).json()

    assert body["fields"] == {
        "vendor_name": None,
        "invoice_number": None,
        "issue_date": None,
        "due_date": None,
        "currency": None,
        "subtotal": None,
        "tax": None,
        "total": None,
        "line_items": [],
    }


@pytest.mark.parametrize(
    ("content", "status"),
    [
        (b"", 400),
        (b"%PDF-" + b"x" * (64 * 1024), 413),
        (b"GIF89a not accepted", 415),
        (b"just some text", 415),
    ],
    ids=["empty", "too-large", "gif", "text"],
)
def test_rejected_uploads_store_nothing(client: TestClient, content: bytes, status: int) -> None:
    response = client.post("/invoices", files={"file": ("a.pdf", content, "application/pdf")})

    assert response.status_code == status
    assert "detail" in response.json()
    assert client.get("/invoices").json()["total"] == 0


def test_missing_file_is_a_validation_error(client: TestClient) -> None:
    assert client.post("/invoices").status_code == 422


@pytest.mark.parametrize("suffix", ["", "/events", "/document"])
def test_unknown_invoice_is_404(client: TestClient, suffix: str) -> None:
    assert client.get(f"/invoices/{uuid4()}{suffix}").status_code == 404


def test_malformed_id_is_422(client: TestClient) -> None:
    assert client.get("/invoices/not-a-uuid").status_code == 422


def test_list_is_newest_first_with_paging_and_status_filter(client: TestClient) -> None:
    pdf = SAMPLE.read_bytes()
    ids = [
        client.post("/invoices", files={"file": (f"{n}.pdf", pdf, "application/pdf")}).json()["id"]
        for n in range(3)
    ]

    page = client.get("/invoices", params={"limit": 2}).json()
    rest = client.get("/invoices", params={"limit": 2, "offset": 2}).json()
    uploaded = client.get("/invoices", params={"status": "uploaded"}).json()
    approved = client.get("/invoices", params={"status": "approved"}).json()

    assert (page["total"], page["limit"], page["offset"]) == (3, 2, 0)
    listed = page["items"] + rest["items"]
    assert sorted(item["id"] for item in listed) == sorted(ids)
    times = [item["uploaded_at"] for item in listed]
    assert times == sorted(times, reverse=True)  # newest first (ties possible within a clock tick)
    assert set(page["items"][0]) == {
        "id", "filename", "status", "uploaded_at", "vendor_name", "currency", "total",
    }  # fmt: skip
    assert uploaded["total"] == 3
    assert (approved["total"], approved["items"]) == (0, [])


@pytest.mark.parametrize(
    "params",
    [{"status": "paid"}, {"limit": 0}, {"limit": 101}, {"offset": -1}],
)
def test_bad_list_parameters_are_422(client: TestClient, params: dict[str, str | int]) -> None:
    assert client.get("/invoices", params=params).status_code == 422


def test_stats_count_invoices_per_status(client: TestClient) -> None:
    empty = client.get("/invoices/stats").json()
    for _ in range(2):
        client.post("/invoices", files={"file": ("a.pdf", SAMPLE.read_bytes(), "application/pdf")})

    stats = client.get("/invoices/stats").json()

    assert empty["total"] == 0 and set(empty["by_status"].values()) == {0}
    assert stats["total"] == 2
    assert stats["by_status"]["uploaded"] == 2
    assert len(stats["by_status"]) == 7  # every status, zero when empty
