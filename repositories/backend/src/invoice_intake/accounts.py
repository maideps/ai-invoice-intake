"""Manage accounts from the command line (D-019). A composition root, like ``main.py``.

    python -m invoice_intake.accounts create USERNAME --name "Display Name" --role admin
    python -m invoice_intake.accounts set-password USERNAME
    python -m invoice_intake.accounts list
    python -m invoice_intake.accounts demo

From the repository root, ``npm run accounts -- <command>``; in the Docker stack,
``docker compose exec api python -m invoice_intake.accounts <command>``. Passwords are read
from a prompt (or from standard input with ``--password-stdin``), never from an argument, so
they stay out of shell history and process lists.
"""

import argparse
import getpass
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from invoice_intake.config import get_settings
from invoice_intake.domain import DomainError, Role
from invoice_intake.infrastructure.accounts import SqlAccountRepository, SqlSessionRepository
from invoice_intake.infrastructure.database import make_engine, make_session_factory
from invoice_intake.services.accounts import DEMO_ACCOUNTS, AccountService


@contextmanager
def account_service() -> Iterator[AccountService]:
    settings = get_settings()
    engine = make_engine(settings.database_url)
    try:
        with make_session_factory(engine).begin() as session:
            yield AccountService(
                SqlAccountRepository(session),
                SqlSessionRepository(session),
                clock=lambda: datetime.now(timezone.utc),
                session_ttl=timedelta(hours=settings.session_ttl_hours),
            )
    finally:
        engine.dispose()


def read_password(from_stdin: bool) -> str:
    if from_stdin:
        return sys.stdin.readline().rstrip("\r\n")
    first = getpass.getpass("Password: ")
    if getpass.getpass("Repeat it: ") != first:
        raise SystemExit("The passwords differ; nothing was changed.")
    return first


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="accounts", description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create", help="add an account")
    create.add_argument("username")
    create.add_argument("--name", required=True, help="display name")
    create.add_argument("--role", choices=[role.value for role in Role], required=True)
    create.add_argument("--password-stdin", action="store_true")
    reset = commands.add_parser("set-password", help="set an account's password")
    reset.add_argument("username")
    reset.add_argument("--password-stdin", action="store_true")
    commands.add_parser("list", help="list the accounts")
    commands.add_parser("demo", help="create the demo accounts that are missing")
    args = parser.parse_args(argv)

    try:
        with account_service() as service:
            if args.command == "create":
                account = service.create_account(
                    username=args.username,
                    display_name=args.name,
                    role=Role(args.role),
                    password=read_password(args.password_stdin),
                )
                print(f"Created {account.username} ({account.role.value}).")
            elif args.command == "set-password":
                found = next(
                    (a for a in service.list_accounts() if a.username == args.username.lower()),
                    None,
                )
                if found is None:
                    print(f"No account named {args.username!r}.", file=sys.stderr)
                    return 1
                service.update_account(found.id, password=read_password(args.password_stdin))
                print(f"Set a new password for {found.username}; their sessions have ended.")
            elif args.command == "list":
                for account in service.list_accounts():
                    state = "" if account.active else " (inactive)"
                    print(
                        f"{account.username:<24} {account.role.value:<9} "
                        f"{account.display_name}{state}"
                    )
            else:
                created = service.ensure_demo_accounts()
                names = {account.username for account in created}
                for demo in DEMO_ACCOUNTS:
                    note = "created" if demo.username in names else "exists"
                    print(f"{demo.username:<12} {demo.role.value:<9} {demo.password:<14} {note}")
    except DomainError as error:  # an invalid username or password, or a taken username
        print(f"Not done: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
