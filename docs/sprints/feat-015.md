# Sprint Contract

**Feature ID:** feat-015
**Feature Name:** Sign-in and roles
**Date:** 2026-10-14
**Estimated Duration:** 1–2 sessions

## What I Will Build

Until now the API trusted an `X-User` header, so anyone could act as anyone, and the audit trail's "who approved it" proved nothing. People now sign in, the API knows who they are from a session, and three roles decide what each person may do. The author chose the roles and the demo experience.

- **Roles** (domain, `domain/accounts.py`):
  - **viewer** reads: the queue, invoices, documents and audit trails.
  - **reviewer** also uploads, edits fields, approves, rejects, and retries extraction or export.
  - **admin** also manages accounts.
  
  An inactive account can do nothing. Validation:
  - usernames: lower case, 2–64 characters of `a-z 0-9 . _ -`
  - display names: 1–100 characters
  - passwords: 10–256 characters
- **Accounts and sessions** (services; stdlib crypto only):
  - Passwords are hashed with `hashlib.scrypt` (salted, parameters stored with the hash) and compared in constant time. An unknown username still costs one hash, so response times don't reveal which usernames exist.
  - Signing in returns a random session token (`secrets.token_urlsafe(32)`). Only its SHA-256 is stored, so a copy of the database holds no usable sessions. Sessions expire after `INVOICE_INTAKE_SESSION_TTL_HOURS` (default 12).
  - `AccountService`: sign in, sign out, look up a session, list, create and update accounts (role, display name, active, new password). Deactivating an account or changing its password ends its sessions. The last active admin can't be demoted or deactivated.
  - `ensure_demo_accounts`: one account per role, with fixed passwords; existing accounts are never changed.
- **Persistence:** migration 0006 adds `accounts` (unique username) and `sessions` (token hash, account, expiry; removed with the account).
- **API:**
  - `POST /auth/sign-in` sets an HttpOnly, SameSite=Lax cookie, `Secure` when `INVOICE_INTAKE_SESSION_COOKIE_SECURE` is set.
  - `POST /auth/sign-out`, `GET /auth/me`.
  - `GET /auth/demo-accounts` lists the demo credentials only when `INVOICE_INTAKE_DEMO_ACCOUNTS` is on, as in the Docker demo; otherwise it returns an empty list.
  - `GET/POST/PATCH /accounts` for admins.
  - Every invoice endpoint requires a session and the right role: 401 when signed out, 403 for the wrong role. `/health` and the API docs stay public.
  - The audit trail records the signed-in username; `X-User` is gone.
  - Cross-site requests: SameSite=Lax keeps the cookie off cross-site POSTs, and sign-in accepts JSON only, so a forged form can neither act nor sign someone in.
- **Command line** (`python -m invoice_intake.accounts`, or `npm run accounts --` at the root):
  - `create`, which reads the password from a prompt or stdin, never from an argument
  - `set-password`, `list`
  - `demo`
  
  This is how the first admin is made outside the demo.
- **UI:**
  - A sign-in page, which in the demo lists the demo accounts with a "Use" button.
  - A user menu (name, role, Sign out) replacing "Acting as".
  - Viewers see the same screens read-only: no upload, no editing, no decision buttons, and a note saying why.
  - Admins get a **Users** screen: list, add (with a starting password), change role, deactivate or reactivate, set a new password.
  - A session that ends mid-use returns to sign-in.
- **Demo and tools:**
  - The Docker demo creates the demo accounts on start, and its seed signs in to upload.
  - `npm run seed` does both in development.
  - The e2e, the compose smoke test and the screenshots sign in.

Out of scope: single sign-on, self-service sign-up and password reset by email, rate limiting of sign-in attempts (noted as a risk), API tokens for integrations.

## How I Will Verify

- [x] Layer 1 (static): `npm run lint`, `npm run typecheck`, `npm run check-arch` (accounts follow the layer rules)
- [x] Layer 2 (runtime): `npm run test`:
  - domain rules
  - hashing and sessions (expiry, sign-out, ending sessions on deactivation or a password change)
  - the last-admin rule and demo accounts
  - SQL repositories and migration 0006 up and down
  - the cookie's flags
  - **every protected route: 401 signed out, 403 for each role below it, allowed at its role**, checked by walking the app's routes so a new endpoint can't be left open
  - the audit actor is the signed-in user
  - the accounts endpoints and the command line
  - frontend: sign-in, read-only viewer, Users screen, sign-out
- [x] Layer 3a: `npm run verify-all`
- [x] Layer 3 (system): `npm run check` and `npm run verify-feature -- feat-015`:
  - the e2e signs in as the reviewer for the existing flow, and as a viewer, who can't approve
  - `npm run compose:smoke` signs in with a demo account
  - screenshots regenerated
- [x] After the push (when the author agrees to commit): CI green (run 38594156191)

## What Success Looks Like

Opening the app shows a sign-in page; in the Docker demo it lists three demo accounts. A viewer can read everything and change nothing, and the API refuses them too, not just the UI. A reviewer works as before. An admin adds a colleague on the Users screen. The audit trail now says who approved an invoice, and that can be trusted.

## Dependencies

- [x] Depends on: feat-014
- [ ] Blocked by: none

## Risks

- Sign-in attempts are not rate limited. A public deployment would need that, or a proxy that does it. Recorded in the decision.
- The demo passwords are public by design. They exist only where `demo` is run and are listed only with `INVOICE_INTAKE_DEMO_ACCOUNTS` on.
- Many tests sign in now. A helper keeps that one line per test.

## Commit Plan

One commit after the author agrees, after feat-014's.

---

_Signed off by: Claude (Opus 5.5) on 2026-10-14_
