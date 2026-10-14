# Progress Log

Session continuity source of truth for this project. Update at the end of each session with verified state, blockers, and next steps.

Keep the "Current Verified State" block current at all times; the session log below it is append-only.

## Current Verified State

- Project root: ai-invoice-intake (harness adopter repo, created with create-harness)
- Primary startup command: ./init.sh
- Primary verification command: npm run check
- Current active feature (or none): none (all thirteen features passing: feat-001 to feat-013)
- Current blocker (or none): none (baseline green after harness-upgrade; see D-001)

## Session Log

<!-- Append one session entry per session. Example fields below. -->

### Session 001 — 2026-10-12

- Goal: scaffold the project with ai-harness-framework and plan the features.
- Completed: create-harness scaffold; project-specific README, docs/PRODUCT.md, docs/ARCHITECTURE.md (product section), docs/quality-document.md; 12-feature plan in feature_list.json; productRoots declared in the manifest; LICENSE holder and .gitignore updated.
- Verification run: npm run check-arch (all rules pass); npm run check (65 runner tests, 1-2 intermittent failures in harness-backup tests).
- Evidence captured: none yet (no feature activated).
- Commits: none yet (repo initialised on branch main, nothing committed).
- Files or artifacts updated: README.md, docs/*, feature_list.json, .harness/manifest.json, LICENSE, .gitignore, DECISIONS.md.
- Known risk or unresolved issue: none open. The backup-id collision (flaky harness-backup tests) was fixed upstream in ai-harness-framework (D-021, commit 53eaa48) and applied here with harness-upgrade; npm run check and check-arch pass. harness-upgrade also reset LICENSE (a CORE surface) to the framework's copyright line.
- Next best step: activate feat-001 (FastAPI service skeleton), fill a sprint contract, implement, then verify-feature.

### Session 002 — 2026-10-12

- Goal: feat-001, the FastAPI service skeleton, with the backend covered by the harness gates.
- Completed:
  - Sprint contract in `docs/sprints/feat-001.md`.
  - `backend/`: FastAPI app factory, `GET /health`, typed settings (`INVOICE_INTAKE_*`), layer packages (`api`, `services`, `domain`, `infrastructure`), 12 tests (health, settings, layers), ruff, mypy --strict.
  - `tools/py.mjs` launcher (interpreter lookup, `setup` command, missing-dependency hint) and `tools/skip.mjs`; root `lint`, `typecheck`, `test`, `build` scripts now also run the backend; `setup:backend` and `dev:backend` added (D-003).
  - `e2e` layer set to an explicit SKIP placeholder because the framework's adoption matrix breaks on a customised `package.json` (D-004).
  - README backend quick start, quality document, `productRoots` (`tools/`, `docs/sprints/`).
- Verification run: `npm run check` (all layers pass; e2e reports SKIP); fresh-clone path tested in a throwaway copy (`setup` then tests, ruff, mypy all pass).
- Evidence captured: `.harness/state/feat-001.json` (written by `npm run verify-feature -- feat-001`).
- Commits: none yet.
- Files or artifacts updated: backend/, tools/, package.json, README.md, DECISIONS.md, docs/quality-document.md, docs/sprints/feat-001.md, .harness/manifest.json, .gitignore, PROGRESS.md.
- Known risk or unresolved issue: layer 3b (e2e) is SKIP until feat-009/feat-011; docker is not available in the sandbox used so far, so the compose stack cannot be exercised there; mypy's cache needs a normal writable folder (it fails on the sandbox's mounted drive; set `MYPY_CACHE_DIR` there).
- Next best step: activate feat-002 (invoice domain model and state machine), sprint contract first.

### Session 003 — 2026-10-12

- Goal: take the upstream e2e fix (ai-harness-framework D-022) and confirm it in this repo.
- Completed: `harness-upgrade` applied (scripts/ refreshed; backup 2026-10-12T18-51-02-153Z); the adoption matrix now passes against this repo's customised `package.json` (all cells); D-004 follow-up updated.
- Verification run: `node scripts/adoption-matrix.mjs` (all cells pass); `npm run check` and `npm run check-arch`.
- Evidence captured: this entry.
- Commits: see git log.
- Files or artifacts updated: scripts/ (CORE, via upgrade), LICENSE (CORE, reset by upgrade to the framework's copyright line), DECISIONS.md, PROGRESS.md.
- Known risk or unresolved issue: the e2e layer is still the SKIP placeholder (by design, D-004).
- Next best step: feat-002 (invoice domain model and state machine), sprint contract first.

### Session 004 — 2026-10-12

- Goal: first run on the author's Windows machine, provider-by-config plan change, then feat-002 (invoice domain model and state machine) feat-003 (synthetic invoice generator), feat-004 (persistence and upload API) and feat-005 (AI extraction service).
- Completed:
  - Windows baseline: `npm run setup:backend` and `npm run check` pass (Python 3.14 venv); the earlier mypy cache issue did not occur.
  - D-005: the extraction provider is chosen by `INVOICE_INTAKE_EXTRACTION_PROVIDER` through one factory (default `fake`); feat-005 declaration, ARCHITECTURE.md and README updated (commit f48a0b4).
  - feat-002: sprint contract `docs/sprints/feat-002.md`; domain package (`actors`, `status`, `audit`, `invoice`, `errors`) with the state machine, actor rules (only a user approves or rejects), required rejection reason, append-only audit trail, Decimal-only money, timezone-aware times.
  - feat-003: sprint contract `docs/sprints/feat-003.md`; generator in `backend/tools/samplegen/` (7 fictional vendors, 4 languages, 5 currencies, 3 layouts), `npm run samples`, strict ground-truth loader, 12 committed samples in `samples/invoices/` with `samples/README.md` and `samples/.gitattributes`; ReportLab 4.5.1 pinned (D-006). PDFs checked visually in the browser pane.
  - feat-004: sprint contract `docs/sprints/feat-004.md`; `InvoiceRepository` and `Invoice.restore` in the domain; SQLAlchemy 2 models, `SqlInvoiceRepository`, Alembic migration 0001 (append-only trigger on `audit_events`), `npm run db:migrate`; `IntakeService` (magic-byte type check, size limit, filename cleaning); `POST /invoices`, `GET /invoices`, `/{id}`, `/{id}/events`, `/{id}/document`; uploader from `X-User`; commit before response (`scope="function"`). Import checker generalised to `backend/tools/check_layer_imports.py` with new arch-008 (api/services never import infrastructure). Tests use a testcontainers PostgreSQL and fail with a clear message without Docker (author's choice). D-007.
  - Live check: dev database container on port 5433, `npm run db:migrate`, server via the preview pane, real upload of `invoice-002.pdf` (201, audit event by `maide`, byte-identical download, 415 for a non-invoice file); container and temporary launch config removed afterwards.
  - feat-005: sprint contract `docs/sprints/feat-005.md`; domain output contract (`OUTPUT_SCHEMA`, `parse_extraction`, `ExtractionProvider`); audit events with JSON `details` and the `extraction_recorded` / `extraction_rejected` actions (migration 0002, downgrade refuses while such events exist); `ExtractionService`; `fake` and `openai` providers with `make_extraction_provider` run at startup; `POST /invoices/{id}/extract`; invoice responses carry `confidence`. D-008. Live check with the fake provider (sample to `needs_review`, ground-truth fields, confidence, 409 on repeat, empty fields for an unknown document) and startup refused for `openai` without a key.
  - arch-007 in `.harness/arch-rules.json`: `backend/tools/check_domain_imports.py` fails on any domain import outside the standard library or the domain package; shown to fail on a planted `invoice_intake.config` import.
- Verification run: `npm run verify-feature -- feat-002` to `-- feat-005` (layers 1-3 pass, e2e SKIP placeholder); `npm run check-arch` (all 8 rules pass; arch-007 and arch-008 shown to fail on planted imports); 303 backend tests (including PostgreSQL ones), ruff, mypy --strict on src, tests, tools and migrations.
- Evidence captured: `.harness/state/feat-002.json` to `feat-005.json` (written by verify-feature).
- Commits: f48a0b4 (D-005), 44a0fc1 (feat-002), d0f6278 (feat-003), f28ef17 (feat-004); feat-005 is the next commit.
- Files or artifacts updated: backend/src/invoice_intake/domain/, backend/tests/ (domain tests), backend/tools/, backend/pyproject.toml (pytest and mypy paths), .harness/arch-rules.json, docs/ARCHITECTURE.md, docs/quality-document.md, docs/sprints/feat-002.md, PROGRESS.md, session-handoff.md.
- Known risk or unresolved issue: the state set has no `failed` status; feat-007 (worker) must add it with its transitions. The `Invoice` entity can only be created as a new upload; feat-004 needs a way to rebuild one from stored events. Field edits and their audit actions belong to feat-006. The ground-truth helpers live in `backend/tools/samplegen/`; if the fake extraction provider (feat-005) needs them at runtime, move them into the app package. Upgrading ReportLab means regenerating the samples. `npm run check` now needs Docker running (database tests fail, by design, without it). New audit actions must be added in three places together: `AuditAction` plus `_NOTE_RULES` in the domain, and the `ck_audit_events_action` check (a new migration). The OpenAI provider has never been called for real (no key in this session); only its request shape is tested. The `X-User` header is trusted as-is (no authentication, a documented non-goal).
- Next best step: feat-006 (review and approval API: edit fields, approve, reject, every human decision audited), sprint contract first.

### Session 005 — 2026-10-13

- Goal: feat-006 (review and approval API), feat-007 (background worker and queue), feat-008 (review queue UI) and feat-009 (review detail UI).
- Completed:
  - Sprint contract `docs/sprints/feat-006.md`.
  - JSON field parsing moved to `domain/field_values.py` (shared by AI output and reviewer edits); `parse_field_patch` for partial edits.
  - Domain: `fields_edited` audit action (only in `needs_review`, only by a user, old/new values in details, no event for a no-op edit), `Invoice.version`, approval requires vendor name, invoice number, issue date, currency and total (`ApprovalBlockedError`).
  - `ReviewService` (edit, approve, reject, each checking the reviewer's version); `PATCH /invoices/{id}/fields`, `POST /invoices/{id}/approve`, `POST /invoices/{id}/reject`; invoice responses carry `version`; 422 detail `{message, errors}`.
  - Migration 0003 (`fields_edited` in the action check; downgrade refuses while such events exist). D-009.
  - Test helper invoices now carry approvable fields (`READY_FIELDS`).
  - feat-007: sprint contract `docs/sprints/feat-007.md`; `failed` status (`extracting -> failed` by system with a reason; `failed -> extracting` / `failed -> rejected` by a user); `ExtractionService` split into `request` / `begin` / `complete` / `fail` / `requeue_stale_uploads`; `ExtractionRunner`; `services/queue.py` (`ExtractionQueue`, `AfterCommitQueue`); `infrastructure/queue.py` (reliable Redis queue); `invoice_intake/worker.py` and `npm run dev:worker`; `POST /invoices/{id}/extract` now queues (202); migration 0004; D-010. RQ ruled out: no `fork` / `SIGALRM` on Windows.
  - Published: public repo https://github.com/maideps/ai-invoice-intake (`main` pushed). `LICENSE` names the author (keeping the framework's MIT line for the harness files) and the inherited framework CI is switched to manual runs (D-011).
  - feat-008: sprint contract `docs/sprints/feat-008.md`; `frontend/` (React 19, TypeScript strict, Vite 7, Tailwind v4, shadcn-style primitives, TanStack Query, React Router, Motion, sonner, self-hosted Inter); review queue with status overview and URL filters, drop-zone upload, live list (2 s while busy, 15 s idle), loading / empty / stale / error states, theme toggle, "acting as" (`X-User`); placeholder detail page; `GET /invoices/stats`; OpenAPI export and generated client with drift tests on both sides; `tools/web.mjs` and root scripts (`setup:frontend`, `dev:frontend`, `api:types`; lint, typecheck, test and build now include the frontend). D-012. Plan and concept mockup shared in chat first; author chose calm and clean, system theme.
  - Live check in the browser pane (dev PostgreSQL, Redis, API, worker, Vite): phone and tablet widths, light and dark; queued-to-needs-review without reload; API down then retry; filters in the URL; detail placeholder. Fixed from it: idle refresh (uploads by others never appeared), words in the UI language vs numbers in the viewer locale (the pane's Spanish locale showed "ahora"), a 502 from the dev proxy so "can't reach the API" is said plainly, a stale-data notice, and wording ("Nothing in Failed").
  - feat-009: sprint contract `docs/sprints/feat-009.md`; review screen in `frontend/src/features/review/`: pdf.js viewer (lazy, own chunk) with click-to-highlight in the text layer (`highlight.ts`), field editor with confidence bands and next-low-confidence, totals check in exact cents (`totals.ts`), minimal patch and error mapping (`draft.ts`), approve / reject with reason / retry, 409 conflict banner, audit timeline, keyboard shortcuts. Review mutations in `api/queries.ts`. Real end-to-end tests: `tools/e2e.mjs` + Playwright (`frontend/e2e/review.spec.ts`), replacing the SKIP (D-013 supersedes D-004).
  - Fixed along the way: two ambiguous Playwright selectors, Node's DEP0190 shell warning (shell only for npm/npx), and the vendor chunk pulling pdf.js into every page (now its own lazy `pdf` chunk). Full-resolution screenshots (Playwright, light and dark) confirmed the French total `3 627,23` highlighted in the PDF.
  - The worker end-to-end test found a real race (a read pairing an old invoice row with newer audit events); reads now load in one statement, with a regression test.
  - Live check: dev PostgreSQL and Redis containers, API via the preview pane, worker as a separate process; upload answered in about 120 ms with `uploaded`, the worker reached `needs_review` about 3 s later. Containers, launch config and worker processes cleaned up (on Windows, stopping the npm wrapper left the Python worker running; it was stopped by hand).
  - Live check: dev DB with migrations 0001-0003, server, upload + extract + edit + stale approve (409) + approve, and reject without reason / approve without total (422) then reject; temporary container and launch config removed.
- Verification run: `npm run verify-feature -- feat-006` to `-- feat-009` (feat-009 with the real e2e layer, no SKIP); `npm run check-arch`; 432 backend tests (PostgreSQL and Redis ones included; worker and queue tests repeated three times without flakiness), ruff, mypy --strict; 55 frontend tests, ESLint (zero warnings), `tsc` strict, `vite build`; Playwright e2e on the real stack (containers and processes cleaned up afterwards).
- Evidence captured: `.harness/state/feat-006.json` to `feat-009.json` (written by verify-feature).
- Commits: 4a69540 (feat-005), 351f554 (feat-006), d34e070 (feat-007), fbcd862 (LICENSE and CI, D-011), a6474e0 (feat-008, pushed); feat-009 is the next commit.
- Files or artifacts updated: backend/src/invoice_intake/domain/ (field_values.py, extraction.py, invoice.py, audit.py), services/review.py, api/review.py, api/schemas.py, api/dependencies.py, main.py, migrations/versions/rev_0003_*, tests, README.md, docs/ARCHITECTURE.md, DECISIONS.md, docs/quality-document.md, docs/sprints/feat-006.md, PROGRESS.md, session-handoff.md.
- Known risk or unresolved issue: the acting user is still the trusted `X-User` header; the approval field list is a fixed rule (D-009); the OpenAI provider is still untried with a real key; `npm run check` now needs Docker for PostgreSQL and Redis; several workers need distinct `INVOICE_INTAKE_WORKER_ID`s; the frontend needs Node 20.19+ and `npm run setup:frontend` (with Playwright's Chromium) before `npm run check`; `npm run e2e` uses ports 5434, 6380, 8100 and 5174.
- Next best step: feat-010 (export webhook: approved invoices posted to a configured URL with retries and visible export status), sprint contract first.

### Session 006 — 2026-10-13

- Goal: feat-010 (export webhook).
- Completed:
  - Sprint contract `docs/sprints/feat-010.md`.
  - Domain: `export_failed` audit action (only while `approved`, only by the system; attempt, error, HTTP status, last attempt or not), `Invoice.export_status` derived from the trail (`pending`, `retrying`, `failed`, `exported`), `EXPORTER` actor. Migration 0005 (downgrade refuses while such events exist).
  - Services: `services/export.py` (`export_payload` v1, `ExportService` with `request` / `begin` / `complete` / `record_failure` / `requeue_unsent`, `ExportRunner`, the `ExportSender` interface); approving queues an export after the commit; queue jobs gained a `kind` (`extract` / `export`).
  - Infrastructure: `HttpWebhookSender` (httpx2; `Idempotency-Key`, per-attempt delivery id, HMAC-SHA256 signature).
  - Worker: dispatches by job kind, export backoff, skips export when no URL is set, sweep re-queues approved invoices still pending.
  - API: `export` on invoice responses, `POST /invoices/{id}/export` (202 / 404 / 409), `export_configured` in `GET /health`; settings `INVOICE_INTAKE_EXPORT_*`.
  - UI: export state in the decision area (sending, not configured, retrying, failed with "Retry export", exported), failed attempts in the timeline, closer polling while an export is in flight.
  - E2E: `tools/e2e.mjs` runs an in-process webhook receiver (port 8101) and configures the worker with a URL and secret; the spec checks one signed delivery with the corrected fields and the "Exported" state. Playwright now runs through an async spawn, because `spawnSync` blocked the receiver (found by the first run, where the screen correctly showed the retries).
  - D-014; README, ARCHITECTURE.md, `backend/.env.example`, quality document.
- Verification run: `npm run verify-feature -- feat-010` (all layers, real e2e); `npm run check-arch`; 463 backend tests (worker export tests repeated without flakiness), ruff, mypy --strict; 61 frontend tests, ESLint, `tsc`, `vite build`; Playwright e2e (no containers, ports or processes left behind).
- Evidence captured: `.harness/state/feat-010.json` (written by verify-feature).
- Commits: af657d5 (feat-009); feat-010 is the next commit.
- Files or artifacts updated: backend/src/invoice_intake/ (domain/audit.py, domain/invoice.py, services/export.py, services/queue.py, services/review.py, infrastructure/export_webhook.py, infrastructure/queue.py, api/, config.py, main.py, worker.py), backend/migrations/versions/rev_0005_*, backend/tests/, frontend/src/ (api, features/review, test/server.ts), frontend/e2e/review.spec.ts, tools/e2e.mjs, README.md, docs/, DECISIONS.md, PROGRESS.md, session-handoff.md.
- Known risk or unresolved issue: delivery is at least once (receivers de-duplicate by `Idempotency-Key`); one destination only; the e2e run now also needs port 8101; the acting user is still the trusted `X-User` header.
- Next best step: feat-011 (Docker Compose packaging and project CI), sprint contract first.

### Session 007 — 2026-10-13

- Goal: feat-011 (Docker Compose and CI).
- Completed:
  - Sprint contract `docs/sprints/feat-011.md`.
  - `docker-compose.yml` with these services:
    - `postgres` and `redis`, with health checks and volumes
    - one-shot `migrate`, then `api` (health check) and `worker`
    - one-shot `seed`, which uploads the 12 samples into an empty instance
    - `accounting`, a demo receiver that checks signatures
    - `web`

    Only `web` (8080) and `accounting` (9000) are published, and both ports can be changed.
  - `backend/Dockerfile`: one image for the API, worker, migrations and tools. Python 3.14 slim, non-root, dependencies cached in their own layer, samples from a second build context. `frontend/Dockerfile`: a Vite build served by nginx. `frontend/nginx.conf`: `/api/` proxy with per-request DNS, a 502 JSON message when the API is down, SPA fallback, long caching for hashed assets, 11 MB uploads, `.mjs` served as JavaScript.
  - `backend/tools/seed_samples.py` and `backend/tools/demo_receiver.py`, with tests in `tests/test_compose_tools.py`.
  - `tools/compose-smoke.mjs` (`npm run compose:smoke`): its own Compose project on ports 8180 and 9180. It checks assets, the SPA routes, health, the seeded samples, an upload, an approval and its signed export, then removes everything.
  - `.github/workflows/ci.yml` replaces the switched-off framework workflow. Job `check` runs `setup:*`, Playwright's system libraries, `npm run check` and `check-arch`, and keeps the traces on failure; job `compose` runs the smoke test.
  - D-015 (D-011's CI part marked superseded); README "Run it with Docker", CI badge; ARCHITECTURE.md; quality document.
  - Manual check in the browser pane on `docker compose up --build`:
    - 12 seeded invoices reached "Needs review" on their own.
    - The review screen first showed "This PDF couldn't be displayed": nginx served the pdf.js worker (`.mjs`) as `application/octet-stream`. That is fixed, and the smoke test now checks every built asset's content type.
    - Approving led to "Exported", and the receiver logged the signed delivery.
    - `docker compose down` takes about 3 s and keeps the volumes.
- Verification run: `npm run verify-feature -- feat-011` (all layers, real e2e); `npm run check-arch`; `npm run compose:smoke` (about 25 s with cached images); 470 backend tests, ruff, mypy --strict; the non-Docker backend tests also on Linux (`python:3.14-slim`, 380 passed); 61 frontend tests. The GitHub Actions run is checked after the push.
- Evidence captured: `.harness/state/feat-011.json` (written by verify-feature).
- Commits: 3845c56 (feat-010, pushed); feat-011 is the next commit.
- Files or artifacts updated: docker-compose.yml, backend/Dockerfile, backend/.dockerignore, backend/tools/seed_samples.py, backend/tools/demo_receiver.py, backend/tests/test_compose_tools.py, frontend/Dockerfile, frontend/.dockerignore, frontend/nginx.conf, tools/compose-smoke.mjs, package.json (`compose:smoke`), .github/workflows/ci.yml, README.md, docs/, DECISIONS.md, PROGRESS.md, session-handoff.md.
- Known risk or unresolved issue: the first CI run on GitHub is still to be confirmed; the Compose stack uses fixed demo credentials (local use only); the backend image is about 350 MB.
- Next best step: feat-012 (README, diagram and demo), sprint contract first.

### Session 008 — 2026-10-13

- Goal: feat-012 (README, diagram and demo), committed and pushed without a stop (the author asked to go to the end).
- Completed:
  - Sprint contract `docs/sprints/feat-012.md`.
  - README rewritten product-first:
    - pitch, CI badge and hero screenshot
    - "Run it in five minutes" with the main flow to try
    - a walkthrough (queue, review in light and dark, export with its audit trail)
    - Mermaid component and lifecycle diagrams, and what holds the system together
    - a decisions table (D-005 to D-016, with checked anchors)
    - development, then how it was built

    The per-feature details and the harness command reference are collapsed; the command table stays, so the harness check still applies.
  - `docs/images/` (queue, review, review-dark, exported; about 100 KB each), declared in `productRoots`.
  - `tools/screenshots.mjs` (`npm run screenshots`) and `tools/lib/compose-stack.mjs` (shared with the refactored `tools/compose-smoke.mjs`).
  - `tools/check-docs.mjs` in `npm run lint`.
  - D-016; ARCHITECTURE.md; quality document.
  - Screenshot fixes found by looking at them: a Spanish locale in headless Chromium (`7806,20 US$`), so the locale is now fixed to `en-US`; a shot taken mid-scroll after focusing a field; the export shot reframed on the audit trail.
  - Five-minute check: a fresh clone of github.com/maideps/ai-invoice-intake, `docker compose up --build` with an empty buildx builder (no layer cache, base images and dependencies downloaded). The first attempt failed once in the pip dependency layer, with no output kept. A single build of the same image on its own then passed, and two full runs passed: 205 s and 299 s (with lint running on the same machine) from clone to 12 invoices in "Needs review".
- Verification run: `npm run verify-feature -- feat-012`; `npm run check-arch`; `npm run lint` with the docs check (shown to fail on planted errors); `npm run compose:smoke` after the refactor; `npm run screenshots`.
- Evidence captured: `.harness/state/feat-012.json` (written by verify-feature).
- Commits: c72f3bc (feat-011, pushed; first CI run green); feat-012 is committed and pushed in this session.
- Files or artifacts updated: README.md, docs/images/, docs/ARCHITECTURE.md, docs/quality-document.md, docs/sprints/feat-012.md, DECISIONS.md, tools/check-docs.mjs, tools/screenshots.mjs, tools/lib/compose-stack.mjs, tools/compose-smoke.mjs, package.json (`screenshots`, lint), .harness/manifest.json (`productRoots`), PROGRESS.md, session-handoff.md.
- Known risk or unresolved issue: the single failed cold build has no recorded cause, most likely a network error in pip; if it happens again, keep the full build log. The OpenAI provider has still never been called with a real key.
- Next best step: none planned. Possible next features: authentication (replacing the trusted `X-User`), a real run of the OpenAI provider, image publishing.

### Session 009 — 2026-10-13

- Goal: stop the running app, then feat-013. The author asked to move the frontend and the backend under `repositories/`; they chose folders in this git repository over separate repositories.
- Completed:
  - Stopped the Compose stack (`docker compose down`, data kept) and closed its terminal tab.
  - feat-013 added with `npm run add-feature`, with a repository-gates layer (`npm run verify-all`); sprint contract `docs/sprints/feat-013.md`.
  - Moved with `git mv`:
    - `backend/` to `repositories/backend/`
    - `frontend/` to `repositories/frontend/` (`node_modules` moved with it)
    - `frontend/src/api/openapi.json` to `contracts/openapi.json`

    The template's `repositories/example` was removed, and the backend `.venv` was recreated.
  - `repositories/{backend,frontend}/scripts/verify` (+ `verify.mjs`); `repositories/README.md` and `contracts/README.md` list them.
  - Paths updated:
    - the launchers, e2e, screenshots, compose file, Dockerfile notes, CI (caches, working directory, artifacts)
    - the manifest's `productRoots` and the architecture rules' texts
    - in code: the tests' repository root and the OpenAPI export target; the frontend's `api:types`, drift test and e2e sample
    - `.env.example`, README (layout, repository gates), ARCHITECTURE, samples README
  - Fixed: settings found the samples by counting folder levels, which crashed the migration in the image (`IndexError`, found by the compose smoke test). They now search upwards for `samples/`, with a test.
  - D-017; quality document.
- Verification run:
  - `npm run verify-feature -- feat-013` (lint, test, verify-all, check with the e2e)
  - `npm run verify-all` (backend 471 tests, frontend 61)
  - `npm run check-arch`, `npm run compose:smoke`
  - `npm run api:types`, which produces byte-identical files
  - a search for old root paths, with none left outside history documents
- Evidence captured: `.harness/state/feat-013.json` (written by verify-feature).
- Commits: none yet; waiting for the author.
- Files or artifacts updated: repositories/ (backend, frontend, README), contracts/ (openapi.json, README), tools/ (py, web, e2e, screenshots), docker-compose.yml, .github/workflows/ci.yml, .harness/manifest.json, .harness/arch-rules.json, feature_list.json, README.md, docs/ARCHITECTURE.md, docs/quality-document.md, docs/sprints/feat-013.md, samples/README.md, DECISIONS.md, PROGRESS.md, session-handoff.md.
- Known risk or unresolved issue: any other checkout must run `npm run setup:backend` again after pulling (the old `.venv` points at `backend/`).
- Next best step: commit and push feat-013 when the author agrees, and confirm CI.
