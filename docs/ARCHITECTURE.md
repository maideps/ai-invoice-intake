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

- `backend/` — FastAPI service and extraction worker (Python; `main.py` and `worker.py` are the two composition roots). Layers: `api/` (presentation), `services/` (application), `domain/` (entities, state machine, rules), `infrastructure/` (database, queue, extraction providers, webhook). `main.py` is the composition root: the only module that wires infrastructure into the app. Alembic migrations live in `backend/migrations/` (`npm run db:migrate`).
- `frontend/` — React + TypeScript review dashboard (Vite 7, Tailwind CSS v4, TanStack Query, React Router). `src/api/` holds the generated OpenAPI types and the typed client; `src/features/` holds screens; `src/components/ui/` holds small shadcn/ui-style primitives; `src/lib/` holds formatting, theme, identity and status metadata. The dev server proxies `/api` to FastAPI. `tools/web.mjs` runs its npm scripts from the repository root for the harness gates.
- `samples/` — the committed synthetic invoices (PDF plus ground-truth JSON). The generator that produces them lives in `backend/tools/samplegen/` so the backend's ruff, mypy and pytest cover it; run it with `npm run samples` (D-006).
- `docker-compose.yml` — local stack (API, worker, Postgres, Redis, frontend).

Key design rules:

- The invoice lifecycle is an explicit state machine in the domain layer (`backend/src/invoice_intake/domain/status.py`): `uploaded -> extracting -> needs_review -> approved -> exported`, or `needs_review -> rejected`. `rejected` and `exported` are terminal. Each move names the actor kind allowed to make it: only a `user` may approve or reject, and the platform (`system`) makes every other move. A rejection needs a reason.
- The domain layer imports only the standard library and itself (arch-007); `api` and `services` never import `infrastructure` or `main` (arch-008). Both rules run in `check-arch` through `backend/tools/check_layer_imports.py`.
- Persistence (D-007): the domain defines `InvoiceRepository`; `SqlInvoiceRepository` implements it on PostgreSQL with SQLAlchemy 2. The original upload is stored in the database (`invoice_documents`, `bytea`). A trigger makes `audit_events` append-only, so even direct SQL cannot rewrite history. `Invoice.restore` rebuilds an invoice by replaying its stored trail through the lifecycle rules, and `save` appends only new events with an optimistic concurrency check.
- AI extraction (D-005, D-008): the domain owns the output contract (`OUTPUT_SCHEMA`, `parse_extraction`) and the `ExtractionProvider` interface. Providers in `infrastructure/extraction/` (`fake`, `openai`) return raw output only; `ExtractionService` validates it in one place. Accepted output becomes the invoice's fields and is recorded as an `extraction_recorded` audit event (with per-field confidence) before the move to `needs_review`; rejected output is recorded as `extraction_rejected` with its errors, and the invoice stays in `extracting`. `make_extraction_provider` is the only place that reads provider settings, and it runs at startup.
- Review (D-009): `ReviewService` applies reviewer edits (`parse_field_patch`, the same JSON field format and checks as AI output, from `domain/field_values.py`), approvals and rejections. Edits are `fields_edited` audit events with old and new values; decisions are status changes by the `user` actor. Every review request carries the invoice `version` (its audit event count) and is refused with 409 if the invoice moved on.
- Background extraction (D-010): uploads are queued in Redis only after their transaction commits (`AfterCommitQueue`). The worker (`invoice_intake/worker.py`) reserves a job, runs one attempt with `ExtractionRunner` (`begin`, then the provider call outside any transaction, then `complete` or `fail`, each in its own short transaction), and schedules retries with exponential backoff. After the last attempt the invoice moves to `failed`, with the reason. The queue (`infrastructure/queue.py`) is a small reliable queue on redis-py: a ready list, a delayed sorted set and a per-worker processing list, so a crash never loses a job. Delivery is at least once and every step is idempotent. A periodic sweep re-queues uploads whose job was lost.
- Reads load an invoice with its line items and events in one SQL statement (one snapshot), so a concurrent save can never produce a half-old, half-new invoice.
- The frontend talks to the API only through the client generated from the OpenAPI document (`backend/tools/export_openapi.py` → `frontend/src/api/openapi.json` → `schema.d.ts`); a backend test and a frontend test fail if either step is stale. Server state lives in TanStack Query; lists refresh every 2 s while an invoice on screen is being processed and every 15 s otherwise.
- Each request gets one service and one database transaction, which commits before the response is sent (a failed commit is an error response, never a false success).
- The extraction provider is an interface owned by the domain; infrastructure implements it (OpenAI first, plus a deterministic fake for tests). `INVOICE_INTAKE_EXTRACTION_PROVIDER` selects the implementation in one factory, and nothing else names a concrete provider (D-005).
- Every state change and every AI or human edit appends an audit event; events are never updated or deleted.
