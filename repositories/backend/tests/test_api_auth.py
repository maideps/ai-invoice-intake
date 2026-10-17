"""Signing in, the session cookie, roles on every route, and account management, against a real
PostgreSQL (D-019)."""

from collections.abc import Iterator
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select

from invoice_intake.domain import DuplicateUsernameError, Permission, Role
from invoice_intake.infrastructure.accounts import (
    SqlAccountRepository,
    SqlSessionRepository,
    SqlSignInFailureRepository,
)
from invoice_intake.infrastructure.database import make_session_factory
from invoice_intake.infrastructure.tables import SessionRow, SignInFailureRow
from invoice_intake.services.accounts import DEMO_ACCOUNTS, token_hash

from .app_helpers import TEST_PASSWORD, add_account, make_app, sign_in

pytestmark = pytest.mark.postgres

SESSION_COOKIE = "invoice_intake_session"
ANY_ID = "00000000-0000-4000-8000-000000000001"

# Who may call each route. A route missing here fails test_every_route_is_classified, so a new
# endpoint can't be left open by accident.
PUBLIC = {
    ("GET", "/health"),
    ("POST", "/auth/sign-in"),
    ("POST", "/auth/sign-out"),
    ("GET", "/auth/demo-accounts"),
}
SIGNED_IN = {("GET", "/auth/me")}
REQUIRED: dict[tuple[str, str], Permission] = {
    ("GET", "/invoices"): Permission.READ,
    ("GET", "/invoices/stats"): Permission.READ,
    ("GET", "/invoices/{invoice_id}"): Permission.READ,
    ("GET", "/invoices/{invoice_id}/events"): Permission.READ,
    ("GET", "/invoices/{invoice_id}/document"): Permission.READ,
    ("POST", "/invoices"): Permission.UPLOAD,
    ("POST", "/invoices/{invoice_id}/extract"): Permission.REVIEW,
    ("POST", "/invoices/{invoice_id}/export"): Permission.REVIEW,
    ("PATCH", "/invoices/{invoice_id}/fields"): Permission.REVIEW,
    ("POST", "/invoices/{invoice_id}/approve"): Permission.REVIEW,
    ("POST", "/invoices/{invoice_id}/reject"): Permission.REVIEW,
    ("GET", "/accounts"): Permission.MANAGE_ACCOUNTS,
    ("POST", "/accounts"): Permission.MANAGE_ACCOUNTS,
    ("PATCH", "/accounts/{account_id}"): Permission.MANAGE_ACCOUNTS,
}
ROLE_ALLOWS = {
    Role.VIEWER: {Permission.READ},
    Role.REVIEWER: {Permission.READ, Permission.UPLOAD, Permission.REVIEW},
    Role.ADMIN: set(Permission),
}


@pytest.fixture
def client(engine: Engine) -> Iterator[TestClient]:
    with TestClient(make_app(engine)) as client:
        yield client


def _routes(client: TestClient) -> set[tuple[str, str]]:
    """Every route, from the OpenAPI document (it lists each path and method the app serves)."""
    paths: dict[str, dict[str, Any]] = client.get("/openapi.json").json()["paths"]
    return {(method.upper(), path) for path, operations in paths.items() for method in operations}


def _call(client: TestClient, method: str, path: str) -> int:
    url = path.replace("{invoice_id}", ANY_ID).replace("{account_id}", ANY_ID)
    return client.request(method, url).status_code


def test_every_route_is_classified(client: TestClient) -> None:
    assert _routes(client) == PUBLIC | SIGNED_IN | set(REQUIRED)


@pytest.mark.parametrize(("method", "path"), sorted(SIGNED_IN | set(REQUIRED)))
def test_signed_out_requests_get_401(client: TestClient, method: str, path: str) -> None:
    assert _call(client, method, path) == 401


@pytest.mark.parametrize("role", list(Role))
def test_each_role_reaches_exactly_its_routes(
    client: TestClient, engine: Engine, role: Role
) -> None:
    sign_in(client, engine, f"as-{role.value}", role)

    for (method, path), permission in REQUIRED.items():
        status = _call(client, method, path)
        if permission in ROLE_ALLOWS[role]:
            assert status not in (401, 403), f"{role.value}: {method} {path} -> {status}"
        else:
            assert status == 403, f"{role.value}: {method} {path} -> {status}"


def test_signing_in_sets_a_protected_session_cookie(client: TestClient, engine: Engine) -> None:
    add_account(engine, "maide")

    response = client.post("/auth/sign-in", json={"username": "Maide", "password": TEST_PASSWORD})

    assert response.status_code == 200
    body = response.json()
    assert (body["username"], body["role"], body["active"]) == ("maide", "reviewer", True)
    assert body["permissions"] == ["read", "upload", "review"]
    assert "password_hash" not in body
    cookie = response.headers["set-cookie"]
    assert cookie.startswith(f"{SESSION_COOKIE}=")
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    assert "Path=/" in cookie
    assert "Max-Age=43200" in cookie
    assert "Secure" not in cookie  # plain HTTP locally; INVOICE_INTAKE_SESSION_COOKIE_SECURE=true
    token = client.cookies[SESSION_COOKIE]
    with make_session_factory(engine)() as session:
        stored = session.scalars(select(SessionRow.token_hash)).all()
    assert stored == [token_hash(token)]  # only the hash is stored


def test_the_cookie_is_secure_when_configured(engine: Engine) -> None:
    add_account(engine, "maide")
    with TestClient(make_app(engine, session_cookie_secure=True)) as client:
        response = client.post(
            "/auth/sign-in", json={"username": "maide", "password": TEST_PASSWORD}
        )

    assert "Secure" in response.headers["set-cookie"]


def test_wrong_credentials_are_401_without_a_cookie(client: TestClient, engine: Engine) -> None:
    add_account(engine, "maide")

    response = client.post("/auth/sign-in", json={"username": "maide", "password": "nope-nope-1"})

    assert response.status_code == 401
    assert response.json() == {"detail": "wrong username or password"}
    assert "set-cookie" not in response.headers


def test_sign_in_takes_json_only(client: TestClient, engine: Engine) -> None:
    # A cross-site HTML form posts urlencoded data: it can't sign anyone in.
    add_account(engine, "maide")

    response = client.post("/auth/sign-in", data={"username": "maide", "password": TEST_PASSWORD})

    assert response.status_code == 422


def test_me_and_signing_out(client: TestClient, engine: Engine) -> None:
    sign_in(client, engine)
    assert client.get("/auth/me").json()["username"] == "maide"

    response = client.post("/auth/sign-out")

    assert response.status_code == 204
    assert f'{SESSION_COOKIE}=""' in response.headers["set-cookie"]
    assert client.get("/auth/me").status_code == 401


def test_a_stolen_cookie_stops_working_after_sign_out(client: TestClient, engine: Engine) -> None:
    sign_in(client, engine)
    token = client.cookies[SESSION_COOKIE]
    client.post("/auth/sign-out")

    client.cookies.set(SESSION_COOKIE, token)

    assert client.get("/auth/me").status_code == 401


def test_demo_accounts_are_listed_only_when_turned_on(engine: Engine) -> None:
    with TestClient(make_app(engine)) as client:
        assert client.get("/auth/demo-accounts").json() == []
    with TestClient(make_app(engine, demo_accounts=True)) as client:
        listed = client.get("/auth/demo-accounts").json()

    assert [(a["username"], a["role"], a["password"]) for a in listed] == [
        (demo.username, demo.role.value, demo.password) for demo in DEMO_ACCOUNTS
    ]


def test_an_admin_manages_accounts(client: TestClient, engine: Engine) -> None:
    sign_in(client, engine, "boss", Role.ADMIN)

    created = client.post(
        "/accounts",
        json={
            "username": "New.Person",
            "display_name": "New Person",
            "role": "viewer",
            "password": "a starting password",
        },
    )
    assert created.status_code == 201
    new = created.json()
    assert (new["username"], new["role"], new["permissions"]) == ("new.person", "viewer", ["read"])

    changed = client.patch(f"/accounts/{new['id']}", json={"role": "reviewer"})
    assert changed.json()["role"] == "reviewer"
    deactivated = client.patch(f"/accounts/{new['id']}", json={"active": False})
    assert (deactivated.json()["active"], deactivated.json()["permissions"]) == (False, [])

    listed = [a["username"] for a in client.get("/accounts").json()]
    assert listed == ["boss", "new.person"]


@pytest.mark.parametrize(
    ("body", "status"),
    [
        ({"username": "boss", "display_name": "Twin", "role": "viewer", "password": "x" * 12}, 409),
        (
            {"username": "x", "display_name": "Too short", "role": "viewer", "password": "x" * 12},
            422,
        ),
        (
            {"username": "fine", "display_name": "Short pw", "role": "viewer", "password": "short"},
            422,
        ),
        (
            {"username": "fine", "display_name": "No role", "role": "owner", "password": "x" * 12},
            422,
        ),
    ],
)
def test_account_creation_errors(
    client: TestClient, engine: Engine, body: dict[str, str], status: int
) -> None:
    sign_in(client, engine, "boss", Role.ADMIN)

    assert client.post("/accounts", json=body).status_code == status


def test_the_last_admin_cannot_demote_themselves(client: TestClient, engine: Engine) -> None:
    boss = sign_in(client, engine, "boss", Role.ADMIN)

    response = client.patch(f"/accounts/{boss.id}", json={"role": "viewer"})

    assert response.status_code == 409
    assert "at least one active admin" in response.json()["detail"]


def test_a_deactivated_account_is_signed_out_at_once(engine: Engine) -> None:
    with TestClient(make_app(engine)) as admin, TestClient(make_app(engine)) as reviewer:
        sign_in(admin, engine, "boss", Role.ADMIN)
        account = sign_in(reviewer, engine, "maide")
        assert reviewer.get("/invoices").status_code == 200

        admin.patch(f"/accounts/{account.id}", json={"active": False})

        assert reviewer.get("/invoices").status_code == 401


def test_a_role_change_applies_to_the_next_request(engine: Engine) -> None:
    with TestClient(make_app(engine)) as admin, TestClient(make_app(engine)) as reviewer:
        sign_in(admin, engine, "boss", Role.ADMIN)
        account = sign_in(reviewer, engine, "maide")

        admin.patch(f"/accounts/{account.id}", json={"role": "viewer"})

        assert (
            reviewer.post("/invoices/" + ANY_ID + "/approve", json={"version": 1}).status_code
            == 403
        )
        assert reviewer.get("/invoices").status_code == 200


# The SQL repositories


def test_sql_accounts_round_trip_and_stay_unique(engine: Engine) -> None:
    account = add_account(engine, "maide")
    sessions = make_session_factory(engine)

    with sessions.begin() as session:
        repository = SqlAccountRepository(session)
        assert repository.get(account.id) == account
        assert repository.get_by_username("maide") == account
        with pytest.raises(DuplicateUsernameError):
            repository.add(replace(account, id=UUID(int=1), display_name="Twin"))
        # the savepoint kept the transaction usable
        repository.update(account.changed(role=Role.ADMIN, active=False))
        assert repository.count_active_admins() == 0
        repository.update(account.changed(role=Role.ADMIN))
        assert repository.count_active_admins() == 1
        assert [a.username for a in repository.list_all()] == ["maide"]


def test_sql_sessions_expire_and_are_deleted(engine: Engine) -> None:
    account = add_account(engine, "maide")
    now = datetime(2026, 10, 14, 9, tzinfo=timezone.utc)

    with make_session_factory(engine).begin() as session:
        repository = SqlSessionRepository(session)
        repository.add("a" * 64, account.id, created_at=now, expires_at=now + timedelta(hours=1))
        repository.add("b" * 64, account.id, created_at=now, expires_at=now + timedelta(hours=2))
        assert repository.account_for("a" * 64, now=now) == account.id
        assert repository.account_for("a" * 64, now=now + timedelta(hours=1)) is None
        repository.delete_expired(now=now + timedelta(hours=1))
        assert repository.account_for("b" * 64, now=now) == account.id
        repository.delete("b" * 64)
        assert repository.account_for("b" * 64, now=now) is None
        repository.add("c" * 64, account.id, created_at=now, expires_at=now + timedelta(hours=1))
        repository.delete_for_account(account.id)
        assert repository.account_for("c" * 64, now=now) is None


# Rate limiting (D-022)


def test_too_many_failures_are_429_with_retry_after(engine: Engine) -> None:
    add_account(engine, "maide")
    with TestClient(make_app(engine, sign_in_max_failures=2)) as client:
        for _ in range(2):
            wrong = client.post(
                "/auth/sign-in", json={"username": "maide", "password": "nope-nope-1"}
            )
            assert wrong.status_code == 401

        refused = client.post(
            "/auth/sign-in", json={"username": "maide", "password": TEST_PASSWORD}
        )

    assert refused.status_code == 429
    assert refused.json()["detail"].startswith("too many failed sign-ins; try again in about")
    assert 0 < int(refused.headers["retry-after"]) <= 15 * 60
    assert "set-cookie" not in refused.headers
    # The failures were committed although each request was refused; the 429 added none.
    with make_session_factory(engine).begin() as session:
        rows = session.scalars(select(SignInFailureRow)).all()
    assert [(row.username, row.client) for row in rows] == [("maide", "testclient")] * 2


def test_signing_in_clears_earlier_failures(client: TestClient, engine: Engine) -> None:
    add_account(engine, "maide")
    client.post("/auth/sign-in", json={"username": "maide", "password": "nope-nope-1"})

    sign_in(client, engine, "maide")

    with make_session_factory(engine).begin() as session:
        assert session.scalars(select(SignInFailureRow)).all() == []


def test_sql_sign_in_failures_by_username_and_client(engine: Engine) -> None:
    now = datetime(2026, 10, 17, 9, tzinfo=timezone.utc)

    with make_session_factory(engine).begin() as session:
        repository = SqlSignInFailureRepository(session)
        repository.add("maide", "10.0.0.1", at=now + timedelta(minutes=2))
        repository.add("maide", "10.0.0.2", at=now)
        repository.add("other", "10.0.0.1", at=now + timedelta(minutes=1))
        repository.add("other", "x" * 80, at=now)  # longer than the column: truncated

        assert repository.times_for_username("maide", since=now) == [
            now,
            now + timedelta(minutes=2),
        ]
        assert repository.times_for_username("maide", since=now + timedelta(minutes=1)) == [
            now + timedelta(minutes=2)
        ]
        assert repository.times_for_client("10.0.0.1", since=now) == [
            now + timedelta(minutes=1),
            now + timedelta(minutes=2),
        ]
        assert repository.times_for_client("x" * 80, since=now) == [now]

        repository.clear_username("maide")
        assert repository.times_for_username("maide", since=now) == []
        repository.delete_before(now + timedelta(minutes=1))
        assert repository.times_for_username("other", since=now) == [now + timedelta(minutes=1)]
