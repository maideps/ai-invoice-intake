"""POST /invoices/{id}/extract against a real, migrated PostgreSQL."""

import json
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from invoice_intake.domain import FIELD_NAMES, ExtractionProvider, ExtractionProviderError
from invoice_intake.main import create_app

from .fakes import ScriptedProvider
from .helpers import IsolatedSettings

pytestmark = pytest.mark.postgres

SAMPLES = Path(__file__).resolve().parents[2] / "samples" / "invoices"


def _client(engine: Engine, provider: ExtractionProvider | None = None) -> TestClient:
    settings = IsolatedSettings(
        environment="test", database_url=engine.url.render_as_string(hide_password=False)
    )
    return TestClient(create_app(settings, extraction_provider=provider))


@pytest.fixture
def client(engine: Engine) -> Iterator[TestClient]:
    with _client(engine) as client:  # default settings: the fake provider
        yield client


def _upload(client: TestClient, pdf: Path) -> str:
    response = client.post("/invoices", files={"file": (pdf.name, pdf.read_bytes(), "x/y")})
    assert response.status_code == 201
    return str(response.json()["id"])


def test_extracting_a_sample_returns_its_ground_truth(client: TestClient) -> None:
    pdf = SAMPLES / "invoice-007.pdf"
    truth = json.loads(pdf.with_suffix(".json").read_text(encoding="utf-8"))
    invoice_id = _upload(client, pdf)

    response = client.post(f"/invoices/{invoice_id}/extract")

    assert response.status_code == 200
    body = response.json()
    assert (body["accepted"], body["errors"]) == (True, [])
    invoice = body["invoice"]
    assert invoice["status"] == "needs_review"
    assert invoice["fields"] == truth["fields"]  # decimals and dates serialise like the samples
    assert set(invoice["confidence"]) == set(FIELD_NAMES)
    recorded = invoice["events"][2]
    assert (recorded["action"], recorded["actor_kind"]) == ("extraction_recorded", "ai")
    assert recorded["details"]["fields"] == truth["fields"]

    assert client.get(f"/invoices/{invoice_id}").json() == invoice  # what we saw was stored


def test_extracting_twice_is_a_conflict(client: TestClient) -> None:
    invoice_id = _upload(client, SAMPLES / "invoice-001.pdf")
    client.post(f"/invoices/{invoice_id}/extract")

    response = client.post(f"/invoices/{invoice_id}/extract")

    assert response.status_code == 409
    assert "needs_review" in response.json()["detail"]


def test_unknown_invoice_is_404(client: TestClient) -> None:
    assert client.post(f"/invoices/{uuid4()}/extract").status_code == 404


def test_rejected_output_is_recorded_and_reported(engine: Engine) -> None:
    with _client(engine, ScriptedProvider("not json at all")) as client:
        invoice_id = _upload(client, SAMPLES / "invoice-001.pdf")

        body = client.post(f"/invoices/{invoice_id}/extract").json()

        assert body["accepted"] is False
        assert body["errors"] == ["output must be a JSON object"]
        stored = client.get(f"/invoices/{invoice_id}").json()
    assert stored["status"] == "extracting"
    assert stored["confidence"] is None
    rejected = stored["events"][-1]
    assert rejected["action"] == "extraction_rejected"
    assert rejected["details"]["output"] == "not json at all"


def test_provider_failure_is_502_and_records_nothing(engine: Engine) -> None:
    provider = ScriptedProvider(ExtractionProviderError("OpenAI request failed: timeout"))
    with _client(engine, provider) as client:
        invoice_id = _upload(client, SAMPLES / "invoice-001.pdf")

        response = client.post(f"/invoices/{invoice_id}/extract")

        assert response.status_code == 502
        assert "timeout" in response.json()["detail"]
        stored = client.get(f"/invoices/{invoice_id}").json()
    assert stored["status"] == "uploaded"  # the move to extracting was rolled back
    assert len(stored["events"]) == 1
