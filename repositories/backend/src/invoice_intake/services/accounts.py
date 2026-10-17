"""Use cases for signing in and managing accounts (D-019).

Passwords are hashed with scrypt from the standard library; sessions are random tokens of
which only the SHA-256 is stored.
"""

import hashlib
import hmac
import math
import secrets
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from invoice_intake.domain import (
    Account,
    AccountRepository,
    InvalidAccountError,
    Role,
    SessionRepository,
    SignInFailureRepository,
    check_password,
    clean_display_name,
    normalize_username,
)

# scrypt cost: 2**14 rounds, 8 blocks, 1 lane: about 16 MB and tens of milliseconds per hash.
SCRYPT_N, SCRYPT_R, SCRYPT_P = 2**14, 8, 1
SALT_BYTES = 16


def hash_password(password: str, *, n: int = SCRYPT_N) -> str:
    """``scrypt$n$r$p$salt$hash`` (hex): the parameters can change without breaking old hashes."""
    salt = secrets.token_bytes(SALT_BYTES)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=n, r=SCRYPT_R, p=SCRYPT_P)
    return f"scrypt${n}${SCRYPT_R}${SCRYPT_P}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt, digest = stored.split("$")
        if scheme != "scrypt":
            return False
        candidate = hashlib.scrypt(
            password.encode(), salt=bytes.fromhex(salt), n=int(n), r=int(r), p=int(p)
        )
    except ValueError:
        return False
    return hmac.compare_digest(candidate.hex(), digest)


# Checked when the username does not exist, so a wrong username costs as long as a wrong password.
_UNKNOWN_USER_HASH = hash_password(secrets.token_hex(16))


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class InvalidCredentialsError(Exception):
    """Wrong username or password, or an inactive account; deliberately not more specific."""


class SignInThrottledError(Exception):
    """Too many failed sign-ins for this username or client address; try again later (D-022)."""

    def __init__(self, retry_after_seconds: int) -> None:
        minutes = max(1, math.ceil(retry_after_seconds / 60))
        unit = "minute" if minutes == 1 else "minutes"
        super().__init__(f"too many failed sign-ins; try again in about {minutes} {unit}")
        self.retry_after_seconds = retry_after_seconds


@dataclass(frozen=True)
class SignInPolicy:
    """How many failures within ``window`` lock a username, or a client address, out."""

    max_per_username: int = 5
    max_per_client: int = 20
    window: timedelta = timedelta(minutes=15)


DEFAULT_SIGN_IN_POLICY = SignInPolicy()


class AccountNotFoundError(LookupError):
    pass


class LastAdminError(Exception):
    """The change would leave no active admin to manage accounts."""


@dataclass(frozen=True)
class DemoAccount:
    username: str
    display_name: str
    role: Role
    password: str


# Public by design: created only by ``accounts demo`` and listed only when demo accounts are on.
DEMO_ACCOUNTS = (
    DemoAccount("sam.rivera", "Sam Rivera", Role.REVIEWER, "demo-reviewer"),
    DemoAccount("alex.chen", "Alex Chen", Role.VIEWER, "demo-viewer"),
    DemoAccount("jordan.lee", "Jordan Lee", Role.ADMIN, "demo-admin"),
)


@dataclass(frozen=True)
class SignedIn:
    account: Account
    token: str
    expires_at: datetime


class AccountService:
    def __init__(
        self,
        accounts: AccountRepository,
        sessions: SessionRepository,
        *,
        clock: Callable[[], datetime],
        session_ttl: timedelta,
        password_cost: int = SCRYPT_N,
        failures: SignInFailureRepository | None = None,
        sign_in_policy: SignInPolicy = DEFAULT_SIGN_IN_POLICY,
    ) -> None:
        """``failures`` turns on rate limiting for sign-in; the app always passes it, while tools
        that only manage accounts (the command line) need not."""
        self._accounts = accounts
        self._sessions = sessions
        self._failures = failures
        self._policy = sign_in_policy
        self._clock = clock
        self._session_ttl = session_ttl
        self._password_cost = password_cost

    # Signing in and out

    def sign_in(self, username: str, password: str, *, client: str = "") -> SignedIn:
        """Start a session, or raise ``InvalidCredentialsError`` (recorded as a failure) or
        ``SignInThrottledError`` (nothing checked, nothing recorded: the lock never extends
        itself). Failures are recorded in the caller's transaction, which must commit them."""
        now = self._clock()
        key = username.strip().lower()[:64]  # unknown usernames count like real ones
        self._refuse_if_throttled(key, client, now)
        try:
            account = self._accounts.get_by_username(normalize_username(username))
        except InvalidAccountError:
            account = None
        if account is None:
            verify_password(password, _UNKNOWN_USER_HASH)
            self._record_failure(key, client, now)
            raise InvalidCredentialsError("wrong username or password")
        if not verify_password(password, account.password_hash) or not account.active:
            self._record_failure(key, client, now)
            raise InvalidCredentialsError("wrong username or password")
        if self._failures is not None:
            self._failures.clear_username(key)
        token = secrets.token_urlsafe(32)
        self._sessions.delete_expired(now=now)  # housekeeping: expired sessions go here
        expires_at = now + self._session_ttl
        self._sessions.add(token_hash(token), account.id, created_at=now, expires_at=expires_at)
        return SignedIn(account, token, expires_at)

    def _refuse_if_throttled(self, key: str, client: str, now: datetime) -> None:
        if self._failures is None:
            return
        window = self._policy.window
        self._failures.delete_before(now - window)  # housekeeping, like expired sessions
        waits = [timedelta(0)]
        for times, limit in (
            (
                self._failures.times_for_username(key, since=now - window),
                self._policy.max_per_username,
            ),
            (
                self._failures.times_for_client(client, since=now - window) if client else [],
                self._policy.max_per_client,
            ),
        ):
            if len(times) >= limit:
                # Locked until the oldest of the last ``limit`` failures leaves the window.
                waits.append(times[-limit] + window - now)
        if max(waits) > timedelta(0):
            raise SignInThrottledError(max(1, math.ceil(max(waits).total_seconds())))

    def _record_failure(self, key: str, client: str, now: datetime) -> None:
        if self._failures is not None:
            self._failures.add(key, client, at=now)

    def account_for_session(self, token: str) -> Account | None:
        """The active account behind an unexpired session token, or ``None``."""
        if not token:
            return None
        account_id = self._sessions.account_for(token_hash(token), now=self._clock())
        account = self._accounts.get(account_id) if account_id else None
        return account if account is not None and account.active else None

    def sign_out(self, token: str) -> None:
        if token:
            self._sessions.delete(token_hash(token))

    # Managing accounts (the API allows these to admins only)

    def list_accounts(self) -> list[Account]:
        return self._accounts.list_all()

    def create_account(
        self, *, username: str, display_name: str, role: Role, password: str
    ) -> Account:
        account = Account(
            id=uuid4(),
            username=normalize_username(username),
            display_name=clean_display_name(display_name),
            role=role,
            active=True,
            password_hash=self._hash(password),
            created_at=self._clock(),
        )
        self._accounts.add(account)  # raises DuplicateUsernameError
        return account

    def update_account(
        self,
        account_id: UUID,
        *,
        display_name: str | None = None,
        role: Role | None = None,
        active: bool | None = None,
        password: str | None = None,
    ) -> Account:
        account = self._accounts.get(account_id)
        if account is None:
            raise AccountNotFoundError(f"account {account_id} not found")
        updated = account.changed(
            display_name=None if display_name is None else clean_display_name(display_name),
            role=role,
            active=active,
            password_hash=None if password is None else self._hash(password),
        )
        was_admin = account.active and account.role is Role.ADMIN
        still_admin = updated.active and updated.role is Role.ADMIN
        if was_admin and not still_admin and self._accounts.count_active_admins() <= 1:
            raise LastAdminError("keep at least one active admin, or no one can manage accounts")
        self._accounts.update(updated)
        if not updated.active or password is not None:
            self._sessions.delete_for_account(account_id)  # sign them out everywhere
        return updated

    def ensure_demo_accounts(self) -> list[Account]:
        """Create the demo accounts that do not exist yet; existing accounts stay as they are."""
        created = []
        for demo in DEMO_ACCOUNTS:
            if self._accounts.get_by_username(demo.username) is None:
                created.append(
                    self.create_account(
                        username=demo.username,
                        display_name=demo.display_name,
                        role=demo.role,
                        password=demo.password,
                    )
                )
        return created

    def _hash(self, password: str) -> str:
        return hash_password(check_password(password), n=self._password_cost)


AccountServiceFactory = Callable[[], AbstractContextManager[AccountService]]
