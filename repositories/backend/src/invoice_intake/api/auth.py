"""Signing in and out (D-019).

A successful sign-in sets an HttpOnly, SameSite=Lax session cookie: scripts in the page can't
read it, and browsers don't send it with requests from other sites, so another site can't act
for a signed-in reviewer. Sign-in accepts JSON only, so a forged form can't sign someone in
either.
"""

from typing import Annotated

from fastapi import APIRouter, Cookie, HTTPException, Request, Response

from invoice_intake.services.accounts import DEMO_ACCOUNTS, InvalidCredentialsError

from .dependencies import SESSION_COOKIE, AccountServiceDep, SignedIn
from .schemas import AccountOut, DemoAccountOut, SignInIn

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/sign-in",
    response_model=AccountOut,
    responses={401: {"description": "Wrong username or password, or an inactive account"}},
)
def sign_in(
    body: SignInIn, request: Request, response: Response, service: AccountServiceDep
) -> AccountOut:
    """Start a session: the response sets the session cookie."""
    try:
        signed_in = service.sign_in(body.username, body.password)
    except InvalidCredentialsError as error:
        raise HTTPException(401, "wrong username or password") from error
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
