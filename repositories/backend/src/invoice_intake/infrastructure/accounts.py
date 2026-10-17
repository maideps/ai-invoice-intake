"""``AccountRepository``, ``SessionRepository`` and ``SignInFailureRepository`` on PostgreSQL."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import ColumnElement, delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from invoice_intake.domain import Account, DuplicateUsernameError, Role

from .tables import AccountRow, SessionRow, SignInFailureRow


class SqlAccountRepository:
    """Works inside the caller's session and transaction; it flushes but never commits."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, account_id: UUID) -> Account | None:
        row = self._session.get(AccountRow, account_id)
        return _to_domain(row) if row else None

    def get_by_username(self, username: str) -> Account | None:
        row = self._session.scalars(
            select(AccountRow).where(AccountRow.username == username)
        ).one_or_none()
        return _to_domain(row) if row else None

    def list_all(self) -> list[Account]:
        rows = self._session.scalars(select(AccountRow).order_by(AccountRow.username))
        return [_to_domain(row) for row in rows]

    def add(self, account: Account) -> None:
        row = AccountRow(
            id=account.id,
            username=account.username,
            display_name=account.display_name,
            role=account.role.value,
            active=account.active,
            password_hash=account.password_hash,
            created_at=account.created_at,
        )
        try:
            # Added inside a savepoint (begin_nested flushes pending rows first, so the row must
            # not exist yet): a taken username rolls back only the savepoint.
            with self._session.begin_nested():
                self._session.add(row)
        except IntegrityError as error:
            raise DuplicateUsernameError(f"the username {account.username!r} is taken") from error

    def update(self, account: Account) -> None:
        row = self._session.get(AccountRow, account.id, with_for_update=True)
        if row is None:
            raise LookupError(f"account {account.id} not found")
        row.display_name = account.display_name
        row.role = account.role.value
        row.active = account.active
        row.password_hash = account.password_hash
        self._session.flush()

    def count_active_admins(self) -> int:
        return (
            self._session.scalar(
                select(func.count())
                .select_from(AccountRow)
                .where(AccountRow.role == Role.ADMIN.value, AccountRow.active.is_(True))
            )
            or 0
        )


class SqlSessionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(
        self, token_hash: str, account_id: UUID, *, created_at: datetime, expires_at: datetime
    ) -> None:
        self._session.add(
            SessionRow(
                token_hash=token_hash,
                account_id=account_id,
                created_at=created_at,
                expires_at=expires_at,
            )
        )
        self._session.flush()

    def account_for(self, token_hash: str, *, now: datetime) -> UUID | None:
        return self._session.scalar(
            select(SessionRow.account_id).where(
                SessionRow.token_hash == token_hash, SessionRow.expires_at > now
            )
        )

    def delete(self, token_hash: str) -> None:
        self._session.execute(delete(SessionRow).where(SessionRow.token_hash == token_hash))

    def delete_for_account(self, account_id: UUID) -> None:
        self._session.execute(delete(SessionRow).where(SessionRow.account_id == account_id))

    def delete_expired(self, *, now: datetime) -> None:
        self._session.execute(delete(SessionRow).where(SessionRow.expires_at <= now))


class SqlSignInFailureRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, username: str, client: str, *, at: datetime) -> None:
        self._session.add(SignInFailureRow(username=username, client=client[:64], failed_at=at))
        self._session.flush()

    def times_for_username(self, username: str, *, since: datetime) -> list[datetime]:
        return self._times(SignInFailureRow.username == username, since)

    def times_for_client(self, client: str, *, since: datetime) -> list[datetime]:
        return self._times(SignInFailureRow.client == client[:64], since)

    def clear_username(self, username: str) -> None:
        self._session.execute(delete(SignInFailureRow).where(SignInFailureRow.username == username))

    def delete_before(self, cutoff: datetime) -> None:
        self._session.execute(delete(SignInFailureRow).where(SignInFailureRow.failed_at < cutoff))

    def _times(self, match: ColumnElement[bool], since: datetime) -> list[datetime]:
        return list(
            self._session.scalars(
                select(SignInFailureRow.failed_at)
                .where(match, SignInFailureRow.failed_at >= since)
                .order_by(SignInFailureRow.failed_at)
            )
        )


def _to_domain(row: AccountRow) -> Account:
    return Account(
        id=row.id,
        username=row.username,
        display_name=row.display_name,
        role=Role(row.role),
        active=row.active,
        password_hash=row.password_hash,
        created_at=row.created_at,
    )
