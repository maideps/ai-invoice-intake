"""Signing in and out (D-019).

A successful sign-in sets an HttpOnly, SameSite=Lax session cookie: scripts in the page can't
read it, and browsers don't send it with requests from other sites, so another site can't act
for a signed-in reviewer. Sign-in accepts JSON only, so a forged form can't sign someone in
either.

Failed sign-ins are counted per username and per client address; too many answer 429 with
``Retry-After`` (D-022).
"""

from typing import Annotated

from fastapi import APIRouter, Cookie, HTTPException, Request, Response

from invoice_intake.services.accounts import (
    DEMO_ACCOUNTS,
    AccountServiceFactory,
    InvalidCredentialsError,
    SignInThrottledError,
)
from invoice_intake.services.accounts import (
    SignedIn as SignedInSession,
)

from .dependencies import SESSION_COOKIE, AccountServiceDep, SignedIn
from .schemas import AccountOut, DemoAccountOut, SignInIn

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/sign-in",
    response_model=AccountOut,
    responses={
        401: {"description": "Wrong username or password, or an inactive account"},
        429: {"description": "Too many failed sign-ins; retry after ``Retry-After`` seconds"},
    },
)
def sign_in(body: SignInIn, request: Request, response: Response) -> AccountOut:
    """Start a session: the response sets the session cookie."""
    # Not the usual service dependency: that rolls back when the route raises, and a failed
    # sign-in must be committed to count. The outcome is caught inside the transaction instead.
    factory: AccountServiceFactory = request.app.state.account_service
    outcome: SignedInSession | Exception
    with factory() as service:
        try:
            outcome = service.sign_in(body.username, body.password, client=client_address(request))
        except (InvalidCredentialsError, SignInThrottledError) as error:
            outcome = error
    if isinstance(outcome, SignInThrottledError):
        raise HTTPException(
            429, str(outcome), headers={"Retry-After": str(outcome.retry_after_seconds)}
        )
    if isinstance(outcome, Exception):
        raise HTTPException(401, "wrong username or password")
    signed_in = outcome
    settings = request.app.state.settings
    response.set_cookie(
        SESSION_COOKIE,
        signed_in.token,
        max_age=int(settings.session_ttl_hours * 3600),
        httponly=True,
        samesite="lax",
        secure=settings.session_cookie_secure,
        path="/",
    )
    return AccountOut.of(signed_in.account)


def client_address(request: Request) -> str:
    """The client's address. Behind nginx it comes from ``X-Forwarded-For``, which nginx sets
    and uvicorn trusts only from the addresses in ``FORWARDED_ALLOW_IPS`` (D-022)."""
    return request.client.host if request.client else ""


@router.post("/sign-out", status_code=204, response_class=Response)
def sign_out(
    service: AccountServiceDep,
    session: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> Response:
    """End the session (if any) and clear the cookie."""
    service.sign_out(session or "")
    response = Response(status_code=204)
    response.delete_cookie(SESSION_COOKIE, path="/", httponly=True, samesite="lax")
    return response


@router.get("/me", response_model=AccountOut, responses={401: {"description": "Not signed in"}})
def me(account: SignedIn) -> AccountOut:
    """Who is signed in, with what their role allows."""
    return AccountOut.of(account)


@router.get("/demo-accounts", response_model=list[DemoAccountOut])
def demo_accounts(request: Request) -> list[DemoAccountOut]:
    """The demo accounts and their passwords when demo accounts are on (the Docker demo);
    otherwise an empty list."""
    if not request.app.state.settings.demo_accounts:
        return []
    return [
        DemoAccountOut(
            username=demo.username,
            display_name=demo.display_name,
            role=demo.role,
            password=demo.password,
        )
        for demo in DEMO_ACCOUNTS
    ]
