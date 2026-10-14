"""Review endpoints against a real, migrated PostgreSQL."""

from collections.abc import Iterator
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from .app_helpers import extract_now, make_app

pytestmark = pytest.mark.postgres

SAMPLES = Path(__file__).resolve().parents[3] / "samples" / "invoices"
ALICE = {"X-User": "alice@example.com"}
BOB = {"X-User": "bob@example.com"}


@pytest.fixture
def client(engine: Engine) -> Iterator[TestClient]:
    with TestClient(make_app(engine)) as client:
        yield client


@pytest.fixture
def in_review(client: TestClient, engine: Engine) -> dict[str, Any]:
    """A sample uploaded and extracted (fake provider, as the worker would): ready for review."""
    pdf = SAMPLES / "invoice-005.pdf"
    created = client.post("/invoices", files={"file": (pdf.name, pdf.read_bytes(), "x/y")})
    invoice_id = created.json()["id"]
    extract_now(engine, UUID(invoice_id))
    body: dict[str, Any] = client.get(f"/invoices/{invoice_id}").json()
    assert body["status"] == "needs_review"
    return body


def test_correct_then_approve_leaves_a_complete_audit_trail(
    client: TestClient, in_review: dict[str, Any]
) -> None:
    invoice = in_review
    old_total = invoice["fields"]["total"]

    edited = client.patch(
        f"/invoices/{invoice['id']}/fields",
        json={"version": invoice["version"], "fields": {"total": "999.99"}},
        headers=ALICE,
    )
    assert edited.status_code == 200
    assert edited.json()["fields"]["total"] == "999.99"

    approved = client.post(
        f"/invoices/{invoice['id']}/approve",
        json={"version": edited.json()["version"]},
        headers=BOB,
    )
    assert approved.status_code == 200

    stored = client.get(f"/invoices/{invoice['id']}").json()
    assert stored == approved.json()
    assert stored["status"] == "approved"
    trail = [(e["action"], e["to_status"], e["actor_name"]) for e in stored["events"]]
    assert trail[-2:] == [
        ("fields_edited", None, "alice@example.com"),
        ("status_changed", "approved", "bob@example.com"),
    ]
    assert stored["events"][-2]["details"] == {
        "changes": {"total": {"from": old_total, "to": "999.99"}}
    }


def test_reject_with_a_reason(client: TestClient, in_review: dict[str, Any]) -> None:
    invoice = in_review

    response = client.post(
        f"/invoices/{invoice['id']}/reject",
        json={"version": invoice["version"], "reason": "Duplicate of INV-4410"},
        headers=ALICE,
    )

    assert response.status_code == 200
    last = response.json()["events"][-1]
    assert (last["to_status"], last["reason"], last["actor_name"]) == (
        "rejected",
        "Duplicate of INV-4410",
        "alice@example.com",
    )


def test_stale_version_is_a_conflict_and_changes_nothing(
    client: TestClient, in_review: dict[str, Any]
) -> None:
    invoice = in_review
    path = f"/invoices/{invoice['id']}"
    client.patch(f"{path}/fields", json={"version": invoice["version"], "fields": {"tax": "1.00"}})

    response = client.post(f"{path}/approve", json={"version": invoice["version"]})

    assert response.status_code == 409
    assert "reload it and retry" in response.json()["detail"]
    assert client.get(path).json()["status"] == "needs_review"


def test_decisions_on_a_finished_invoice_are_conflicts(
    client: TestClient, in_review: dict[str, Any]
) -> None:
    invoice = in_review
    path = f"/invoices/{invoice['id']}"
    rejected = client.post(
        f"{path}/reject", json={"version": invoice["version"], "reason": "wrong"}
    ).json()

    for action, body in (
        ("approve", {"version": rejected["version"]}),
        ("fields", {"version": rejected["version"], "fields": {"total": "1.00"}}),
    ):
        method = client.patch if action == "fields" else client.post
        response = method(f"{path}/{action}", json=body)
        assert response.status_code == 409
        assert "rejected" in response.json()["detail"]


def test_invalid_edits_are_422_with_the_reasons(
    client: TestClient, in_review: dict[str, Any]
) -> None:
    invoice = in_review

    response = client.patch(
        f"/invoices/{invoice['id']}/fields",
        json={"version": invoice["version"], "fields": {"total": "1.234,50", "nope": 1}},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == {
        "message": "invalid field values",
        "errors": ["fields has unknown keys nope"],
    }


def test_approval_needs_the_key_fields(client: TestClient, in_review: dict[str, Any]) -> None:
    invoice = in_review
    path = f"/invoices/{invoice['id']}"
    cleared = client.patch(
        f"{path}/fields",
        json={"version": invoice["version"], "fields": {"total": None, "currency": None}},
    ).json()

    response = client.post(f"{path}/approve", json={"version": cleared["version"]})

    assert response.status_code == 422
    assert response.json()["detail"] == {
        "message": "cannot approve until these fields are filled",
        "errors": ["currency", "total"],
    }


def test_rejection_needs_a_reason(client: TestClient, in_review: dict[str, Any]) -> None:
    invoice = in_review

    response = client.post(
        f"/invoices/{invoice['id']}/reject", json={"version": invoice["version"], "reason": " "}
    )

    assert response.status_code == 422
    assert response.json()["detail"]["errors"] == ["a rejection needs a reason"]


@pytest.mark.parametrize(
    ("method", "action", "body"),
    [
        ("patch", "fields", {"version": 1, "fields": {"total": "1.00"}}),
        ("post", "approve", {"version": 1}),
        ("post", "reject", {"version": 1, "reason": "x"}),
    ],
)
def test_unknown_invoice_is_404(
    client: TestClient, method: str, action: str, body: dict[str, Any]
) -> None:
    response = getattr(client, method)(f"/invoices/{uuid4()}/{action}", json=body)

    assert response.status_code == 404


@pytest.mark.parametrize(
    "body", [{}, {"version": 0}, {"version": "three"}], ids=["missing", "zero", "text"]
)
def test_version_is_required(
    client: TestClient, body: dict[str, Any], in_review: dict[str, Any]
) -> None:
    invoice = in_review

    assert client.post(f"/invoices/{invoice['id']}/approve", json=body).status_code == 422
