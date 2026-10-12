# Architecture

## Layer Model

This project follows a layered structure:

```
┌─────────────────────────────────────────────┐
│               Presentation Layer             │
│  (UI, CLI, API endpoints — user-facing)     │
├─────────────────────────────────────────────┤
│               Application Layer              │
│  (Use cases, orchestration, workflows)       │
├─────────────────────────────────────────────┤
│                 Domain Layer                  │
│  (Business logic, entities, rules)           │
├─────────────────────────────────────────────┤
│             Infrastructure Layer             │
│  (Persistence, networking, external APIs)    │
└─────────────────────────────────────────────┘
```

## Harness Boundaries

The harness contract (described in `.harness/manifest.json` and enforced by `make check-arch` / `npm run check-arch`) separates:

- **CORE** — files that ship as-is and must not be edited (runner, scripts, templates, root operating manual).
- **TEMPLATES** — adopter skeletons under `templates/`.
- **INSTANCE** — this project's own state (feature list, progress, decisions, docs).
- **PRODUCT-OWNED** — directories listed in the manifest's `productRoots`.

Verification entrypoints delegate to the Node runner (`scripts/framework-check.mjs`); Makefile targets and npm scripts are 1:1 mirrors.

## Worktree Lanes

Multiple agents can work concurrently, each in its own sibling git worktree on branch `lane/<feature-id>` (`make lane-new F=<id>`, `lane-list`, `lane-land F=<id>`, `lane-drop F=<id>`). A branch can only be checked out in one worktree at a time, so git's own branch-checkout exclusivity is the coordination primitive — no lock file needed. WIP=1 is enforced per lane: a `lane/<feature-id>` branch may only activate the feature it is named for.

## Sharded Feature State

`feature_list.json` declares what each feature is and rarely changes; each feature's mutable state (`state`, `evidence`) lives in its own file, `.harness/state/<feature-id>.json`. `verify-feature` writes only that shard, never the shared declarations file — two lanes finishing two different features merge without conflict. `npm run migrate-feature-state` moves an older repo's inline state into shards.

## Application Dependency Rules

- Layers may only depend on layers below them
- Domain layer has zero external dependencies
- Infrastructure implements interfaces defined by domain
- Presentation never directly accesses infrastructure

Encode these rules as entries in `.harness/arch-rules.json` as the codebase grows.

## Enforcement

```bash
make check-arch     # or: npm run check-arch
```

## Module Documentation

Co-locate architecture notes with the modules they affect; record framework-wide decisions in the root `DECISIONS.md`.


## Product Architecture

```
React + TypeScript dashboard  --HTTP-->  FastAPI service  --->  PostgreSQL
                                              |
                                              +--->  Redis queue  --->  Worker  --->  Extraction provider (chosen by config; OpenAI first)
                                                                           |
                                                                           +--->  Export webhook
```

Product directories (declared in `.harness/manifest.json` as `productRoots`):

- `backend/` — FastAPI service and worker (Python). Layers: `api/` (presentation), `services/` (application), `domain/` (entities, state machine, rules), `infrastructure/` (database, queue, extraction providers, webhook). `main.py` is the composition root: the only module that wires infrastructure into the app. Alembic migrations live in `backend/migrations/` (`npm run db:migrate`).
- `frontend/` — React + TypeScript review dashboard.
- `samples/` — the committed synthetic invoices (PDF plus ground-truth JSON). The generator that produces them lives in `backend/tools/samplegen/` so the backend's ruff, mypy and pytest cover it; run it with `npm run samples` (D-006).
- `docker-compose.yml` — local stack (API, worker, Postgres, Redis, frontend).

Key design rules:

- The invoice lifecycle is an explicit state machine in the domain layer (`backend/src/invoice_intake/domain/status.py`): `uploaded -> extracting -> needs_review -> approved -> exported`, or `needs_review -> rejected`. `rejected` and `exported` are terminal. Each move names the actor kind allowed to make it: only a `user` may approve or reject, and the platform (`system`) makes every other move. A rejection needs a reason.
- The domain layer imports only the standard library and itself (arch-007); `api` and `services` never import `infrastructure` or `main` (arch-008). Both rules run in `check-arch` through `backend/tools/check_layer_imports.py`.
- Persistence (D-007): the domain defines `InvoiceRepository`; `SqlInvoiceRepository` implements it on PostgreSQL with SQLAlchemy 2. The original upload is stored in the database (`invoice_documents`, `bytea`). A trigger makes `audit_events` append-only, so even direct SQL cannot rewrite history. `Invoice.restore` rebuilds an invoice by replaying its stored trail through the lifecycle rules, and `save` appends only new events with an optimistic concurrency check.
- Each request gets one service and one database transaction, which commits before the response is sent (a failed commit is an error response, never a false success).
- The extraction provider is an interface owned by the domain; infrastructure implements it (OpenAI first, plus a deterministic fake for tests). `INVOICE_INTAKE_EXTRACTION_PROVIDER` selects the implementation in one factory, and nothing else names a concrete provider (D-005).
- Every state change and every AI or human edit appends an audit event; events are never updated or deleted.
