"""``python -m invoice_intake.accounts`` against a real PostgreSQL (D-019)."""

import io
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from invoice_intake import accounts
from invoice_intake.config import get_settings
from invoice_intake.services.accounts import DEMO_ACCOUNTS

from .app_helpers import database_url, make_app

pytestmark = pytest.mark.postgres


@pytest.fixture(autouse=True)
def settings_for(engine: Engine, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("INVOICE_INTAKE_DATABASE_URL", database_url(engine))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def run(monkeypatch: pytest.MonkeyPatch, *argv: str, stdin: str = "") -> int:
    monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
    return accounts.main(list(argv))


def can_sign_in(engine: Engine, username: str, password: str) -> bool:
    with TestClient(make_app(engine)) as client:
        response = client.post("/auth/sign-in", json={"username": username, "password": password})
    return bool(response.status_code == 200)


def test_demo_creates_the_missing_demo_accounts(
    engine: Engine, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run(monkeypatch, "demo") == 0
    assert run(monkeypatch, "demo") == 0

    out = capsys.readouterr().out.splitlines()
    assert [line.split()[-1] for line in out] == ["created"] * 3 + ["exists"] * 3
    assert all(can_sign_in(engine, demo.username, demo.password) for demo in DEMO_ACCOUNTS)


def test_create_list_and_set_a_password(
    engine: Engine, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    created = run(
        monkeypatch,
        "create",
        "Kim.Lee",
        "--name",
        "Kim Lee",
        "--role",
        "admin",
        "--password-stdin",
        stdin="first password\n",
    )
    assert created == 0
    assert run(monkeypatch, "list") == 0
    assert (
        run(monkeypatch, "set-password", "kim.lee", "--password-stdin", stdin="second password\n")
        == 0
    )

    out = capsys.readouterr().out
    assert "Created kim.lee (admin)." in out
    assert "kim.lee" in out and "Kim Lee" in out
    assert not can_sign_in(engine, "kim.lee", "first password")
    assert can_sign_in(engine, "kim.lee", "second password")


def test_mistakes_are_reported_and_change_nothing(
    engine: Engine, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    short = run(
        monkeypatch,
        "create",
        "kim",
        "--name",
        "Kim",
        "--role",
        "viewer",
        "--password-stdin",
        stdin="short\n",
    )
    unknown = run(monkeypatch, "set-password", "nobody", "--password-stdin", stdin="x" * 12)

    assert (short, unknown) == (1, 1)
    err = capsys.readouterr().err
    assert "Not done: a password has 10 to 256 characters" in err
    assert "No account named 'nobody'." in err
    assert not can_sign_in(engine, "kim", "short")
