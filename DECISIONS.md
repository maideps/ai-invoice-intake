# Architectural Decisions Log

This file records significant architectural decisions, their context, alternatives considered, and consequences. It serves as durable cross-session memory for why the codebase is structured the way it is.

## Decision Template

```
### D-XXX: [Decision Title]

**Date:** YYYY-MM-DD
**Status:** proposed | accepted | deprecated | superseded by D-YYY
**Context:** [What problem are we solving? What constraints exist?]
**Decision:** [What did we decide to do?]
**Alternatives considered:**
- Alternative 1: [description] — Rejected because [reason]
**Consequences:**
- Positive: [benefits gained]
- Negative: [tradeoffs accepted]
```

## Recorded Decisions

<!-- Add decision records here, newest last. Expand long records into docs/decisions/ and link back from here. -->

### D-001: Known baseline flake from the framework's backup tests

**Date:** 2026-10-12
**Status:** resolved 2026-10-12 (fixed upstream in ai-harness-framework D-021, applied via harness-upgrade)
**Context:** `npm run check` runs the shipped runner tests. `tests/harness-backup.test.mjs` fails intermittently (1-2 tests) because `createBackup` derives the backup id from `new Date().toISOString()` (millisecond resolution), so two backups in the same millisecond share a directory. Reproduced 5/5 runs in the framework repo itself.
**Decision:** Do not edit CORE files in this repo. Fix the id generation upstream in ai-harness-framework, then apply it here with `harness-upgrade`. Until then, treat these two tests as a known flake and do not mark features passing on a run where they are the only failures without re-running.
**Alternatives considered:**
- Patch scripts/harness-backup.mjs here — Rejected because CORE files must not be edited in adopter repos and the change would be lost on upgrade.
**Consequences:**
- Positive: the harness contract stays intact and the bug gets fixed at its source.
- Negative: the baseline is not reliably green until the upstream fix lands.

### D-002: Tech stack and scope for the portfolio project

**Date:** 2026-10-12
**Status:** accepted (provider selection refined by D-005)
**Context:** The goal is a public portfolio piece showing full-stack and AI-automation skills without using any employer code or data.
**Decision:** FastAPI + PostgreSQL + Redis worker + React/TypeScript, invoices as the document type, all data synthetic, AI extraction behind an interface with a deterministic fake for tests, human approval required before any export.
**Alternatives considered:**
- CVs as the document type — Rejected because it is too close to prior private work (HireLens).
- Vue frontend — Rejected in favour of React for wider hiring recognition.
**Consequences:**
- Positive: clear, verifiable features; no NDA exposure.
- Negative: a larger stack to keep green in CI.

### D-003: Backend tooling runs through a small Node launcher wired into the harness scripts

**Date:** 2026-10-12
**Status:** accepted
**Context:** The harness resolves product verification layers from the root `package.json` scripts (the root is a Node project), but the backend is Python. The author works on Windows, where virtualenv paths differ (`.venv/Scripts` vs `.venv/bin`).
**Decision:** `tools/py.mjs` finds the right interpreter (`$INVOICE_INTAKE_PYTHON`, then `backend/.venv`, then the system Python), prints a clear hint when dependencies are missing, and offers a `setup` command that creates `backend/.venv`. The root `lint`, `typecheck`, `test` and `build` scripts keep the harness's own check and append the backend command with `&&`, so the harness gates cover both. Dev dependency `httpx2` replaces `httpx` because the current Starlette test client deprecates `httpx`.
**Alternatives considered:**
- Add a `pyproject.toml` at the repo root so stack detection picks Python — Rejected: it would shadow the harness's own Node runtime and skip its checks.
- Document the Python commands only in the README — Rejected: the harness gates would not verify the backend.
**Consequences:**
- Positive: one command surface (`npm run check`) covers harness and backend on every OS.
- Negative: a fresh clone must run `npm run setup:backend` once before the gates can pass; the launcher says so when it is missing.

### D-004: The `e2e` layer is an explicit SKIP placeholder until the product has end-to-end tests

**Date:** 2026-10-12
**Status:** superseded by D-013 (real end-to-end tests since feat-009)
**Context:** The harness ships `scripts.e2e` as `node scripts/framework-check.mjs e2e`, which runs the framework's own adoption matrix: it generates throwaway adopter repos from this repository's `package.json` and runs the harness in each. Once this project customised its `package.json` scripts (D-003), the matrix fixtures referenced `tools/py.mjs` and `backend/`, which the fixtures do not contain, so the matrix failed (6 failures) even though the product itself was healthy.
**Decision:** Point `scripts.e2e` at `tools/skip.mjs`, which prints a visible `[SKIP]` and exits 0, so `npm run check` stays runnable and honest about what is not verified. Replace it with real end-to-end tests when the UI exists.
**Alternatives considered:**
- Keep the framework's matrix as the e2e layer — Rejected: it tests the framework, not this product, and breaks on any customised `package.json`.
- Delete the `e2e` script — Rejected: `npm run check` chains `npm run e2e` and would fail with a missing-script error.
**Consequences:**
- Positive: `npm run check` is green and the skipped layer is stated in its output.
- Negative: layer 3b is unverified until real e2e tests exist; the feature gate must not be read as end-to-end evidence yet.
- Follow-up (resolved 2026-10-12): the framework's matrix no longer breaks on customised scripts (ai-harness-framework D-022, commit 79bd6c4), and the matrix passes in this repo after `harness-upgrade`. The placeholder stays anyway: the default e2e layer tests the harness, not this product, so it is replaced only when real end-to-end tests exist.

### D-005: The AI extraction provider is chosen by configuration

**Date:** 2026-10-12
**Status:** accepted (implemented in feat-005; see D-008)
**Context:** D-002 put AI extraction behind an interface but named OpenAI as the only real implementation. The author wants to be able to run the pipeline on other providers (for example Anthropic, Gemini or a local model) without touching the worker, services or review flow.
**Decision:** The `INVOICE_INTAKE_EXTRACTION_PROVIDER` setting names the provider (`openai`, `fake`, and later others). One factory in the infrastructure layer maps that name to an implementation of the domain's `ExtractionProvider` interface; nothing else imports a concrete provider. Each provider reads its own API key and model settings. The default is `fake`, so a fresh clone, the tests and CI run without an API key or network access. An unknown name or a missing key for the chosen provider fails at startup, not on the first invoice. feat-005 ships `openai` and `fake`; each extra provider is a new class plus a factory entry.
**Alternatives considered:**
- Hard-wire OpenAI and swap in the fake only in tests — Rejected: changing provider would mean code changes outside infrastructure.
- Use a multi-provider wrapper library (for example LiteLLM) — Rejected for now: it hides the structured-output and document-input differences between providers that the extraction step depends on, and adds a dependency before there is a second provider.
**Consequences:**
- Positive: adding a provider touches only infrastructure and settings; the default runs offline.
- Negative: providers differ in document input, structured-output support and confidence signals, so each implementation must map its output into the same validated `ExtractionResult`, and each one needs its own tests.

### D-006: Synthetic samples are generated deterministically and committed

**Date:** 2026-10-12
**Status:** accepted
**Context:** feat-003 needs reproducible synthetic invoices (PDF plus ground truth). Later features use them: the fake extraction provider and its tests (feat-005), integration tests (feat-004) and the demo. A PDF normally carries a creation date, a random document id and zlib-compressed streams, and zlib output can differ between platforms and Python builds.
**Decision:** The generator lives in `backend/tools/samplegen/` (entry point `backend/tools/generate_samples.py`, `npm run samples`), uses one `random.Random` per invoice seeded from `(seed, index)`, and builds the ground truth from the domain's `InvoiceFields` and `LineItem`. PDFs are written with ReportLab in invariant mode and without page compression; ReportLab is pinned exactly (4.5.1) as a dev dependency. The default set (seed 42, 12 invoices) is committed to `samples/invoices/`, `samples/.gitattributes` turns off line-ending conversion there, and a test fails when the committed files differ from a fresh run.
**Alternatives considered:**
- Generate samples on the fly in tests and the demo, commit nothing — Rejected: the demo, the docker stack and people browsing the repository need the files, and committing them makes any change in generator output visible in review.
- Keep the generator in `samples/` as the architecture first said — Rejected: it would fall outside the backend's lint, type-check and test commands.
- fpdf2 instead of ReportLab — no strong reason either way; ReportLab has a documented invariant mode for reproducible output.
**Consequences:**
- Positive: byte-identical output on every OS, proven by tests; ground truth is valid domain data by construction.
- Negative: upgrading ReportLab (or changing the generator) means regenerating and re-committing the samples; uncompressed PDFs are larger (about 4-5 KB each, fine at this size).

### D-007: Persistence on PostgreSQL with SQLAlchemy 2, Alembic and container-based tests

**Date:** 2026-10-12
**Status:** accepted
**Context:** feat-004 stores invoices, their audit trail and the uploaded file, and exposes upload and read endpoints. The audit trail is the product's evidence of who decided what, so it must not be editable. Tests must prove the code works against a real PostgreSQL. The author's machine has Docker Desktop, plus a local PostgreSQL on port 5432 whose credentials the project should not depend on.
**Decision:**
- SQLAlchemy 2 (sync) with psycopg 3, and Alembic migrations written by hand. A test compares the models with the migrated schema. Handlers are plain functions, which FastAPI runs in a thread pool.
- The domain owns `InvoiceRepository`; infrastructure implements it. A new arch-008 rule keeps `api` and `services` from importing infrastructure, and `main.py` is the only place that wires it in.
- One transaction per request, through a service factory on `app.state`. The dependency uses FastAPI's `scope="function"` so the commit happens before the response is sent.
- `audit_events` is append-only in the database: a trigger raises on UPDATE or DELETE. `Invoice.restore` derives the status from the trail and rejects a trail the lifecycle rules would not produce. `save` locks the row, appends only new events, and raises `ConcurrentModificationError` when the stored trail moved on.
- The uploaded file goes into PostgreSQL (`bytea`, 10 MB default limit). Its type comes from the file's first bytes (PDF, PNG, JPEG), not from the client.
- The uploader comes from an `X-User` header, default `anonymous`. This is a stand-in until authentication exists, which is a non-goal for version 1.
- Tests start a throwaway `postgres:16-alpine` container with testcontainers. If Docker is unavailable they fail with a clear message instead of skipping, so a green run always means persistence was tested (author's choice). The development database uses port 5433.
**Alternatives considered:**
- Async SQLAlchemy — Rejected for now: the worker (feat-007) will be synchronous anyway, and sync code is simpler to test; thread-pool handlers are enough at this scale.
- Store files on disk or in object storage — Rejected for now: the API and worker containers would need a shared volume or a second service; the `get_document` repository method keeps that change local if it is ever needed.
- SQLite for tests — Rejected: CHECK constraints, triggers, `numeric` scale and row locks behave differently, so tests would prove less.
- Skip database tests without Docker — Rejected by the author: it lets `npm run check` go green without testing persistence.
**Consequences:**
- Positive: history cannot be rewritten even with direct SQL; persistence is tested against the real database engine; the API and services can be tested with an in-memory repository.
- Negative: `npm run check` needs Docker; the first run pulls the image; listing loads each page's invoices with their events (two extra queries per page, fine at this scale).

### D-008: Every AI output is validated in one place and kept in the audit trail

**Date:** 2026-10-12
**Status:** accepted
**Context:** feat-005 adds AI extraction. The product promises that AI output is only a draft and that the audit log shows "model output, confidence, edits, who decided what". Providers differ (D-005), and real models sometimes return malformed or partial output. Tests must never call a real model.
**Decision:**
- The domain owns the output contract: a strict JSON schema with all fields required and nullable, plus a per-field confidence from 0 to 1. `parse_extraction` validates provider output against it and reports every problem at once. Providers only return raw output, so all of them share one validation path.
- Audit events gain a JSON `details` payload. Status columns are now used only for `status_changed`, and a database check enforces that.
- New actions: `extraction_recorded` (the accepted output and its confidence) and `extraction_rejected` (the output, cut to 20,000 characters, and the errors). Both are allowed only while `extracting` and only for an `ai` actor named `provider:model`.
- Rejected output leaves the invoice in `extracting` so a retry can continue (feat-007). A provider failure records nothing and rolls back.
- `fake` provider: it recognises a document by SHA-256 among the committed samples and returns their ground truth with stable, varied confidence. Unknown documents get empty fields and zero confidence.
- `openai` provider: Responses API with a strict `json_schema` format and `store=False`. The document is sent inline (PDF as `input_file`, images as `input_image`). The default model is `gpt-5.4-mini`, set by `INVOICE_INTAKE_OPENAI_MODEL`. Its confidence is the model's own estimate.
- Migration 0002 adds the column and the checks. Its downgrade refuses while extraction events exist, because the trail is append-only.
- `POST /invoices/{id}/extract` runs extraction on request until the worker (feat-007) does it automatically. (Superseded by D-010: it now queues and returns 202.)
**Alternatives considered:**
- Let each provider validate its own output — Rejected: rules would drift between providers, and rejections would not be recorded the same way.
- Drop invalid output after logging it — Rejected: the audit log is the record of what the model said; a rejected answer is evidence too.
- A separate `extractions` table — Rejected for now: the audit trail already orders events, holds the actor and is append-only; a separate table would duplicate that. Revisit if outputs need querying across invoices.
- Per-line-item confidence — Rejected for now: one value for the whole table keeps the contract small; the review UI can still flag the table.
**Consequences:**
- Positive: one place decides what valid output is; every model answer is kept, accepted or not; the default setup runs offline.
- Negative: confidence from real models is not calibrated, so the UI must present it as a hint; the default model name will age (it is a setting); audit events now carry two shapes (status change or note), checked in the domain and the database.

### D-009: Review uses optimistic versions, audited edits and a minimum for approval

**Date:** 2026-10-13
**Status:** accepted
**Context:** feat-006 lets people correct extracted fields, approve and reject. Two reviewers can work on the same invoice, and extraction can run again (feat-007), so a reviewer could approve or overwrite values they never saw. The audit log must show who changed what. An approved invoice goes to export (feat-010), which needs its key values.
**Decision:**
- Optimistic concurrency: `Invoice.version` is the number of audit events. Responses include it; edit, approve and reject must send it back; a different current version is refused with 409 ("reload it and retry"). This works without locks while a reviewer is reading, and needs no extra column because the trail is append-only.
- An edit is a partial patch in the same JSON field format as AI output (`null` clears; `line_items` replaces the whole list). It goes through the same parser, now in `domain/field_values.py`, and is recorded as a `fields_edited` audit event holding the old and new value of each changed field. It is allowed only in `needs_review` and only for a `user` actor. An edit that changes nothing records nothing.
- Approval requires vendor name, invoice number, issue date, currency and total (`REQUIRED_FOR_APPROVAL`). Totals are not cross-checked: a mismatch is a hint for the reviewer, not a block. Rejection still needs a reason.
- Error shape: domain validation failures are 422 with `detail = {message, errors[]}`, so the UI can show every problem. A stale version or the wrong status is 409; an unknown invoice is 404. Malformed request bodies keep FastAPI's own 422 shape.
- Migration 0003 adds `fields_edited` to the action check. Its downgrade refuses while such events exist.
**Alternatives considered:**
- Last write wins — Rejected: a reviewer could approve values someone else just changed without seeing them.
- Lock an invoice while a reviewer has it open — Rejected: it needs lock expiry and cleanup, and the version check gives the same safety more simply.
- Record each edit as a complete snapshot of the fields — Rejected: before/after per changed field is what an auditor reads, and the full fields are always in the invoice row.
- Block approval when totals do not add up — Rejected for now: real invoices have rounding and discount lines the model does not capture; the UI should warn instead (feat-009).
**Consequences:**
- Positive: no silent overwrites; the trail answers "who changed what, from what, to what"; export can rely on the key fields being present.
- Negative: clients must keep the version and reload after a 409; the required-field list is a product rule that may need to become configurable.

### D-010: Extraction runs in a worker fed by a small reliable queue on Redis

**Date:** 2026-10-13
**Status:** accepted
**Context:** feat-007 moves extraction out of the request: uploads must return at once, provider failures must be retried, and an invoice must not be lost if a process dies. The author develops on Windows, which has neither `os.fork` nor `SIGALRM`. A model call can take many seconds and must not hold a database transaction open.
**Decision:**
- A worker process (`python -m invoice_intake.worker`, `npm run dev:worker`) takes jobs `{invoice_id, attempt}` from Redis.
- The queue is written directly on redis-py, about 100 lines in `infrastructure/queue.py`:
  - a ready list (`LPUSH`, and `BLMOVE` from the right)
  - a delayed sorted set for retries, moved to the ready list atomically by a Lua script
  - a per-worker processing list that `recover()` drains back to the queue on startup
  Delivery is at least once.
- Every extraction step is idempotent. An invoice past extraction, or one that no longer exists, makes the job a no-op (`SKIPPED`).
- An attempt is three short transactions: `begin`, the provider call outside any transaction, then `complete` or `fail`.
- Retries cover both provider errors and rejected output, up to `INVOICE_INTAKE_EXTRACTION_MAX_ATTEMPTS` (default 3), waiting `base × 2^(attempt-1)` seconds between attempts (base 5). After the last one the invoice moves `extracting → failed` by `system`, with the attempt count and the last problem as the reason.
- New transitions: `failed → extracting` (a person asks for a retry through `POST /invoices/{id}/extract`, which now returns 202 and only queues) and `failed → rejected` (a person gives up on it, with a reason). A move to `failed` needs a reason.
- The API puts a job on the queue only after its transaction has committed (`AfterCommitQueue`). If Redis is unreachable, the upload still succeeds; the worker's sweep, at start and every `INVOICE_INTAKE_WORKER_SWEEP_SECONDS`, re-queues invoices left in `uploaded` for more than 30 seconds.
- Migration 0004 adds `failed` to the status checks. Its downgrade refuses while failed invoices or events exist.
- Tests run against a throwaway `redis:7-alpine` container and, like PostgreSQL, fail rather than skip without Docker. The worker end-to-end tests run the real loop in a thread.
**Alternatives considered:**
- RQ — Rejected: its worker forks and uses `SIGALRM` for timeouts, neither of which exists on Windows; `SimpleWorker` still needs workarounds.
- Celery — Rejected: far more machinery (broker plus result backend, configuration surface) than one job type needs.
- Dramatiq or arq — Viable, but arq is asyncio-first (the services are sync), and either way the retry policy and audit trail stay in our code, so a library would add a dependency without removing much.
- Use PostgreSQL as the queue (`SELECT … FOR UPDATE SKIP LOCKED`) — A good option, but the feature asked for Redis, and keeping the queue separate shows the hand-off between the services.
- Transactional outbox — Stronger than enqueue-after-commit plus the sweep, but more moving parts; the sweep gives the same eventual result here.
**Consequences:**
- Positive: uploads are instant; no job is lost on a crash or a Redis outage at upload time; the same code runs on Windows, Linux and in Docker; retries and failures are visible in the audit trail.
- Negative: we own the queue code (kept small and tested against real Redis); a job may run twice (harmless, by design); each worker needs its own `INVOICE_INTAKE_WORKER_ID` when several run at once; `npm run check` needs Docker for both PostgreSQL and Redis.

### D-011: Public repository: author in LICENSE, inherited framework CI switched off

**Date:** 2026-10-13
**Status:** accepted; the CI part is superseded by D-015 (the project's own workflow since feat-011)
**Context:** The project is now public at github.com/maideps/ai-invoice-intake. `create-harness` left two things that do not fit a public adopter repo. `LICENSE` named only "AI Harness Framework contributors", and `harness-upgrade` resets it because it is a CORE file. `.github/workflows/ci.yml` is the framework's own CI (its adoption matrix), which does not set up this project's backend, PostgreSQL or Redis.
**Decision:**
- `LICENSE` (MIT) names Maidelin Prieto as the copyright holder. It keeps the framework's line, scoped to the harness files, because MIT requires its notice to stay with that code.
- `ci.yml` only runs when started by hand (`workflow_dispatch`), with a comment saying why. feat-011 replaces it with this project's CI.
**Alternatives considered:**
- Replace the framework's copyright line — Rejected: the harness files (`scripts/`, `templates/`, `skills/`, `tests/`) are the framework's work under MIT.
- Delete `ci.yml` — Rejected: it is declared in the manifest as an instance surface; keeping it switched off avoids manifest churn until feat-011 rewrites it.
**Consequences:**
- Positive: the public repo shows the right author; pull requests do not trigger a CI run that is bound to fail.
- Negative: after every `harness-upgrade`, restore the author line in `LICENSE` (the upgrade overwrites it). There is no CI until feat-011.

### D-012: Frontend stack and how it joins the harness gates

**Date:** 2026-10-13
**Status:** accepted
**Context:** feat-008 starts the review dashboard. The author asked for something "modern and wow", and chose a calm, clean direction with the theme following the system. The harness gates run from the root `package.json` (as with the backend, D-003). The harness pins Node 18 (`.nvmrc`, CORE), but current Vite needs Node 20.19 or newer. Tests must not call real services.
**Decision:**
- React 19 + TypeScript (strict, with `noUncheckedIndexedAccess`) on Vite 7.
- Tailwind CSS v4 with design tokens as CSS variables: neutral zinc greys, one indigo accent, status colours that carry meaning only, light and dark values. Small component primitives in the shadcn/ui style (Radix plus class-variance-authority), lucide icons, Motion for transitions (respecting reduced motion), sonner for toasts, and the Inter font self-hosted rather than loaded from Google.
- TanStack Query for server state; React Router; `openapi-fetch` with types generated by `openapi-typescript` from the committed `frontend/src/api/openapi.json` (`npm run api:types`).
- Live updates by polling: 2 seconds while anything on screen is queued or extracting, 15 seconds otherwise.
- Numbers and currency follow the viewer's browser locale; words (relative times, month names) follow the interface language (English).
- The dev server proxies `/api` to FastAPI (no CORS in development) and answers 502 when the API is down, so the UI can say "can't reach the API".
- `tools/web.mjs` runs the frontend's scripts from the root and says plainly when `npm run setup:frontend` is needed or Node is too old. The root `lint`, `typecheck`, `test` and `build` scripts append it. The frontend declares `engines.node >= 20.19`; the harness itself still runs on 18.
- Tests: Vitest + Testing Library + MSW. The whole app renders against an in-memory API, so the real fetch and query code runs. Three jsdom-versus-Node mismatches are handled in the test setup only:
  - Node's `FormData` replaces jsdom's for uploads.
  - A declarative `MemoryRouter` replaces the data router, which builds requests with jsdom's `AbortSignal`.
  - Animations are skipped.
- Stack majors stay within known versions (React 19, Vite 7, Tailwind 4, Vitest 3) rather than "latest".
**Alternatives considered:**
- Next.js — Rejected: no server rendering is needed for an authenticated-style dashboard behind an API; Vite is simpler to run next to FastAPI.
- A full component kit (MUI, Chakra) — Rejected: heavier and harder to make look distinctive; shadcn-style primitives are code we own.
- Server-sent events for live status — Deferred: polling is enough at this scale and needs no new backend channel.
- Raising `.nvmrc` to 20 — Rejected: it is a CORE harness file; the frontend's own `engines` field and the launcher's check are enough.
**Consequences:**
- Positive: one typed contract between backend and frontend; the gates cover both halves; light, dark, mobile and tablet were checked in a browser.
- Negative: `npm run check` needs `npm run setup:frontend` once and Node 20.19 or newer; the frontend dependency tree is large; polling costs a request every 15 seconds per open queue.

### D-013: End-to-end tests run the real stack with Playwright

**Date:** 2026-10-13
**Status:** accepted (supersedes D-004)
**Context:** D-004 left the `e2e` layer as a SKIP placeholder until there was a UI. feat-009 must show that "an end-to-end test approves an invoice through the UI". The stack has five moving parts (PostgreSQL, Redis, API, worker, web app). The author's machine runs a local PostgreSQL on 5432 and develops on Windows, where stopping a process does not stop its children.
**Decision:**
- `npm run e2e` runs `tools/e2e.mjs`:
  - starts throwaway `postgres:16-alpine` (port 5434) and `redis:7-alpine` (port 6380) containers, waits for them, and applies the Alembic migrations
  - starts the API (8100), the extraction worker and the Vite dev server (5174, proxying to the API), with their output in log files
  - waits for health, then runs `playwright test` in Chromium
  - tears everything down in a `finally`: whole process trees (`taskkill /T` on Windows, process groups elsewhere) and the containers
- Ports differ from development, so a running dev stack is never touched. Only `npm`/`npx` go through a shell on Windows (they are `.cmd` files); everything else runs directly.
- The scenario covers the product's main path: set "acting as", upload a sample through the file picker, wait for the worker, open the review screen, see the PDF and the highlighted total, correct a field, save, approve with the keyboard, and check the audit trail and the queue counts. It uses the fake provider, so no network is needed.
- Docker is required, as for the backend tests; `npm run setup:frontend` installs Playwright's Chromium.
**Alternatives considered:**
- Playwright's `webServer` option — Rejected: it cannot start the worker (no URL to wait on) or the containers, and per-server cleanup on Windows is unreliable.
- docker compose for the stack — Deferred to feat-011: compose will package the app; e2e can switch to it then.
- Mocking the API in browser tests — Rejected: the component tests already do that; this layer exists to prove the real pieces work together.
**Consequences:**
- Positive: `npm run check` now ends with a real end-to-end run (about 10 seconds plus startup); the SKIP is gone.
- Negative: `npm run check` needs Docker and Chromium; the run uses four local ports.

### D-014: Export to a signed webhook, from the same worker

**Date:** 2026-10-13
**Status:** accepted
**Context:** feat-010: approved invoices must reach an accounting system, with retries and a visible export status, and nothing may leave before a person approves it. The worker and the reliable queue from D-010 already exist; there is no real accounting system, so a webhook stands in for one.
**Decision:**
- One queue and one worker: jobs carry a `kind` (`extract` or `export`); old jobs without one are extraction. Approving queues an export job after the commit (`AfterCommitQueue`).
- An attempt is three short steps, as for extraction: `begin` (only for `approved`; builds the payload), the HTTP call outside any transaction, then `complete` (`approved -> exported` by the system) or `record_failure`.
- Payload version 1 (JSON): `payload_version`, `invoice_id`, `filename`, `approved_at`, `approved_by`, `audit_version` and `fields` in the API's JSON format. Headers: `Idempotency-Key` (the invoice id, the same on every attempt), `X-Invoice-Intake-Delivery` (a new id per attempt) and, with a secret, `X-Invoice-Intake-Signature: sha256=<HMAC-SHA256 of the exact body>`.
- Any 2xx is success. Non-2xx answers (the message keeps the status and up to 200 characters of the body), timeouts and connection errors are failed attempts. Defaults: 5 attempts, waits doubling from 10 s, a 10 s timeout.
- Each failed attempt is an `export_failed` audit event (only while `approved`, only by the system) with the attempt, the error, the HTTP status and whether it was the last. The export state (`pending`, `retrying`, `failed`, `exported`) is derived from the trail; migration 0005 adds the action and refuses to downgrade while such events exist.
- `POST /invoices/{id}/export` (202) lets a person start again after the last attempt; 409 for any status other than `approved`.
- No webhook URL means export is off: the worker skips export jobs, invoices stay `approved`, `GET /health` reports `export_configured: false` and the review screen says so. The periodic sweep re-queues approved invoices that are still pending, so they go out once a URL is set.
- Delivery is at least once: a crash between the receiver's answer and `complete` sends again. Receivers drop duplicates by `Idempotency-Key`.
**Alternatives considered:**
- A separate export worker or queue — Rejected: the queue already has everything needed; a `kind` is less to run and to test.
- An "export status" column — Rejected: the audit trail already holds every attempt; a derived state cannot disagree with it.
- Exactly-once delivery (outbox with a receiver acknowledgement protocol) — Rejected: not achievable over a plain webhook; an idempotency key is the standard contract.
- Sending the original PDF in the payload — Deferred: the fields are what an accounting system books; the document can be linked once there is authentication.
- Protection against server-side request forgery for the URL — Not needed now: the URL is operator configuration, not user input.
**Consequences:**
- Positive: approval is the only way out (the runner refuses anything else, and `approved -> exported` is the only transition to `exported`); every attempt is auditable; the end-to-end run proves one signed delivery per approval.
- Negative: receivers must de-duplicate; one destination only; an invoice cannot be edited after export; the e2e run needs one more free port (8101).

### D-015: Docker Compose for the whole product, and the project's own CI

**Date:** 2026-10-13
**Status:** accepted (supersedes the CI part of D-011)
**Context:** feat-011: one command should run the product on synthetic data, and every push should run the checks. The pieces exist (API, worker, migrations, dashboard, export), but the dashboard only had the Vite dev server, and the export needs a receiver. The inherited framework workflow is switched off (D-011).
**Decision:**
- `docker-compose.yml` at the root, with these services:
  - `postgres` and `redis` (health checks, named volumes)
  - one-shot `migrate`, then `api` (health check) and `worker`
  - one-shot `seed`, which uploads the 12 samples only when the instance is empty, so it is safe on every start
  - `accounting`, a demo receiver that checks the HMAC signature and logs and lists deliveries
  - `web`
- Only `web` (8080) and `accounting` (9000) are published, and both ports can be changed. PostgreSQL and Redis stay inside the Compose network, so a local PostgreSQL on 5432 is never touched. Export is on and signed by default with a fixed demo secret; the provider stays `fake` unless overridden.
- One backend image (Python 3.14 slim, non-root) for the API, worker, migrations and helper tools. Dependencies are installed in their own layer from `pyproject.toml`. The samples come from a second build context (`additional_contexts`), so the build context stays `backend/` and the manifest needs no new root files.
- `web` is nginx serving the Vite build and forwarding `/api/` to the API, with Docker's DNS looked up per request, so the API can restart under it. It answers 502 with a JSON message when the API is down, like the dev proxy. It falls back to `index.html` for client routes, caches hashed assets for a year, allows uploads up to 11 MB, and maps `.mjs` to JavaScript. Without that mapping, pdf.js's worker was refused; the manual check found this.
- `tools/compose-smoke.mjs` (`npm run compose:smoke`) runs the stack as its own Compose project on other ports and checks it through nginx:
  - every built asset is served with the right content type
  - the seeded samples are extracted
  - an upload through nginx works
  - its approval leads to one signed delivery

  Afterwards it removes the containers and volumes, also on failure.
- `.github/workflows/ci.yml`, on every push and pull request, with read-only permissions and older runs on the same branch cancelled:
  - job `check`: Node 22, Python 3.14, `setup:backend`, `setup:frontend`, Playwright's system libraries, then `npm run check` (tests and e2e use the runner's Docker) and `npm run check-arch`; Playwright traces are uploaded when it fails
  - job `compose`: the smoke test
- The Playwright e2e keeps running against the dev servers (D-013), not the Compose stack. It tests the current source without image builds; the smoke test covers the packaging.
**Alternatives considered:**
- Running the migrations when the API starts — Rejected: several API replicas would race. A one-shot service is explicit and fails visibly.
- Serving the built dashboard from FastAPI — Rejected: it mixes concerns and loses nginx's caching and upload handling; the dev proxy shape stays the same in both setups.
- Switching the e2e to the Compose stack — Rejected for now: every UI change would need an image build first. The smoke test already proves the packaged stack works.
- Publishing images to a registry — Out of scope (no deployment target).
**Consequences:**
- Positive: `docker compose up --build` is the whole product with data on screen in seconds. CI proves both the source (`check`) and the packaging (`compose`).
- Negative: the backend image is about 350 MB (the OpenAI SDK and uvicorn extras). The demo credentials are fixed, which is fine for synthetic local data but not for deployment. the first CI run took about 2 minutes for `check` and 1 minute for `compose`.

### D-016: A product-first README, checked and reproducible

**Date:** 2026-10-13
**Status:** accepted
**Context:** feat-012: a new reader must be able to run the project from the README alone in under five minutes, and understand what it does and why. The README began as the harness template, with the project's notes added feature by feature, and the harness checks that it documents every make target.
**Decision:**
- The README is ordered for a visitor:
  1. Pitch and a hero screenshot.
  2. "Run it in five minutes": three commands and the main flow to try.
  3. A walkthrough with screenshots.
  4. Mermaid diagrams of the components and the lifecycle (GitHub renders them).
  5. What holds the system together.
  6. The decisions table, linking to this file.
  7. Development, then how it was built.

  The per-feature details and the harness command reference move into collapsed sections. The command table stays, so the harness check still applies.
- The screenshots come from the real Compose stack through `npm run screenshots`. It uses its own project and ports, the same data steps (a correction, three approvals that the worker exports, one rejection), a fixed locale, light and dark, and 1440 × 900. A UI change is one command away from updated images.
- `tools/check-docs.mjs` runs in `npm run lint` and checks four documents (README, ARCHITECTURE, PRODUCT, samples). It checks that relative links and images exist, that `#anchors` match GitHub's heading ids, and that every `npm run` script mentioned exists. It does not fetch external links, so it stays offline and gives the same answer every time.
- The five-minute claim is measured, not assumed. The test clones the public repository into an empty folder and builds with a new, empty buildx builder, so there is no layer cache and the base images and dependencies are downloaded. The README states the measured time.
**Alternatives considered:**
- An animated GIF of the flow — Rejected: large, lossy, and hard to regenerate. Still screenshots show more detail and come from a script.
- A link checker that fetches external URLs — Rejected: it is slow and fails without network or when a site is down; external links are few and stable.
- Moving the harness command reference to its own document — Rejected: `docs/` files are classified by the manifest. A collapsed section keeps the check and the reference without a new surface.
**Consequences:**
- Positive: the first screen of the repository shows the product. Broken links, images or script names fail the lint. The screenshots can always be regenerated.
- Negative: `npm run screenshots` needs Docker and Playwright's Chromium and takes about a minute. The measured start time depends on the network.

### D-017: Backend and frontend as repositories of the multi-repo component, in one git repository

**Date:** 2026-10-13
**Status:** accepted
**Context:** The author asked to move the backend and the frontend under `repositories/`. The harness's multi-repo component was already present but held only the template's `example`. Two shapes were possible: folders in this git repository, or separate GitHub repositories as submodules. The author chose folders.
**Decision:**
- `backend/` moves to `repositories/backend/` and `frontend/` to `repositories/frontend/`, with `git mv`, so file history follows. The template's `repositories/example` is removed.
- Each repository has its own gate, `scripts/verify`, which `npm run verify-all` runs:
  - backend: ruff, ruff format, mypy --strict, pytest, compile check, with its own `.venv`
  - frontend: ESLint, `tsc`, Vitest, build, with its own `node_modules`

  The extension-less `verify` only does `import("./verify.mjs")`. That works whether Node loads the file as CommonJS (the backend) or as ESM (the frontend, whose `package.json` says `"type": "module"`).
- The OpenAPI document becomes a cross-repository contract, `contracts/openapi.json`, owned by the backend and consumed by the frontend. Both drift tests read it there.
- The root stays the control plane: the launchers, `docker-compose.yml`, the e2e and smoke tests, CI and the harness files. Every root command works as before.
- Code no longer counts folder levels to find the samples. Settings search upwards for the folder that holds `samples/`. Counting broke in the image, where Alembic imports the package from `/app/src`; the compose smoke test caught it.
- History documents (past sprint contracts, decisions, progress entries, the feat-001 declaration) keep the old paths: they describe what was true then.
**Alternatives considered:**
- Separate GitHub repositories as submodules — Not chosen by the author. It means three repositories, three CIs, a split history and `--recurse-submodules` for every reader.
- Keeping `openapi.json` in the frontend — Rejected: it is written by the backend and read by the frontend, which is what `contracts/` is for.
- Running `verify-all` in CI as well — Not now: `npm run check` already runs the same tools over both repositories, so it would double the CI time for no new coverage.
**Consequences:**
- Positive: the layout matches the harness's multi-repo model. Each side can be verified alone. The API contract has one visible home with an owner and a consumer.
- Negative: paths are one level deeper. A checkout's `.venv` must be recreated after the move (`npm run setup:backend`), because an editable install records its path.

### D-018: Backend dependencies installed from universal, hash-checked lock files

**Date:** 2026-10-14
**Status:** accepted
**Context:** The backend declared minimum versions only (`fastapi>=0.121` and the like). A new release on PyPI could change what a fresh `docker compose up --build`, `npm run setup:backend` or CI run installs, and break it with no change in the project. The frontend was already locked by `package-lock.json`. The code is developed on Windows, and the image and CI run on Linux; some packages differ by platform (`uvloop` with `uvicorn[standard]` only outside Windows; `colorama` and `pywin32` only on Windows).
**Decision:**
- Two lock files in `repositories/backend/`, generated by `uv pip compile`:
  - `requirements.lock`: the runtime dependencies, for the image.
  - `requirements-dev.lock`: plus the `dev` extra, for setup and CI.
- Both are universal (`--universal`): one resolution for every platform and for Python 3.10 and up, with environment markers.
- Both carry SHA-256 hashes (`--generate-hashes`), and every install uses `pip --require-hashes`. A file that changed on the index is refused.
- `npm run lock:backend` regenerates both. `uv` is a development dependency only: installing needs plain `pip`.
- The project itself is installed separately with `--no-deps`, because `--require-hashes` needs every requirement hashed. The image installs the lock in its own layer, so code changes reuse it. This replaces the earlier stub-package trick.
- `tests/test_dependency_locks.py` fails when:
  - a dependency in `pyproject.toml` is missing from its lock or pinned outside its range
  - a lock entry is not an exact pin with hashes
  - a lock was not generated universally with hashes
  - the two locks disagree on a shared package, which would mean the image runs other versions than the tests
**Alternatives considered:**
- `pip-compile` (pip-tools) — Rejected: it resolves for the machine it runs on. A lock made on Windows would miss `uvloop` and fail the hash-checked install on Linux.
- `uv sync` with `uv.lock` as the install path — Rejected for now: every user and the image would need `uv`. `requirements` files work with the `pip` that comes with Python.
- Pinning exact versions in `pyproject.toml` — Rejected: it pins direct dependencies only, has no hashes, and stops the package from declaring the ranges it supports.
**Consequences:**
- Positive: the same versions on every machine and every day, verified by hash; upgrades are deliberate commits; the image and the tests run the same versions.
- Negative: two generated files of about 3,000 lines in the repository. Adding a package now needs `npm run lock:backend` (the test says so). A fresh `setup:backend` on Windows took about 4 minutes.

### D-019: Sign-in with sessions, and three roles enforced by the API

**Date:** 2026-10-14
**Status:** accepted
**Context:** Until feat-015 the API trusted an `X-User` header: anyone could act as anyone, and the audit trail's "who approved it" proved nothing. The author chose three roles (viewer, reviewer, admin) with a Users screen for admins, and demo accounts listed on the sign-in page of the Docker demo, so visitors still get in within seconds.
**Decision:**
- **Roles** (domain):
  - viewer: read
  - reviewer: read, upload, review
  - admin: all of that and manage accounts

  Inactive accounts can do nothing. The audit trail records the username, which never changes.
- **Passwords:** `hashlib.scrypt` (n=2^14, r=8, p=1, a 16-byte salt) stored as `scrypt$n$r$p$salt$hash`, so the cost can change later. Comparison is constant-time, and an unknown username still costs one hash, so timing doesn't reveal which usernames exist. Passwords have 10–256 characters.
- **Sessions:**
  - The token is `secrets.token_urlsafe(32)`; only its SHA-256 is stored, so a database copy holds no usable sessions.
  - Sessions expire after 12 hours (configurable). Expired ones are removed on sign-in.
  - Signing out deletes the session. Deactivating an account or setting its password deletes all of its sessions; a role change applies on the next request.
- **The cookie:** HttpOnly (scripts can't read it), `SameSite=Lax` (cross-site POSTs don't carry it), `Path=/`, and `Secure` when `INVOICE_INTAKE_SESSION_COOKIE_SECURE` is set. Sign-in accepts JSON only, so a forged HTML form can't sign anyone in either. That covers cross-site request forgery without tokens, because every state-changing route is a non-GET that browsers won't send cross-site with the cookie.
- **API:**
  - `signed_in` gives 401, and `require(permission)` gives 403.
  - Each route declares `Reader`, `Uploader`, `Reviewer` or `Admin` as its first parameter, so the check runs before the route's transaction starts.
  - `/health`, sign-in, sign-out and the demo list are public.
  - `tests/test_api_auth.py` reads every route from the OpenAPI document and fails if one isn't classified. It then checks 401 signed out, 403 for each role below the requirement, and access at the requirement.
- **Account management:** admins only. Usernames are unique and lower case. The last active admin can't be demoted or deactivated. `python -m invoice_intake.accounts` creates the first admin; it reads passwords from a prompt or stdin, never from an argument.
- **Demo accounts:** `sam.rivera` (reviewer), `alex.chen` (viewer) and `jordan.lee` (admin), with public passwords.
  - They are created only by `accounts demo`, which the Docker seed and `npm run seed` run. Existing accounts are never changed.
  - They are listed by `GET /auth/demo-accounts` only when `INVOICE_INTAKE_DEMO_ACCOUNTS` is on, as in the Docker demo.
- **UI:**
  - `<SignedInOnly>` shows the sign-in page without a session, and any 401 returns there.
  - `useCan()` hides what the role can't do: viewers get the same screens read-only, with a note.
  - Admins get the Users screen.
**Alternatives considered:**
- JWTs in local storage — Rejected: scripts could read them (any XSS steals the session), and they can't be revoked before they expire. A server-side session ends the moment it is deleted.
- A CSRF token on every request — Not needed with SameSite=Lax cookies and no state-changing GETs. It would be revisited if the API had to accept cross-site requests.
- Argon2 or bcrypt packages — Rejected for now: scrypt is in the standard library, memory-hard, and the stored parameters allow a later change.
- An identity provider or single sign-on (OIDC) — Out of scope for a self-contained demo. The session layer is where it would plug in.
- Rate limiting sign-in — Deferred: there is no public deployment. A deployment must add it, in the app or at the proxy. (Added by D-022.)
**Consequences:**
- Positive: the audit trail names a person who proved who they are; roles are enforced by the API and tested on every route; viewers can be given read access safely.
- Negative:
  - Every API client must sign in first: the seed, the e2e, the smoke test and the screenshot tool now do.
  - The demo passwords are public by design.
  - There is no password reset by email; an admin, or the command line, sets a new one.
  - Sign-in was not rate limited (until D-022).

### D-020: Small clock steps don't refuse an action

**Date:** 2026-10-14
**Status:** accepted
**Context:** The domain refused any audit event earlier than the previous one ("audit events must not go back in time"). Events are stamped by different processes (the API and the worker) using wall clocks, and a wall clock can step back: NTP corrections, or the time sync of the virtual machine behind Docker Desktop on Windows. Regenerating the screenshots hit it once: a reviewer's edit, made just after the worker finished, was refused with a 422.
**Decision:** An event up to `CLOCK_TOLERANCE` (5 seconds) earlier than the previous event is recorded at the previous event's time. The trail stays in order (its sequence numbers are the authority anyway), and the person's action goes through. An event more than 5 seconds earlier is still refused, because that means a clock is badly wrong and should be noticed.
**Alternatives considered:**
- Database time (`now()`) for every event — Rejected: the domain builds events before saving them, and tests use injected clocks. Clamping in one domain method keeps both.
- Dropping the rule — Rejected: a trail out of order is misleading, and a large skew is worth refusing.
**Consequences:** An event stamped by a slightly late clock shows the previous event's time instead of its own, which is off by at most 5 seconds.

### D-021: Follow ai-harness-framework's generated progress log and command reference

**Date:** 2026-10-17
**Status:** accepted
**Context:** The feedback from building this project became framework issues #2-#10, fixed upstream, and two follow-ups (feat-018, feat-019 in the framework, PRs #20 and #21). Upgrading this project to that version brought new formats with it: a `PROGRESS.md` generated from the feature state plus one note per session in `progress/`; `docs/HARNESS.md` generated from the Makefile and npm scripts; an `activate` command; per-layer verification logs; and `.gitattributes` with LF line endings.
**Decision:**
- Follow the upgrade report:
  - add the `activate` and `harness-docs` npm scripts and the `activate` make target
  - run `progress-migrate`, which moved sessions 001-012 into `progress/` unchanged
  - let `npm run harness-docs` own `docs/HARNESS.md`
- The hand-written `docs/HARNESS.md` from D-016 is replaced by the generated reference. The README keeps its "Built with ai-harness-framework" explanation and links to it.
- `.gitattributes` (`* text=auto eol=lf`) is adopted, and the 29 files committed with CRLF are renormalised once, in their own commit. Mixed line endings had broken scripted edits and inflated diffs (sessions 009 and 011).
**Consequences:**
- Positive: the progress dashboard can't drift from the feature state, the command reference can't drift from the Makefile, every file uses LF, and failed verification layers keep their logs (in `.harness/logs/`, which ignores itself).
- Negative: the line-ending commit touches 29 files without changing their content, so `git blame` shows it for those lines unless `--ignore-rev` is used. Session notes now go in `progress/NNN-date.md`, followed by `node scripts/framework-check.mjs progress-update`.

### D-022: Sign-in is rate-limited per username and per client address

**Date:** 2026-10-17
**Status:** accepted
**Context:** D-019 deferred rate limiting, so passwords could be guessed as fast as the server answered. That has to be fixed before any public deployment.
**Decision:**
- **Limits** (settings): 5 failures for one username, or 20 from one client address, within 15 minutes. Either one refuses sign-in for that username or address until the oldest of those failures is 15 minutes old.
- **While refused:** sign-in answers 429 with `Retry-After`, without checking the password, and a refused attempt isn't recorded, so the lockout can't extend itself.
- **What counts:**
  - Unknown usernames count like real ones, so a lockout doesn't reveal which accounts exist.
  - A successful sign-in clears that username's failures.
- **Storage:** failures are rows in PostgreSQL (`sign_in_failures`, migration 0007), written in the sign-in's own transaction. The sign-in route opens the account service itself and catches the outcome inside the transaction, so a refused sign-in still commits its failure. Old rows are deleted as sign-ins happen.
- **The client address:**
  - nginx sets `X-Forwarded-For` to the connecting address, replacing whatever the browser sent.
  - In the Docker stack, uvicorn trusts that header from any sender (`--forwarded-allow-ips "*"`). That is safe because the API publishes no port: only containers on the stack's network can reach it.
  - Everywhere else, uvicorn's default trusts only 127.0.0.1.
**Alternatives considered:**
- Redis counters — Rejected: PostgreSQL is already in the request's transaction and indexed look-ups are cheap at this volume. Redis would add a second store to keep consistent for no gain.
- Rate limiting at nginx (`limit_req`) — Rejected as the only defence: it can't tell a failed sign-in from a successful one, nor limit per username, and the API must be safe without the proxy.
- Per-account lockout only — Rejected: one address could still try one password against every username. Per-address only — rejected: a botnet spreads its guesses across addresses.
- Lockout until an admin unlocks — Rejected: anyone could lock a known user out indefinitely.
**Consequences:**
- Positive: guessing a password is limited to 5 tries per 15 minutes per account, across API instances and restarts, and the right password doesn't help during a lockout.
- Negative:
  - Anyone who knows a username can lock it out for up to 15 minutes by failing on purpose (the per-address limit slows them down).
  - Exposing the API port directly would require narrowing `--forwarded-allow-ips` to the proxy's address.
