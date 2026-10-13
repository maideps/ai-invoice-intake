# Session Handoff

Fill this at session end for large sessions; keep it current otherwise.

## Current Objective

- Goal: build AI Invoice Intake, a portfolio project (FastAPI + PostgreSQL + Redis worker + React/TypeScript, OpenAI extraction behind an interface, human approval before export, all data synthetic) using ai-harness-framework, one feature at a time.
- Current status: feat-001 (FastAPI service skeleton), feat-002 (invoice domain model and state machine) feat-003 (synthetic invoice generator), feat-004 (persistence and upload API), feat-005 (AI extraction service), feat-006 (review and approval API) and feat-007 (background worker and queue) are `passing`. Nothing else is started. feat-008 (review queue UI) is next.
- Branch / commit: `main` (feat-007 is `d34e070`), pushed to the public repo https://github.com/maideps/ai-invoice-intake (`origin`, tracking `origin/main`).

## Completed This Session

- [x] Scaffolded the project with `create-harness`; filled README, `docs/PRODUCT.md`, `docs/ARCHITECTURE.md`, quality document; wrote the 12-feature plan in `feature_list.json`.
- [x] feat-001: FastAPI app factory, `GET /health`, typed `INVOICE_INTAKE_*` settings, layer packages (`api`, `services`, `domain`, `infrastructure`), 12 tests, ruff, mypy --strict.
- [x] Wired the backend into the harness gates through `tools/py.mjs` (D-003); `e2e` is an explicit SKIP placeholder (D-004).
- [x] Session 004: first run on Windows (setup and `npm run check` pass); D-005 (extraction provider chosen by config, default `fake`); feat-002 domain package with arch-007 (domain imports only the standard library); feat-003 sample generator and 12 committed samples (D-006); feat-004 PostgreSQL persistence, migrations and intake API with arch-008 (D-007); feat-005 AI extraction with `fake` and `openai` providers and every model output kept in the audit trail (D-008).
- [x] Session 005: feat-006 review and approval API with audited edits, version checks and required fields for approval (D-009); feat-007 background extraction worker on a reliable Redis queue with retries and a `failed` status (D-010).
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
| Live worker | dev PostgreSQL + Redis, API and `npm run dev:worker` as separate processes | upload 201 `uploaded` in ~120 ms; `needs_review` ~3 s later | containers and worker processes cleaned up |
| Live review | dev DB (migrations 0001-0003), server, extract + edit + approve, stale version, reject paths | 200 / 409 / 422 as designed; trail shows editor and approver | temporary container removed |
| Live extraction | dev DB, migrations 0001 and 0002, server, upload + `POST /invoices/{id}/extract` | ground-truth fields, confidence, 4-event trail, 409 on repeat | temporary container removed |
| Startup refuses bad provider config | `INVOICE_INTAKE_EXTRACTION_PROVIDER=openai` without a key | `ProviderConfigurationError` naming the variable | |
| No-Docker behaviour | tests with `DOCKER_HOST` pointing nowhere | database tests fail with the "need Docker running" message; the other 176 pass | |
| Live API | dev DB on 5433, `db:migrate`, `dev:backend`, curl upload | 201, audit event, identical download, 415 for non-invoice | temporary container removed |
| arch-008 can fail | planted infrastructure import in `api/` | FAIL as expected | file removed afterwards |
| Samples reproducible | two runs, same seed; committed files vs fresh run | identical bytes | tested in `backend/tests/test_samples.py` |
| arch-007 can fail | planted `from invoice_intake.config import Settings` in the domain | FAIL as expected | file removed afterwards |
| Harness matrix | `node scripts/adoption-matrix.mjs` | pass | all cells, with this repo's customised `package.json` |
| Fresh-clone setup | `npm run setup:backend` then tests, ruff, mypy | pass | tested in a throwaway copy |

## Files Changed

- `backend/` (new): app, tests, `pyproject.toml`, `.env.example`
- `tools/py.mjs`, `tools/skip.mjs` (new); `package.json` scripts (`lint`, `typecheck`, `test`, `build`, `e2e`, `setup:backend`, `dev:backend`)
- `docs/`, `README.md`, `DECISIONS.md` (D-001 to D-004), `PROGRESS.md`, `feature_list.json`, `.harness/manifest.json` (`productRoots`)
- `scripts/` refreshed by `harness-upgrade` (CORE; do not edit by hand); `LICENSE` is CORE too, but its author line is restored by hand after each upgrade (D-011)

## Decisions Made

- D-002: stack and scope (invoices, React, synthetic data, AI behind an interface, human approval required).
- D-003: backend tooling runs through the `tools/py.mjs` launcher wired into the harness scripts.
- D-004: `e2e` stays a SKIP placeholder until real end-to-end tests exist (planned feat-009 / feat-011).
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
- `.github/workflows/ci.yml` is the framework's CI, switched to manual runs only; there is no project CI until feat-011 (D-011).
- The e2e layer is not verified; do not treat a green `npm run check` as end-to-end evidence yet.
- `npm run check` needs Docker Desktop running (it is installed on the author's machine but set to start manually). Without it the database tests fail with a message saying so. `docker compose` (feat-011) is still untested.
- New audit actions must be added to `AuditAction`, `_NOTE_RULES` in `domain/invoice.py` (or as status changes) and the `ck_audit_events_action` check in a new migration, together (0002 and 0003 show the pattern, including a downgrade that refuses to drop events).
- `npm run check` needs Docker running for PostgreSQL and Redis test containers.
- On Windows, stopping `npm run dev:worker` from a tool that kills only the npm process can leave the Python worker running; Ctrl+C in a terminal stops it cleanly.
- Reads load an invoice in one SQL statement on purpose (one snapshot); do not switch them back to separate eager-load queries.
- The OpenAI provider has never been called for real: only its request shape and error mapping are tested with a stub. Try it once with a real key before relying on it.
- Confidence from OpenAI is the model's own estimate; present it as a hint in the review UI (feat-009).
- The `X-User` header is trusted as-is; there is no authentication (non-goal for version 1).
- Ground-truth helpers are in `backend/tools/samplegen/`; feat-005's fake provider may need them moved into the app package.
- Upgrading ReportLab changes the PDF bytes: run `npm run samples` and commit the result.
- In the earlier sandbox, mypy's cache failed on a mounted drive (not seen on Windows); if mypy errors with a cache or sqlite message, set `MYPY_CACHE_DIR` to a normal local folder.

## Next Session Startup

1. Read `AGENTS.md`.
2. Read `feature_list.json` and `PROGRESS.md`.
3. Review this handoff.
4. Run `npm run setup:backend`, then the standard verification command (`npm run check`) before editing.

## Recommended Next Step

- Start feat-008 (review queue UI): sprint contract in `docs/sprints/feat-008.md`, set `.harness/state/feat-008.json` to active. Scaffold `frontend/` (React + TypeScript, Vite), wire its lint, typecheck, test and build into the root npm scripts next to the backend (as D-003 did), and build the queue list with status filters plus loading, empty and error states against the existing API (`GET /invoices`, `version`, `confidence`). Then `npm run verify-feature -- feat-008`.
