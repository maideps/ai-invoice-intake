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
**Status:** accepted
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
