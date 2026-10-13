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
**Status:** accepted (temporary, until feat-009 / feat-011)
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
**Status:** accepted
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
