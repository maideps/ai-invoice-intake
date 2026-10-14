"""Accounts, roles and sessions, without a database (D-019)."""

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from invoice_intake.domain import (
    Account,
    ActorKind,
    DuplicateUsernameError,
    InvalidAccountError,
    Permission,
    Role,
    check_password,
    clean_display_name,
    normalize_username,
)
from invoice_intake.services.accounts import (
    DEMO_ACCOUNTS,
    AccountNotFoundError,
    AccountService,
    InvalidCredentialsError,
    LastAdminError,
    hash_password,
    token_hash,
    verify_password,
)

from .app_helpers import FAST_PASSWORD_COST
from .fakes import InMemoryAccountRepository, InMemorySessionRepository

START = datetime(2026, 10, 14, 9, 0, tzinfo=timezone.utc)
PASSWORD = "correct horse battery"


class Clock:
    def __init__(self) -> None:
        self.now = START

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def sessions() -> InMemorySessionRepository:
    return InMemorySessionRepository()


@pytest.fixture
def service(clock: Clock, sessions: InMemorySessionRepository) -> AccountService:
    return AccountService(
        InMemoryAccountRepository(),
        sessions,
        clock=clock,
        session_ttl=timedelta(hours=12),
        password_cost=FAST_PASSWORD_COST,
    )


def add(service: AccountService, username: str = "maide", role: Role = Role.REVIEWER) -> Account:
    return service.create_account(
        username=username, display_name=username.title(), role=role, password=PASSWORD
    )


# Roles and validation


@pytest.mark.parametrize(
    ("role", "allowed"),
    [
        (Role.VIEWER, {Permission.READ}),
        (Role.REVIEWER, {Permission.READ, Permission.UPLOAD, Permission.REVIEW}),
        (Role.ADMIN, set(Permission)),
    ],
)
def test_each_role_has_its_permissions(role: Role, allowed: set[Permission]) -> None:
    account = Account(uuid4(), "x1", "X", role, True, "", START)

    assert {permission for permission in Permission if account.can(permission)} == allowed


def test_an_inactive_account_can_do_nothing() -> None:
    account = Account(uuid4(), "boss", "Boss", Role.ADMIN, False, "", START)

    assert not any(account.can(permission) for permission in Permission)


def test_the_audit_trail_records_the_username() -> None:
    account = Account(uuid4(), "sam.rivera", "Sam Rivera", Role.REVIEWER, True, "", START)

    assert (account.actor.kind, account.actor.name) == (ActorKind.USER, "sam.rivera")


@pytest.mark.parametrize(
    ("raw", "username"), [("  Sam.Rivera ", "sam.rivera"), ("a1", "a1"), ("x_y-z", "x_y-z")]
)
def test_usernames_are_trimmed_and_lower_case(raw: str, username: str) -> None:
    assert normalize_username(raw) == username


@pytest.mark.parametrize("raw", ["", "a", "-start", "has space", "é", "x" * 65, "a@b.com"])
def test_unusable_usernames_are_refused(raw: str) -> None:
    with pytest.raises(InvalidAccountError, match="username"):
        normalize_username(raw)


def test_display_names_and_passwords_have_limits() -> None:
    assert clean_display_name("  Sam   Rivera ") == "Sam Rivera"
    with pytest.raises(InvalidAccountError):
        clean_display_name("   ")
    with pytest.raises(InvalidAccountError):
        clean_display_name("x" * 101)
    assert check_password("x" * 10) == "x" * 10
    with pytest.raises(InvalidAccountError, match="10 to 256"):
        check_password("short")
    with pytest.raises(InvalidAccountError):
        check_password("x" * 257)


# Passwords


def test_passwords_are_salted_scrypt_hashes() -> None:
    first, second = hash_password(PASSWORD, n=FAST_PASSWORD_COST), hash_password(PASSWORD)

    assert first.startswith(f"scrypt${FAST_PASSWORD_COST}$8$1$")
    assert second.startswith("scrypt$16384$8$1$")
    assert PASSWORD not in first
    assert hash_password(PASSWORD, n=FAST_PASSWORD_COST) != first  # a new salt every time
    assert verify_password(PASSWORD, first) and verify_password(PASSWORD, second)
    assert not verify_password("wrong password", first)


@pytest.mark.parametrize("stored", ["", "bcrypt$1$2$3$aa$bb", "scrypt$x$8$1$aa$bb", "scrypt$1"])
def test_unreadable_hashes_never_match(stored: str) -> None:
    assert not verify_password(PASSWORD, stored)


# Signing in, sessions


def test_signing_in_starts_a_session_stored_by_its_hash(
    service: AccountService, sessions: InMemorySessionRepository
) -> None:
    account = add(service)

    signed_in = service.sign_in("  MAIDE ", PASSWORD)

    assert signed_in.account == account
    assert signed_in.expires_at == START + timedelta(hours=12)
    assert list(sessions.sessions) == [token_hash(signed_in.token)]  # never the token itself
    assert service.account_for_session(signed_in.token) == account


@pytest.mark.parametrize(
    ("username", "password"),
    [("maide", "wrong password!"), ("nobody", PASSWORD), ("not a username", PASSWORD)],
)
def test_wrong_credentials_get_one_vague_answer(
    service: AccountService, username: str, password: str
) -> None:
    add(service)

    with pytest.raises(InvalidCredentialsError, match="wrong username or password"):
        service.sign_in(username, password)


def test_an_inactive_account_cannot_sign_in(service: AccountService) -> None:
    account = add(service)
    add(service, "boss", Role.ADMIN)
    service.update_account(account.id, active=False)

    with pytest.raises(InvalidCredentialsError):
        service.sign_in("maide", PASSWORD)


def test_sessions_expire_and_are_cleaned_up(
    service: AccountService, clock: Clock, sessions: InMemorySessionRepository
) -> None:
    add(service)
    token = service.sign_in("maide", PASSWORD).token

    clock.now = START + timedelta(hours=12)

    assert service.account_for_session(token) is None
    service.sign_in("maide", PASSWORD)  # signing in clears expired sessions
    assert token_hash(token) not in sessions.sessions


def test_signing_out_ends_only_that_session(service: AccountService) -> None:
    add(service)
    laptop, phone = service.sign_in("maide", PASSWORD), service.sign_in("maide", PASSWORD)

    service.sign_out(laptop.token)

    assert service.account_for_session(laptop.token) is None
    assert service.account_for_session(phone.token) is not None


@pytest.mark.parametrize("token", ["", "made-up"])
def test_unknown_tokens_have_no_account(service: AccountService, token: str) -> None:
    assert service.account_for_session(token) is None


# Managing accounts


def test_usernames_are_unique(service: AccountService) -> None:
    add(service)

    with pytest.raises(DuplicateUsernameError):
        add(service, "MAIDE")


def test_deactivating_or_a_new_password_ends_every_session(service: AccountService) -> None:
    alice, bob = add(service, "alice"), add(service, "bob")
    add(service, "boss", Role.ADMIN)
    alice_token = service.sign_in("alice", PASSWORD).token
    bob_token = service.sign_in("bob", PASSWORD).token

    service.update_account(alice.id, active=False)
    service.update_account(bob.id, password="a brand new password")

    assert service.account_for_session(alice_token) is None
    assert service.account_for_session(bob_token) is None
    assert service.sign_in("bob", "a brand new password").account.id == bob.id


def test_a_role_change_keeps_the_session_and_takes_effect_at_once(service: AccountService) -> None:
    account = add(service)
    token = service.sign_in("maide", PASSWORD).token

    service.update_account(account.id, role=Role.VIEWER, display_name="  Maide  P. ")

    current = service.account_for_session(token)
    assert current is not None
    assert (current.role, current.display_name) == (Role.VIEWER, "Maide P.")
    assert not current.can(Permission.REVIEW)


@pytest.mark.parametrize(
    "change",
    [
        lambda s, a: s.update_account(a, role=Role.REVIEWER),
        lambda s, a: s.update_account(a, active=False),
    ],
)
def test_the_last_active_admin_stays_an_admin(
    service: AccountService, change: Callable[[AccountService, object], object]
) -> None:
    boss = add(service, "boss", Role.ADMIN)

    with pytest.raises(LastAdminError):
        change(service, boss.id)

    add(service, "second", Role.ADMIN)
    change(service, boss.id)  # fine once another admin exists


def test_updating_an_unknown_account(service: AccountService) -> None:
    with pytest.raises(AccountNotFoundError):
        service.update_account(uuid4(), role=Role.VIEWER)


def test_demo_accounts_are_created_once_and_never_changed(service: AccountService) -> None:
    created = service.ensure_demo_accounts()
    reviewer = next(a for a in created if a.role is Role.REVIEWER)
    service.update_account(reviewer.id, password="changed by its owner")

    again = service.ensure_demo_accounts()

    assert [a.username for a in created] == [demo.username for demo in DEMO_ACCOUNTS]
    assert {a.role for a in created} == set(Role)
    assert again == []
    assert service.sign_in(reviewer.username, "changed by its owner")
