# Sprint Contract

**Feature ID:** feat-016
**Feature Name:** Sign-in rate limiting
**Date:** 2026-10-17
**Estimated Duration:** 1 session

## What I Will Build

Sign-in accepts unlimited attempts today, so passwords can be guessed as fast as the server answers. D-019 deferred this; it is required before any public deployment.

- **Policy** (settings, with these defaults):
  - **Per username:** 5 failed sign-ins within 15 minutes, and that username is refused until 15 minutes after the oldest of those failures.
  - **Per client address:** 20 failed sign-ins within 15 minutes, and that address is refused the same way.
  - **While refused:** sign-in answers **429** with a `Retry-After` header, without checking the password, so a correct guess during the lockout gets nowhere.
  - **Unknown usernames** are counted like real ones, so a lockout doesn't reveal which accounts exist.
  - **A successful sign-in** clears that username's failures. Failures older than the window are removed as sign-ins happen.
- **Storage:** a `sign_in_failures` table (username, client, time) in PostgreSQL, written in the same transaction as the sign-in. Migration 0007 adds it, with indexes for both look-ups. It works across API instances and restarts with no new service.
- **The client address:**
  - nginx sets `X-Forwarded-For` to the connecting address, overwriting whatever the browser sent, so a header can't choose its own address.
  - The API trusts that header only from the proxy: uvicorn's `--proxy-headers`, with `FORWARDED_ALLOW_IPS` set in the Docker stack, where only nginx can reach the API.
  - In development, the Vite proxy and direct calls use the socket address.
- **Layers:**
  - The services hold a `SignInFailureRepository` interface (domain), implemented in infrastructure.
  - `AccountService.sign_in` takes the client address and raises `SignInThrottledError(retry_after_seconds)`.
  - The API maps that to 429 with `Retry-After`.
- **UI:** the sign-in page explains a 429 in plain words ("Too many failed sign-ins. Try again in about N minutes."). The API's message is shown as is.

Out of scope: CAPTCHA, emailing the account owner, rate limits on other endpoints, permanent lockout.

## How I Will Verify

- [x] Layer 1 (static): `npm run lint`, `npm run typecheck`, `npm run check-arch`
- [x] Layer 2 (runtime): `npm run test`, covering:
  - the per-username limit (the right password is refused while locked, and accepted after the window)
  - unknown usernames
  - the per-address limit across usernames
  - clearing on success, and pruning old rows
  - the SQL repository, migration 0007 up and down
  - the API's 429 with `Retry-After`
  - a sign-in page test for the 429 message
- [x] Layer 3a: `npm run verify-all`
- [x] Layer 3 (system): `npm run check`, `npm run verify-feature -- feat-016`; `npm run compose:smoke` (nginx and the proxy headers)
- [ ] After the push (when the author agrees to commit): CI green

## Risks

- **Account lockout as a nuisance:** anyone can lock a known username for up to 15 minutes by failing on purpose. That's the usual trade-off; the lockout is short, and the per-address limit slows whoever does it.
- **Trusting `X-Forwarded-For`:** this is only safe because the API is reachable only through nginx in the Docker stack, and nginx overwrites the header. Exposing the API port directly would need `FORWARDED_ALLOW_IPS` narrowed. The decision records this.

---

_Signed off by: Claude (Opus 5.5) on 2026-10-17_
