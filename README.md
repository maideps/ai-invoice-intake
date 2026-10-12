# AI Invoice Intake

A full-stack, human-in-the-loop invoice automation app. Invoices are uploaded, an AI service extracts structured data, and a review dashboard lets a person approve, correct or reject every result before it is exported to downstream systems. Every AI output and every human decision is recorded in an audit log.

> **Portfolio project.** All invoices are synthetic. The project is built with [ai-harness-framework](https://github.com/maideps/ai-harness-framework): one feature at a time, with layered verification and durable session state in this repository.

**Stack (planned):** FastAPI · PostgreSQL · Redis worker · AI extraction provider chosen by config (OpenAI structured outputs first) · React + TypeScript · Docker Compose · GitHub Actions

## Status

Early development. In place so far: the FastAPI service skeleton (`GET /health`, typed settings, layered packages), the invoice domain model and state machine, a synthetic invoice generator with 12 committed samples in [`samples/`](samples/README.md), PostgreSQL persistence with an upload API (`POST /invoices`, list, fetch, audit events, original document), and AI extraction (`POST /invoices/{id}/extract`) with the provider chosen by configuration. See [`feature_list.json`](feature_list.json) for the feature plan and [`PROGRESS.md`](PROGRESS.md) for the current state.

## Backend quick start

Requires Node.js >= 18 (the harness), Python >= 3.10 and Docker (the database, and the test suite's throwaway PostgreSQL).

```bash
npm run setup:backend   # creates backend/.venv and installs the backend with dev tools
docker run -d --name invoice-intake-db -p 5433:5432 -e POSTGRES_USER=invoice_intake -e POSTGRES_PASSWORD=invoice_intake -e POSTGRES_DB=invoice_intake postgres:16-alpine
npm run db:migrate      # applies the Alembic migrations
npm run dev:backend     # serves http://localhost:8000 (docs at /docs)
curl http://localhost:8000/health
curl -F "file=@samples/invoices/invoice-001.pdf" -H "X-User: you" http://localhost:8000/invoices
curl -X POST http://localhost:8000/invoices/<id>/extract   # fields, per-field confidence, audit trail
npm run samples         # regenerate the synthetic invoices in samples/invoices
```

Configuration comes from `INVOICE_INTAKE_*` environment variables (see [`backend/.env.example`](backend/.env.example)). The development database listens on port 5433 so it does not clash with a local PostgreSQL. The harness commands below cover the backend: `npm run lint` (ruff), `npm run typecheck` (mypy --strict), `npm run test` (pytest) and `npm run build` (compile check).

**AI extraction.** `INVOICE_INTAKE_EXTRACTION_PROVIDER` picks the provider (D-005). The default, `fake`, needs no key or network: it recognises the synthetic samples and returns their ground truth (any other document comes back empty for a reviewer to fill in). For real extraction set it to `openai` together with `INVOICE_INTAKE_OPENAI_API_KEY` (and optionally `INVOICE_INTAKE_OPENAI_MODEL`, default `gpt-5.4-mini`); the app refuses to start if the key is missing. Every model output is validated against one schema and kept in the audit trail, accepted or not (D-008). Tests never call the real model.

`npm run test` needs Docker running: the database tests start their own `postgres:16-alpine` container and fail with a clear message when Docker is not available. To run everything else without Docker, from `backend/`: `python -m pytest -m "not postgres"`.

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
