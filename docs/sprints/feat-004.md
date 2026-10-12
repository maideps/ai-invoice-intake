# Sprint Contract

**Feature ID:** feat-004
**Feature Name:** Persistence and upload API
**Date:** 2026-10-12
**Estimated Duration:** 1 session

## What I Will Build

PostgreSQL persistence for invoices and their audit trail, Alembic migrations, and HTTP endpoints to upload an invoice and to list or fetch invoices, their audit events and the original document.

- **Domain:** an `InvoiceRepository` interface, and `Invoice.restore` to rebuild an invoice from stored data. `restore` derives the status from the audit trail and rejects a trail that breaks the state machine.
- **Infrastructure:** SQLAlchemy 2 (sync) with psycopg 3. Tables: `invoices`, `invoice_line_items`, `audit_events`, `invoice_documents` (the original file as `bytea`). Status, actor kind and action columns have CHECK constraints. A trigger makes `audit_events` append-only: UPDATE and DELETE raise. `SqlInvoiceRepository` implements `add`, `get`, `list` (status filter, newest first, paginated, with total) and `save` (updates status and fields, appends only new events, and raises on a concurrent append).
- **Migrations:** Alembic in `backend/migrations/` with one revision for the schema, plus `npm run db:migrate`.
- **Services:** `IntakeService` checks the upload (not empty, within the size limit, and really a PDF, PNG or JPEG by its first bytes; the browser-sent content type is not trusted), then creates and stores the invoice. Read use cases for list, fetch, events and document.
- **API:** `POST /invoices` (multipart; 201 with a `Location` header; 400 for an empty file, 413 for too large, 415 for an unsupported type), `GET /invoices?status=&limit=&offset=`, `GET /invoices/{id}`, `GET /invoices/{id}/events`, `GET /invoices/{id}/document`. The uploader comes from an optional `X-User` header (default `anonymous`) until authentication exists, which is a non-goal for this version.
- **Settings:** `INVOICE_INTAKE_DATABASE_URL` and `INVOICE_INTAKE_MAX_UPLOAD_BYTES`.
- **Architecture rules:** the import checker is generalised to `backend/tools/check_layer_imports.py`. arch-007 still covers the domain, and a new arch-008 stops `api` and `services` from importing `infrastructure`. Only the composition root (`main.py`) wires infrastructure in.

Out of scope: running extraction (feat-005/007), editing fields or approving (feat-006), docker compose (feat-011), authentication (non-goal).

## How I Will Verify

- [ ] Layer 1 (static): `npm run lint`, `npm run typecheck` (mypy --strict, SQLAlchemy typed models)
- [ ] Layer 2 (runtime): `npm run test`. Integration tests run against a throwaway `postgres:16-alpine` container started by testcontainers. Docker must be running; without it they fail with a clear message. They cover:
  - migrations upgrade a clean database, downgrade to empty and upgrade again
  - repository round trip of an invoice with fields, line items and a multi-step audit trail
  - `save` appends events without rewriting old ones
  - the database refuses UPDATE or DELETE on `audit_events`
  - two concurrent `save` calls with the same next sequence: the second raises
  - API: upload a committed sample PDF, read it back, see the `uploaded` audit event and download identical bytes
  - API rejection cases (empty, too large, wrong type, unknown id, bad status filter)
  - list filter and pagination
  - unit tests for `Invoice.restore` (valid trails and each kind of invalid trail) and for upload validation with an in-memory repository
- [ ] Layer 3 (system): `npm run check` and `npm run check-arch` (arch-007 and arch-008) pass; `npm run verify-feature -- feat-004` passes

## What Success Looks Like

`POST /invoices` with `samples/invoices/invoice-001.pdf` returns 201. `GET /invoices/{id}` returns status `uploaded` with one audit event by the uploader, and `GET /invoices/{id}/document` returns the same bytes. All of it is stored in PostgreSQL through migrations that apply cleanly to an empty database.

## Dependencies

- [x] Depends on: feat-002 (passing)
- [ ] Blocked by: none (Docker Desktop is installed and running on the author's machine)

## Risks

- The test suite now needs Docker. A fresh clone without Docker fails `npm run check` with a message that says so (author's choice: fail rather than skip).
- The first run pulls the `postgres:16-alpine` image, which is slow once.
- Listing loads each invoice with its events (one extra query, not N+1); fine at this scale, revisit if lists grow.
- Port 5432 is taken by a local PostgreSQL on the author's machine, so the documented dev database uses port 5433.

## Commit Plan

One commit: persistence, migrations, API, tests, arch rule, docs and harness state together.

---

_Signed off by: Claude (Opus 5.5) on 2026-10-12_
