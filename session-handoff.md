# Session Handoff

Fill this at session end for large sessions; keep it current otherwise.

## Current Objective

- Goal: build AI Invoice Intake, a portfolio project (FastAPI + PostgreSQL + Redis worker + React/TypeScript, OpenAI extraction behind an interface, human approval before export, all data synthetic) using ai-harness-framework, one feature at a time.
- Current status: feat-001 (FastAPI service skeleton), feat-002 (invoice domain model and state machine) feat-003 (synthetic invoice generator), feat-004 (persistence and upload API), feat-005 (AI extraction service), feat-006 (review and approval API), feat-007 (background worker and queue), feat-008 (review queue UI), feat-009 (review detail UI), feat-010 (export webhook), feat-011 (Docker Compose and CI) feat-012 (README, diagram and demo), feat-013 (repositories layout), feat-014 (backend dependency locks), feat-015 (sign-in and roles) and polish-portfolio (README order, docs/HARNESS.md, alt-text check, topics) are `passing`. Released as `v1.0.0`.
- Branch / commit: `main` (feat-012 `0f1e9ec` and `823bf7a` pushed, CI green; feat-013 is not committed yet)
- Layout (D-017): the code lives in `repositories/backend` and `repositories/frontend`, each with `scripts/verify` (`npm run verify-all`); the API contract is `contracts/openapi.json`. After pulling the move elsewhere, rerun `npm run setup:backend`., pushed to the public repo https://github.com/maideps/ai-invoice-intake (`origin`, tracking `origin/main`).

## Completed This Session

- [x] Scaffolded the project with `create-harness`; filled README, `docs/PRODUCT.md`, `docs/ARCHITECTURE.md`, quality document; wrote the 12-feature plan in `feature_list.json`.
- [x] feat-001: FastAPI app factory, `GET /health`, typed `INVOICE_INTAKE_*` settings, layer packages (`api`, `services`, `domain`, `infrastructure`), 12 tests, ruff, mypy --strict.
- [x] Wired the backend into the harness gates through `tools/py.mjs` (D-003); `e2e` is an explicit SKIP placeholder (D-004).
- [x] Session 004: first run on Windows (setup and `npm run check` pass); D-005 (extraction provider chosen by config, default `fake`); feat-002 domain package with arch-007 (domain imports only the standard library); feat-003 sample generator and 12 committed samples (D-006); feat-004 PostgreSQL persistence, migrations and intake API with arch-008 (D-007); feat-005 AI extraction with `fake` and `openai` providers and every model output kept in the audit trail (D-008).
- [x] Session 005: feat-006 review and approval API with audited edits, version checks and required fields for approval (D-009); feat-007 background extraction worker on a reliable Redis queue with retries and a `failed` status (D-010); feat-008 React dashboard with the live review queue, wired into the harness gates (D-012); feat-009 review screen (PDF with click-to-highlight, confidence, totals check, decisions, timeline, shortcuts) and real Playwright e2e on the full stack (D-013).
- [x] Session 006: feat-010 export webhook: signed delivery per approval from the same worker (job kinds), retries with `export_failed` audit events, export state derived from the trail, "Retry export", migration 0005, e2e with a local receiver (D-014).
- [x] Session 007: feat-011 `docker compose up --build` runs the whole product with seeded samples and a demo accounting receiver; backend and web images; `npm run compose:smoke`; the project's own GitHub Actions workflow (D-015).
- [x] Session 008: feat-012 product-first README with screenshots, Mermaid diagrams and a decisions table; `npm run screenshots`; docs check in lint; five-minute start measured from a clean clone (D-016).
- [x] Session 009: feat-013 moved the backend and frontend under `repositories/` with their own gates and the OpenAPI contract in `contracts/` (D-017); fixed the samples lookup that broke in the image.
- [x] Session 010: `docs/INSTALL.md`, a step-by-step install guide (run with Docker, everyday commands, `.env` settings, troubleshooting, development setup), linked from the README; `npm run seed` loads the samples into a development API.
- [x] Session 011: feat-014 universal hashed dependency locks (D-018); feat-015 sign-in with viewer/reviewer/admin, sessions, Users screen and demo accounts (D-019); small clock steps no longer refuse an action (D-020).
- [x] Session 012: the profile README (`maideps/maideps`, commit 4ab7425) features the app; repository topics; README decisions in order with D-017 and D-020; "Built with ai-harness-framework"; harness reference moved to `docs/HARNESS.md`; alt-text check; fresh-clone quick start verified; release v1.0.0.
- [x] Session 013: framework issues #2-#10 checked; framework PRs #20 and #21 (feat-018, feat-019); this project upgraded: generated `PROGRESS.md` with `progress/` notes, generated `docs/HARNESS.md`, `activate`, `.gitattributes` with LF (D-021).
- [x] Fixed two bugs upstream in `ai-harness-framework` and applied them here with `harness-upgrade`: backup-id collisions (D-021, commit 53eaa48) and adoption-matrix fixtures breaking on customised scripts (D-022, commit 79bd6c4).

## Verification Evidence

| Check | Command | Result | Notes |
|---|---|---|---|
| Full verification | `npm run check` | pass | e2e layer reports SKIP (placeholder) |
| Architecture rules | `npm run check-arch` | pass | all rules |
| Feature gate | `npm run verify-feature -- feat-001` | pass | evidence in `.harness/state/feat-001.json` |
| Feature gate | `npm run verify-feature -- feat-002` | pass | evidence in `.harness/state/feat-002.json`; 104 backend tests |
| Feature gate | `npm run verify-feature -- feat-003` | pass | evidence in `.harness/state/feat-003.json`; 129 backend tests |
| Feature gate | `npm run verify-feature -- feat-004` | pass | evidence in `.harness/state/feat-004.json`; 212 backend tests, 36 against PostgreSQL |
| Feature gate | `npm run verify-feature -- feat-005` | pass | evidence in `.harness/state/feat-005.json`; 303 backend tests |
| Feature gate | `npm run verify-feature -- feat-006` | pass | evidence in `.harness/state/feat-006.json`; 371 backend tests |
| Feature gate | `npm run verify-feature -- feat-007` | pass | evidence in `.harness/state/feat-007.json`; 426 backend tests |
| Feature gate | `npm run verify-feature -- feat-008` | pass | 432 backend + 25 frontend tests; ESLint, tsc, vite build |
| Feature gate | `npm run verify-feature -- feat-009` | pass, no SKIP | first run with a real e2e layer |
| Feature gate | `npm run verify-feature -- feat-015` | pass, no SKIP | 554 backend + 71 frontend tests, 2 e2e (reviewer flow; viewer refused by the API) |
| Route matrix | `tests/test_api_auth.py` with a route's permission removed | FAIL as expected | every route: 401 / 403 / allowed |
| Locked install | fresh `setup:backend` (Windows), no-cache image build (Linux) | exactly the lock; `uvloop` only on Linux | D-018 |
| Feature gate | `npm run verify-feature -- feat-013` | pass, no SKIP | includes `npm run verify-all` (backend 471, frontend 61 tests) |
| Feature gate | `npm run verify-feature -- feat-012` | pass, no SKIP | evidence in `.harness/state/feat-012.json` |
| Five-minute start | fresh clone + `docker compose up --build`, empty buildx builder | 205 s and 299 s (with lint running on the same machine) | one earlier attempt failed in pip (cause not kept) |
| Docs check | `node tools/check-docs.mjs` with planted errors | FAIL on missing image, bad anchor, unknown script | |
| Feature gate | `npm run verify-feature -- feat-011` | pass, no SKIP | 470 backend + 61 frontend tests; evidence in `.harness/state/feat-011.json` |
| Compose smoke | `npm run compose:smoke` | all checks pass in ~25 s | asset types, seeded samples, upload, approval, signed export; project removed |
| Compose by hand | `docker compose up --build` + browser pane | 12 seeded, PDF renders, approve leads to Exported, receiver logs it | found and fixed the `.mjs` content type |
| Linux backend | non-Docker tests in `python:3.14-slim` | 380 passed | sample PDFs byte-identical on Linux |
| Feature gate | `npm run verify-feature -- feat-010` | pass, no SKIP | 463 backend + 61 frontend tests; evidence in `.harness/state/feat-010.json` |
| End-to-end | `npm run e2e` (containers, API, worker, Vite, webhook receiver, Chromium) | 1 passed in ~8 s | one signed delivery, invoice shown as exported; nothing left behind |
| Review screen look | Playwright screenshots 1440 px, light and dark | total `3 627,23` highlighted in the PDF | |
| Live dashboard | browser pane: Vite + API + worker + dev DB + Redis | queue live-updates, filters, error/retry, light/dark, phone/tablet | processes and containers cleaned up |
| Live worker | dev PostgreSQL + Redis, API and `npm run dev:worker` as separate processes | upload 201 `uploaded` in ~120 ms; `needs_review` ~3 s later | containers and worker processes cleaned up |
| Live review | dev DB (migrations 0001-0003), server, extract + edit + approve, stale version, reject paths | 200 / 409 / 422 as designed; trail shows editor and approver | temporary container removed |
| Live extraction | dev DB, migrations 0001 and 0002, server, upload + `POST /invoices/{id}/extract` | ground-truth fields, confidence, 4-event trail, 409 on repeat | temporary container removed |
| Startup refuses bad provider config | `INVOICE_INTAKE_EXTRACTION_PROVIDER=openai` without a key | `ProviderConfigurationError` naming the variable | |
| No-Docker behaviour | tests with `DOCKER_HOST` pointing nowhere | database tests fail with the "need Docker running" message; the other 176 pass | |
| Live API | dev DB on 5433, `db:migrate`, `dev:backend`, curl upload | 201, audit event, identical download, 415 for non-invoice | temporary container removed |
| arch-008 can fail | planted infrastructure import in `api/` | FAIL as expected | file removed afterwards |
| Samples reproducible | two runs, same seed; committed files vs fresh run | identical bytes | tested in `repositories/backend/tests/test_samples.py` |
| arch-007 can fail | planted `from invoice_intake.config import Settings` in the domain | FAIL as expected | file removed afterwards |
| Harness matrix | `node scripts/adoption-matrix.mjs` | pass | all cells, with this repo's customised `package.json` |
| Fresh-clone setup | `npm run setup:backend` then tests, ruff, mypy | pass | tested in a throwaway copy |

## Files Changed

- `backend/` (new; since feat-013 `repositories/backend/`): app, tests, `pyproject.toml`, `.env.example`
- `tools/py.mjs`, `tools/skip.mjs` (new); `package.json` scripts (`lint`, `typecheck`, `test`, `build`, `e2e`, `setup:backend`, `dev:backend`)
- `docs/`, `README.md`, `DECISIONS.md` (D-001 to D-004), `PROGRESS.md`, `feature_list.json`, `.harness/manifest.json` (`productRoots`)
- `scripts/` refreshed by `harness-upgrade` (CORE; do not edit by hand); `LICENSE` is CORE too, but its author line is restored by hand after each upgrade (D-011)

## Decisions Made

- D-002: stack and scope (invoices, React, synthetic data, AI behind an interface, human approval required).
- D-003: backend tooling runs through the `tools/py.mjs` launcher wired into the harness scripts.
- D-004: `e2e` stays a SKIP placeholder until real end-to-end tests exist (planned feat-009 / feat-011).
- D-021: follow the framework's generated progress log (`progress/NNN-date.md` notes, then `node scripts/framework-check.mjs progress-update`) and generated `docs/HARNESS.md` (`npm run harness-docs`); `.gitattributes` with LF everywhere.
- D-020: an audit event up to 5 s earlier than the previous one is recorded at the previous event's time (clock steps between the API and the worker); more is refused.
- D-019: sign-in. Roles viewer, reviewer and admin, enforced per route (`Reader`, `Uploader`, `Reviewer`, `Admin`); scrypt passwords; session tokens stored as SHA-256 in an HttpOnly SameSite=Lax cookie, 12 h; admins manage accounts (the last admin stays); `python -m invoice_intake.accounts` (`npm run accounts --`); demo accounts sam.rivera, alex.chen and jordan.lee, created by `accounts demo` and listed only with `INVOICE_INTAKE_DEMO_ACCOUNTS`.
- D-018: backend installs from `requirements.lock` and `requirements-dev.lock` (uv, universal, hashed) with `pip --require-hashes`; `npm run lock:backend` regenerates them, and a test catches drift.
- D-017: backend and frontend under `repositories/` (folders, one git repo), each with `scripts/verify` run by `verify-all`; `contracts/openapi.json` owned by the backend, consumed by the frontend; settings find `samples/` by searching upwards.
- D-016: README product-first (run, walkthrough, diagrams, decisions; harness reference collapsed); `npm run screenshots` from the real stack; `tools/check-docs.mjs` in lint; the five-minute start measured from a clean clone.
- D-015: `docker-compose.yml`: postgres, redis, migrate (one-shot), api, worker, seed (one-shot, only into an empty instance), accounting (demo receiver), web (nginx with `/api/` proxy). Only web 8080 and accounting 9000 are published. One backend image, with samples from a second build context. `tools/compose-smoke.mjs` runs on 8180/9180. CI: `check` (full harness check plus check-arch) and `compose` (smoke) on push and PR. The e2e stays on the dev servers.
- D-014: export via the same worker (job `kind`); payload v1 with `Idempotency-Key`, per-attempt delivery id and HMAC-SHA256 signature; any 2xx succeeds; 5 attempts doubling from 10 s; `export_failed` audit events and a state derived from the trail; `POST /export` to start again; no URL = export off (invoices wait, health says so, sweep sends them later); at least once.
- D-013: `npm run e2e` = `tools/e2e.mjs`: throwaway PostgreSQL (5434) and Redis (6380), migrations, API (8100), worker, Vite (5174), Playwright; full teardown in `finally` (process trees, containers). Supersedes the D-004 SKIP.
- D-012: React 19 + TS strict + Vite 7 + Tailwind v4 + shadcn-style primitives + TanStack Query; generated OpenAPI client with drift tests; polling 2 s / 15 s; numbers in viewer locale, words in UI language; dev proxy answers 502 when the API is down; `tools/web.mjs` joins the frontend to the gates; frontend needs Node 20.19+ (harness still 18).
- D-010: extraction runs in a worker; small reliable queue on redis-py (ready list, delayed zset, per-worker processing list, at-least-once, idempotent steps); attempt = begin / provider call outside any transaction / complete or fail; retries for provider errors and rejected output (3 attempts, 5 s doubling); `failed` status; enqueue after commit plus a periodic sweep; `POST /extract` queues (202).
- D-009: review requests carry the invoice `version` (audit event count) and get 409 when stale; edits are audited `fields_edited` events with old/new values (no event for a no-op); approval needs vendor name, invoice number, issue date, currency and total; 422 detail is `{message, errors}`.
- D-008: one output contract and validator in the domain; providers return raw output; accepted output is recorded as `extraction_recorded` with confidence, rejected output as `extraction_rejected` with errors (invoice stays `extracting`); `fake` matches documents by SHA-256 against the samples; `openai` uses the Responses API with a strict schema, `store=False`, default model `gpt-5.4-mini`.
- D-007: PostgreSQL with SQLAlchemy 2 (sync), psycopg 3 and Alembic; documents in `bytea`; append-only trigger on `audit_events`; one transaction per request that commits before the response; uploader from `X-User` until auth exists; tests on a testcontainers PostgreSQL that fail (not skip) without Docker; dev database on port 5433.
- D-006: samples are generated deterministically (ReportLab invariant mode, no page compression, ReportLab pinned to 4.5.1) and committed; a test fails on drift.
- D-005: the extraction provider is chosen by `INVOICE_INTAKE_EXTRACTION_PROVIDER` through one factory; default `fake`.
- feat-002 domain rules: only a `user` actor may approve or reject; a rejection needs a reason; audit events are append-only, numbered from 1, timezone-aware and never go back in time; money is `Decimal` only.

## Blockers / Risks

- No `failed` status yet: feat-007 (worker) must add it and its transitions to `domain/status.py`.
- `Invoice` can only be created as a new upload; feat-004 needs a way to rebuild one from stored data and events.
- `LICENSE` is a CORE file: after every `harness-upgrade`, restore the author line `Copyright (c) 2026 Maidelin Prieto` (D-011).
- `.github/workflows/ci.yml` is the project's CI (D-015). It is an instance surface, so `harness-upgrade` leaves it alone. Its first run (feat-011) passed both jobs.
- The Compose stack shares image tags (`invoice-intake-backend:local`, `invoice-intake-web:local`) with the smoke test; `docker compose down -v` deletes the demo data.
- `npm run check` needs Docker Desktop running (it is installed on the author's machine but set to start manually). Without it the database tests fail with a message saying so. `docker compose up --build` is tested (D-015).
- New audit actions must be added to `AuditAction`, `_NOTE_RULES` in `domain/invoice.py` (or as status changes) and the `ck_audit_events_action` check in a new migration, together (0002 and 0003 show the pattern, including a downgrade that refuses to drop events).
- `npm run check` needs Docker running (backend tests and e2e), plus `npm run setup:frontend` once (npm ci and Playwright's Chromium) and Node 20.19+. The e2e run needs ports 5434, 6380, 8100, 8101 and 5174 free. The webhook receiver lives inside `tools/e2e.mjs`, so anything it waits on must be async (a `spawnSync` blocks the receiver).
- The browser pane in this app shows large emulated viewports at a fraction of their size; for full-resolution UI checks, take screenshots with Playwright's Chromium instead.
- Frontend tests run under jsdom; three jsdom-vs-Node mismatches are handled in `repositories/frontend/src/test/` (Node `FormData`, a declarative `MemoryRouter`, skipped animations). Keep using `renderApp` and `pdfFile`/`testFile` helpers for new tests.
- After changing the API, run `npm run api:types` (both drift tests fail otherwise).
- On Windows, stopping `npm run dev:worker` (or the API / Vite) from a tool that kills only the npm process can leave the child process running; Ctrl+C in a terminal stops them cleanly.
- Reads load an invoice in one SQL statement on purpose (one snapshot); do not switch them back to separate eager-load queries.
- The OpenAI provider has never been called for real: only its request shape and error mapping are tested with a stub. Try it once with a real key before relying on it.
- Confidence from OpenAI is the model's own estimate; present it as a hint in the review UI (feat-009).
- Every API client must sign in (D-019); scripts use the demo reviewer (`sam.rivera` / `demo-reviewer`). Sign-in is not rate limited yet.
- After changing backend dependencies: `npm run lock:backend` and commit both locks (D-018).
- Ground-truth helpers are in `repositories/backend/tools/samplegen/`; feat-005's fake provider may need them moved into the app package.
- Upgrading ReportLab changes the PDF bytes: run `npm run samples` and commit the result.
- In the earlier sandbox, mypy's cache failed on a mounted drive (not seen on Windows); if mypy errors with a cache or sqlite message, set `MYPY_CACHE_DIR` to a normal local folder.

## Next Session Startup

1. Read `AGENTS.md`.
2. Read `feature_list.json` and `PROGRESS.md`.
3. Review this handoff.
4. Run `npm run setup:backend`, then the standard verification command (`npm run check`) before editing.

## Recommended Next Step

- For the author, by hand: pin `ai-invoice-intake` and `ai-harness-framework` on the profile. GitHub has no API for pins: open https://github.com/maideps, choose **Customize your pins**, tick both repositories and press **Save pins**.
- Candidates for a next round: one real run of the OpenAI provider with a key (see D-008); rate limiting sign-in; publishing the images; a hosted demo. Add any of them with `npm run add-feature` and a sprint contract first.
- After a UI change, run `npm run screenshots` and commit the images; the docs check in lint catches broken README links.
