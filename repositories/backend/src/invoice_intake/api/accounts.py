"""Account management, for admins only (D-019)."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException

from invoice_intake.domain import DuplicateUsernameError, InvalidAccountError
from invoice_intake.services.accounts import AccountNotFoundError, LastAdminError

from .dependencies import AccountServiceDep, Admin
from .schemas import AccountCreateIn, AccountOut, AccountUpdateIn, ProblemOut

router = APIRouter(prefix="/accounts", tags=["accounts"])

_ERRORS: dict[int | str, dict[str, Any]] = {
    404: {"description": "Unknown account"},
    409: {"description": "The username is taken, or the change would leave no active admin"},
    422: {"model": ProblemOut, "description": "An invalid username, display name or password"},
}


@router.get("", response_model=list[AccountOut])
def list_accounts(_: Admin, service: AccountServiceDep) -> list[AccountOut]:
    """Every account, by username."""
    return [AccountOut.of(account) for account in service.list_accounts()]


@router.post("", status_code=201, response_model=AccountOut, responses=_ERRORS)
def create_account(_: Admin, body: AccountCreateIn, service: AccountServiceDep) -> AccountOut:
    """Add an account with a starting password; tell the person to keep it private."""
    try:
        account = service.create_account(
            username=body.username,
            display_name=body.display_name,
            role=body.role,
            password=body.password,
        )
    except DuplicateUsernameError as error:
        raise HTTPException(409, str(error)) from error
    except InvalidAccountError as error:
        raise _problem(error) from error
    return AccountOut.of(account)


@router.patch("/{account_id}", response_model=AccountOut, responses=_ERRORS)
def update_account(
    _: Admin, account_id: UUID, body: AccountUpdateIn, service: AccountServiceDep
) -> AccountOut:
    """Change the role, display name or active state, or set a new password. Deactivating an
    account or setting its password signs it out everywhere."""
    try:
        account = service.update_account(
            account_id,
            display_name=body.display_name,
            role=body.role,
            active=body.active,
            password=body.password,
        )
    except AccountNotFoundError as error:
        raise HTTPException(404, str(error)) from error
    except LastAdminError as error:
        raise HTTPException(409, str(error)) from error
    except InvalidAccountError as error:
        raise _problem(error) from error
    return AccountOut.of(account)


def _problem(error: InvalidAccountError) -> HTTPException:
    return HTTPException(
        422, ProblemOut(message="invalid account details", errors=[str(error)]).model_dump()
    )
