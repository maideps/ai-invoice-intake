"""People who sign in, what their role lets them do, and where accounts and sessions are stored.

Roles grow: a viewer reads; a reviewer also uploads and decides; an admin also manages
accounts. An inactive account can do nothing.
"""

import re
from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum
from typing import Protocol
from uuid import UUID

from .actors import Actor, ActorKind
from .errors import DomainError

USERNAME = re.compile(r"[a-z0-9][a-z0-9._-]{1,63}")
MAX_DISPLAY_NAME = 100
MIN_PASSWORD = 10
MAX_PASSWORD = 256


class InvalidAccountError(DomainError, ValueError):
    """A username, display name, password or role is not acceptable."""


class Role(str, Enum):
    VIEWER = "viewer"
    REVIEWER = "reviewer"
    ADMIN = "admin"


class Permission(str, Enum):
    READ = "read"  # the queue, invoices, documents and audit trails
    UPLOAD = "upload"
    REVIEW = "review"  # edit fields, approve, reject, retry extraction or export
    MANAGE_ACCOUNTS = "manage_accounts"


PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.VIEWER: frozenset({Permission.READ}),
    Role.REVIEWER: frozenset({Permission.READ, Permission.UPLOAD, Permission.REVIEW}),
    Role.ADMIN: frozenset(Permission),
}


def normalize_username(raw: str) -> str:
    username = raw.strip().lower()
    if not USERNAME.fullmatch(username):
        raise InvalidAccountError(
            "a username has 2 to 64 characters: lower-case letters, digits, '.', '_' or '-', "
            "starting with a letter or digit"
        )
    return username


def clean_display_name(raw: str) -> str:
    name = " ".join(raw.split())
    if not name or len(name) > MAX_DISPLAY_NAME:
        raise InvalidAccountError(f"a display name has 1 to {MAX_DISPLAY_NAME} characters")
    return name


def check_password(password: str) -> str:
    if not MIN_PASSWORD <= len(password) <= MAX_PASSWORD:
        raise InvalidAccountError(f"a password has {MIN_PASSWORD} to {MAX_PASSWORD} characters")
    return password


@dataclass(frozen=True)
class Account:
    id: UUID
    username: str
    display_name: str
    role: Role
    active: bool
    password_hash: str
    created_at: datetime

    def can(self, permission: Permission) -> bool:
        return self.active and permission in PERMISSIONS[self.role]

    @property
    def actor(self) -> Actor:
        """How the account appears in the audit trail: by its username, which never changes."""
        return Actor(ActorKind.USER, self.username)

    def changed(
        self,
        *,
        display_name: str | None = None,
        role: Role | None = None,
        active: bool | None = None,
        password_hash: str | None = None,
    ) -> "Account":
        return replace(
            self,
            display_name=self.display_name if display_name is None else display_name,
            role=self.role if role is None else role,
            active=self.active if active is None else active,
            password_hash=self.password_hash if password_hash is None else password_hash,
        )


class AccountRepository(Protocol):
    def get(self, account_id: UUID) -> Account | None: ...

    def get_by_username(self, username: str) -> Account | None: ...

    def list_all(self) -> list[Account]:
        """Every account, by username."""
        ...

    def add(self, account: Account) -> None:
        """Store a new account; raises ``DuplicateUsernameError`` if the username is taken."""

    def update(self, account: Account) -> None: ...

    def count_active_admins(self) -> int: ...


class DuplicateUsernameError(DomainError):
    """Another account already has this username."""


class SessionRepository(Protocol):
    """Signed-in sessions, stored by the SHA-256 of their token, never the token itself."""

    def add(
        self, token_hash: str, account_id: UUID, *, created_at: datetime, expires_at: datetime
    ) -> None: ...

    def account_for(self, token_hash: str, *, now: datetime) -> UUID | None:
        """The account of an unexpired session, or ``None``."""
        ...

    def delete(self, token_hash: str) -> None: ...

    def delete_for_account(self, account_id: UUID) -> None: ...

    def delete_expired(self, *, now: datetime) -> None: ...


class SignInFailureRepository(Protocol):
    """Failed sign-ins, by username key and client address, for rate limiting (D-022)."""

    def add(self, username: str, client: str, *, at: datetime) -> None: ...

    def times_for_username(self, username: str, *, since: datetime) -> list[datetime]:
        """When this username failed since ``since``, oldest first."""
        ...

    def times_for_client(self, client: str, *, since: datetime) -> list[datetime]:
        """When this client address failed since ``since``, oldest first."""
        ...

    def clear_username(self, username: str) -> None: ...

    def delete_before(self, cutoff: datetime) -> None: ...
