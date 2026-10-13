# AI Invoice Intake

A full-stack, human-in-the-loop invoice automation app. Invoices are uploaded, an AI service extracts structured data, and a review dashboard lets a person approve, correct or reject every result before it is exported to downstream systems. Every AI output and every human decision is recorded in an audit log.

> **Portfolio project.** All invoices are synthetic. The project is built with [ai-harness-framework](https://github.com/maideps/ai-harness-framework): one feature at a time, with layered verification and durable session state in this repository.

**Stack (planned):** FastAPI · PostgreSQL · Redis worker · AI extraction provider chosen by config (OpenAI structured outputs first) · React + TypeScript · Docker Compose · GitHub Actions

## Status

Early development. In place so far: the FastAPI service skeleton (`GET /health`, typed settings, layered packages), the invoice domain model and state machine, a synthetic invoice generator with 12 committed samples in [`samples/`](samples/README.md), PostgreSQL persistence with an upload API (`POST /invoices`, list, fetch, audit events, original document), AI extraction in a background worker fed by a Redis queue (with retries and a `failed` status) and the provider chosen by configuration, human review (correct fields, approve or reject, each decision audited with who made it), the React dashboard (a live review queue and a review screen with the document beside the fields), and export of approved invoices to a signed webhook with retries. See [`feature_list.json`](feature_list.json) for the feature plan and [`PROGRESS.md`](PROGRESS.md) for the current state.

## Backend quick start

Requires Node.js >= 20.19 (the frontend; the harness alone runs on 18), Python >= 3.10 and Docker (the database and Redis, and the test suite's throwaway containers).

```bash
npm run setup:backend   # creates backend/.venv and installs the backend with dev tools
npm run setup:frontend  # installs frontend/ dependencies (npm ci)
docker run -d --name invoice-intake-db -p 5433:5432 -e POSTGRES_USER=invoice_intake -e POSTGRES_PASSWORD=invoice_intake -e POSTGRES_DB=invoice_intake postgres:16-alpine
docker run -d --name invoice-intake-redis -p 6379:6379 redis:7-alpine
npm run db:migrate      # applies the Alembic migrations
npm run dev:backend     # serves http://localhost:8000 (docs at /docs)
npm run dev:worker      # in a second terminal: extracts uploaded invoices in the background
npm run dev:frontend    # in a third: the dashboard on http://localhost:5173 (calls the API via /api)
curl http://localhost:8000/health
curl -F "file=@samples/invoices/invoice-001.pdf" -H "X-User: you" http://localhost:8000/invoices
curl http://localhost:8000/invoices/<id>                   # a moment later: needs_review, fields, confidence
curl -X PATCH -H "X-User: you" -H "Content-Type: application/json" -d '{"version": 4, "fields": {"total": "120.00"}}' http://localhost:8000/invoices/<id>/fields
curl -X POST -H "X-User: you" -H "Content-Type: application/json" -d '{"version": 5}' http://localhost:8000/invoices/<id>/approve
npm run samples         # regenerate the synthetic invoices in samples/invoices
```

Configuration comes from `INVOICE_INTAKE_*` environment variables (see [`backend/.env.example`](backend/.env.example)). The development database listens on port 5433 so it does not clash with a local PostgreSQL. The harness commands below cover the backend: `npm run lint` (ruff), `npm run typecheck` (mypy --strict), `npm run test` (pytest) and `npm run build` (compile check).

**AI extraction.** `INVOICE_INTAKE_EXTRACTION_PROVIDER` picks the provider (D-005). The default, `fake`, needs no key or network: it recognises the synthetic samples and returns their ground truth (any other document comes back empty for a reviewer to fill in). For real extraction set it to `openai` together with `INVOICE_INTAKE_OPENAI_API_KEY` (and optionally `INVOICE_INTAKE_OPENAI_MODEL`, default `gpt-5.4-mini`); the app refuses to start if the key is missing. Every model output is validated against one schema and kept in the audit trail, accepted or not (D-008). Tests never call the real model.

**Dashboard.** `frontend/` is React 19 + TypeScript (strict) on Vite 7, styled with Tailwind CSS v4 and small shadcn/ui-style components, with TanStack Query for server state (D-012). The review queue shows a count per status (doubling as filters, kept in the URL), a drop zone for uploads, and a list that refreshes every 2 seconds while the worker is busy (15 seconds otherwise), so invoices visibly move from queued to needs review. It has loading, empty and error states, light and dark themes (following the system by default), and an "acting as" name that is sent as `X-User`. API types are generated from FastAPI's OpenAPI document (`npm run api:types`); tests fail if they drift.

**Review screen.** Opening an invoice shows the original PDF (pdf.js, with its text layer) beside the extracted fields. Selecting a field finds its value in the document and highlights it, trying local formats such as `3 627,23` and `14/02/2026`. Low-confidence fields are tinted amber, with a "next low-confidence field" button. A totals check confirms the lines add up to the subtotal and the subtotal plus tax to the total, in exact cents. Edits, approval and rejection send the invoice `version`; a conflict shows a reload banner instead of an error. The audit trail reads as a timeline, and the keyboard works too (`J`/`K`, `E`, `S`, `A`, `R`, `?`).

**Background extraction.** An upload returns at once with status `uploaded`; the job goes to Redis after the upload is committed. The worker (`npm run dev:worker`) moves the invoice to `extracting` and then `needs_review`. Provider errors and rejected output are retried (`INVOICE_INTAKE_EXTRACTION_MAX_ATTEMPTS`, default 3, with doubling waits from `INVOICE_INTAKE_EXTRACTION_RETRY_BASE_SECONDS`, default 5); when the attempts run out the invoice is `failed` with the reason in its audit trail. `POST /invoices/{id}/extract` (202) asks for another try; on a `failed` invoice it records who asked. If Redis is down during an upload, the upload still succeeds and the worker's periodic sweep queues it later (D-010).

**Review.** `PATCH /invoices/{id}/fields`, `POST /invoices/{id}/approve` and `POST /invoices/{id}/reject` work only in `needs_review` and record the acting user from `X-User`. Each request carries the invoice `version` the reviewer saw; if the invoice changed since, the answer is 409 and nothing changes. Approval needs vendor name, invoice number, issue date, currency and total; rejection needs a reason (D-009).

**Export.** Approving an invoice queues an export job. The worker posts the invoice as JSON to `INVOICE_INTAKE_EXPORT_WEBHOOK_URL` (the stand-in for an accounting system) and moves it to `exported` on any 2xx answer. Non-2xx answers, timeouts and connection errors are retried (`INVOICE_INTAKE_EXPORT_MAX_ATTEMPTS`, default 5, with doubling waits from `INVOICE_INTAKE_EXPORT_RETRY_BASE_SECONDS`, default 10), and each failed attempt is recorded in the audit trail. After the last attempt the review screen offers "Retry export" (`POST /invoices/{id}/export`, 202). Only approved invoices are ever sent. The body carries `payload_version`, the invoice id, file name, who approved it and when, the audit version and the fields in the API's format. Each request has an `Idempotency-Key` (the invoice id, the same on every attempt), a per-attempt `X-Invoice-Intake-Delivery` id, and, when `INVOICE_INTAKE_EXPORT_WEBHOOK_SECRET` is set, `X-Invoice-Intake-Signature: sha256=<HMAC-SHA256 of the body>`. Delivery is at least once, so receivers should drop duplicates by `Idempotency-Key`. Without a URL, export is off: approved invoices wait, the screen says so, and `GET /health` reports `export_configured: false` (D-014).

`npm run lint`, `typecheck`, `test` and `build` cover the frontend too (ESLint with zero warnings, `tsc`, Vitest + Testing Library + MSW, `vite build`); run `npm run setup:frontend` once first (it also installs Playwright's Chromium).

`npm run e2e` (part of `npm run check`) runs the end-to-end tests on the real stack (D-013): it starts throwaway PostgreSQL and Redis containers, applies the migrations, starts the API, the worker and the web app on their own ports, plus a local webhook receiver, and drives Chromium through upload, extraction, review, a correction and an approval, then checks that exactly one signed delivery reached the receiver and the screen shows the invoice as exported. Everything is torn down afterwards, also on failure.

`npm run test` needs Docker running: the database and queue tests start their own `postgres:16-alpine` and `redis:7-alpine` containers and fail with a clear message when Docker is not available. To run everything else without Docker, from `backend/`: `python -m pytest -m "not postgres and not redis"`.

## Quick Start

```bash
# 1. Verify the environment is healthy
./init.sh

# 2. Run full verification (make and npm forms are 1:1 mirrors)
make check          # or: npm run check

# 3. See all available commands
make help           # or: npm run help
```

### Prerequisites

- **Node.js** ≥ 18 — the harness runtime (stack detection, verification layers, session traces)
- **Make** — optional; `npm run <target>` mirrors every make target

## Verification Layers

| Layer | Command | What It Checks |
|-------|---------|----------------|
| 1 | `make lint` / `npm run lint` | Static analysis |
| 1b | `make typecheck` / `npm run typecheck` | Type safety |
| 2 | `make test` / `npm run test` | Unit and integration tests |
| 3 | `make build` / `npm run build` | Build verification |
| 3b | `make e2e` / `npm run e2e` | End-to-end tests |

Layers that are not configured report **SKIP** and do not count as verified.

### Command Targets

Every make target is mirrored 1:1 by an npm script:

| Purpose | Make form | npm form |
|---|---|---|
| Install dependencies | `make setup` | `npm run setup` |
| Dev server | `make dev` | `npm run dev` |
| Full verification | `make check` | `npm run check` |
| Layer 1: static analysis | `make lint` | `npm run lint` |
| Layer 1b: type checking | `make typecheck` | `npm run typecheck` |
| Layer 2: runtime tests | `make test` | `npm run test` |
| Layer 3: build verification | `make build` | `npm run build` |
| Layer 3b: end-to-end tests | `make e2e` | `npm run e2e` |
| Architecture enforcement | `make check-arch` | `npm run check-arch` |
| Feature verification | `make verify-feature F=<id>` | `npm run verify-feature -- <id>` |
| Multi-repo verification | `make verify-all` | `npm run verify-all` |
| Create a worktree lane | `make lane-new F=<id>` | `npm run lane-new -- <id>` |
| List worktree lanes | `make lane-list` | `npm run lane-list` |
| Land a passing lane | `make lane-land F=<id>` | `npm run lane-land -- <id>` |
| Drop a lane | `make lane-drop F=<id>` | `npm run lane-drop -- <id>` |
| Migrate feature state to shards | `make migrate-feature-state` | `npm run migrate-feature-state` |
| Add a feature stub | `make add-feature ID=<id> NAME=<name>` | `npm run add-feature -- <id> <name>` |
| Verify + record trail | `make vcr` | `npm run vcr` |
| Record session start | `make session-start` | `npm run session-start` |
| Record session end | `make session-end` | `npm run session-end` |
| Pre-commit clean state | `make clean-check` | `npm run clean-check` |
| Generate an adopter repo | `make create-harness D=<dir>` | `npm run create-harness -- <dir>` |
| Apply a harness upgrade | `make harness-upgrade D=<dir>` | `npm run harness-upgrade -- <dir>` |
| Local harness audit | `make harness-audit D=<dir>` | `npm run harness-audit -- <dir>` |
| List upgrade backups | `make backup-list` | `npm run backup-list` |
| Pin a backup | `make backup-pin F=<id>` | `npm run backup-pin -- <id>` |
| Unpin a backup | `make backup-unpin F=<id>` | `npm run backup-unpin -- <id>` |
| Restore a backup | `make backup-restore F=<id\|latest>` | `npm run backup-restore -- <id\|latest>` |
| Session report | `make report` | `npm run report` |
| Periodic sweep | `make sweep` | `npm run sweep` |
| Show all targets | `make help` | `npm run help` |

## State Files

- `feature_list.json` — feature declarations: id, behavior, dependencies, verification layers
- `.harness/state/<id>.json` — that feature's mutable state (`state`, `evidence`); one file per feature
- `PROGRESS.md` — session continuity log
- `DECISIONS.md` — architectural decisions log
- `session-handoff.md` — multi-session handoff notes

## Documentation

- [Product Overview](docs/PRODUCT.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Observability](docs/OBSERVABILITY.md)
- [Tools & MCP](docs/TOOLS.md)
- [Usage Guide](docs/USAGE.md)
- [Quality Document](docs/quality-document.md)

## License

MIT — see [LICENSE](LICENSE).
