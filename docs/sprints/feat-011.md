# Sprint Contract

**Feature ID:** feat-011
**Feature Name:** Docker Compose and CI
**Date:** 2026-10-13
**Estimated Duration:** 1 session

## What I Will Build

One command, `docker compose up --build`, runs the whole product on synthetic data: the dashboard at http://localhost:8080, the API, the worker, PostgreSQL, Redis and a demo "accounting system" that receives the exports. A GitHub Actions workflow runs the full harness check, plus a smoke test of the compose stack, on every push and pull request.

- **Images:**
  - `backend/Dockerfile`: one image for the API, the worker, the migrations and the helper tools. Python 3.14 slim, non-root user, the package installed from `pyproject.toml`, `alembic.ini`, the migrations, and the synthetic samples (the fake provider recognises them). The samples come from a second build context, so the build context stays `backend/`.
  - `frontend/Dockerfile`: a Node 22 stage runs `vite build`, then nginx serves the files and forwards `/api/` to the API, as the Vite dev proxy does. The SPA falls back to `index.html`, uploads up to the API's 10 MB limit get through, and hashed assets are cached for a long time.
- **`docker-compose.yml`** (root):
  - `postgres` and `redis`, with health checks and a named volume for the data. Neither is published to the host, so a local PostgreSQL on 5432 is never touched.
  - `migrate`: a one-shot `alembic upgrade head`.
  - `api` (with a health check) and `worker`. Both start after the migrations succeed.
  - `seed`: a one-shot that uploads the 12 samples when the database is empty, so the queue fills and the worker extracts them on the first start. It skips when invoices already exist.
  - `accounting`: a small receiver that checks the HMAC signature, logs each delivery and lists them at `GET /deliveries`. Export is on and signed by default.
  - `web` on `${INVOICE_INTAKE_WEB_PORT:-8080}`; the receiver on `${INVOICE_INTAKE_ACCOUNTING_PORT:-9000}`.
  - The provider stays `fake` unless `INVOICE_INTAKE_EXTRACTION_PROVIDER` and `INVOICE_INTAKE_OPENAI_API_KEY` are passed through.
- **Tools:**
  - `backend/tools/seed_samples.py` and `backend/tools/demo_receiver.py`, both standard library plus httpx, covered by ruff, mypy and tests.
  - `tools/compose-smoke.mjs` (`npm run compose:smoke`) runs its own compose project on other ports and checks that:
    - the dashboard and an SPA route are served
    - `/api/health` answers through nginx with export configured
    - the 12 seeded samples reach `needs_review`
    - an upload through nginx works
    - approving it leads to `exported`, and the receiver got one delivery with a valid signature
    
    It then removes the project and its volumes, also on failure.
- **CI** (`.github/workflows/ci.yml`, replacing the switched-off framework workflow, D-011):
  - Job `check` on Ubuntu runs Node 22, Python 3.14 and Docker (for testcontainers and the e2e). It runs `setup:backend`, `setup:frontend`, Playwright's system dependencies, `npm run check` and `npm run check-arch`, and uploads the Playwright report when the job fails.
  - Job `compose` runs `npm run compose:smoke`.
  - Triggers are push and pull_request. Permissions are read-only, and a newer push to the same branch cancels the older run.

Out of scope: publishing images to a registry, deployment, HTTPS, switching the Playwright e2e to the compose stack (it stays on the dev server for fast iteration; see the decision).

## How I Will Verify

- [x] Layer 1 (static): `npm run lint`, `npm run typecheck`, `npm run check-arch`
- [x] Layer 2 (runtime): `npm run test`, including:
  - the seed tool (skips when invoices exist, uploads every sample otherwise)
  - the demo receiver (records deliveries, accepts a valid signature, rejects a bad one)
- [x] Layer 3 (system; the GitHub run is checked after the push): `npm run check` and `npm run verify-feature -- feat-011`, plus:
  - `npm run compose:smoke` on the local Docker
  - `docker compose up --build` checked by hand in the browser
  - the workflow green on GitHub after the push

## What Success Looks Like

On a machine with only Docker, `docker compose up --build` and then http://localhost:8080 shows a queue of 12 synthetic invoices that move to "Needs review" by themselves. Approving one shows "Exported", and `docker compose logs accounting` shows the signed delivery. On GitHub, every push shows a green `ci` workflow with the `check` and `compose` jobs.

## Dependencies

- [x] Depends on: feat-009 (UI and e2e), feat-010 (export)
- [ ] Blocked by: none

## Risks

- Python 3.14 images and wheels: if a dependency has no 3.14 wheel for Linux, fall back to 3.13 (the code targets 3.10+).
- The CI run needs Docker for testcontainers and the e2e. GitHub's Ubuntu runners have it; the first run will show whether timing is tight.
- The demo secret is a fixed value in `docker-compose.yml`, which is fine for synthetic local data. The compose file says so and allows overriding it.

## Commit Plan

One commit: images, compose, tools, tests, CI, docs and harness state together. The CI result is checked after the push.

---

_Signed off by: Claude (Opus 5.5) on 2026-10-13_
