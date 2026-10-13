# Sprint Contract

**Feature ID:** feat-007
**Feature Name:** Background worker and queue
**Date:** 2026-10-13
**Estimated Duration:** 1 session

## What I Will Build

Extraction runs in a separate worker process, fed by a Redis queue. An upload returns at once; the worker takes the invoice through `extracting` to `needs_review`, retries provider failures and rejected output with backoff, and marks the invoice `failed` (with an audited reason) when the attempts run out.

- **Domain:** a new status, `failed`. `extracting` can move to `failed` (by `system`); `failed` can move back to `extracting` (a person asks for a retry) or to `rejected` (a person gives up, with a reason).
- **Services:**
  - `ExtractionService` is split into short transactions: `begin` (move to `extracting`, return the document), `complete` (record the outcome) and `fail` (move to `failed` with a reason). No database transaction stays open during the model call.
  - `ExtractionRunner` runs one attempt from start to finish and reports accepted, retry or failed.
  - `IntakeService` puts each upload on an `ExtractionQueue` (an interface in services).
- **Queue (`infrastructure/queue.py`, D-010):** a small, reliable queue written directly on redis-py.
  - A ready list.
  - A sorted set for delayed retries, moved to the ready list atomically by a Lua script.
  - A per-worker processing list (`BLMOVE`), so a job held by a crashed worker goes back to the queue when it restarts.
  - Jobs are `{invoice_id, attempt}`. Handling them twice is harmless, because an invoice past extraction is skipped.
- **Worker (`invoice_intake/worker.py`, `npm run dev:worker`):** a second composition root.
  - It recovers its processing list at startup, handles jobs, and schedules retries with exponential backoff.
  - It periodically re-queues invoices left in `uploaded` (for example when Redis was down during an upload).
  - It stops cleanly on Ctrl+C or SIGTERM.
- **Upload:** the job goes on the queue only after the upload's transaction commits, so the worker never looks for an invoice that is not stored yet. If Redis is unreachable, the upload still succeeds and the sweep picks it up later.
- **API change:** `POST /invoices/{id}/extract` now queues extraction and returns 202 instead of running it inline (409 when the invoice is past extraction). On a `failed` invoice it records the requesting user's retry (`failed` to `extracting`) first.
- **Persistence:** migration 0004 adds `failed` to the status checks. The downgrade refuses while failed invoices or events exist.
- **Settings:** `INVOICE_INTAKE_REDIS_URL`, `INVOICE_INTAKE_EXTRACTION_MAX_ATTEMPTS` (3), `INVOICE_INTAKE_EXTRACTION_RETRY_BASE_SECONDS` (5, doubling), `INVOICE_INTAKE_WORKER_ID`, `INVOICE_INTAKE_WORKER_SWEEP_SECONDS` (60).

Out of scope: several worker replicas sharing one processing list (each worker has its own id), and scheduling or priorities.

## How I Will Verify

- [ ] Layer 1 (static): `npm run lint`, `npm run typecheck`, `npm run check-arch`
- [ ] Layer 2 (runtime): `npm run test`. Redis tests use a throwaway `redis:7-alpine` container; like PostgreSQL, they fail rather than skip without Docker. They cover:
  - the new transitions and the `failed` status
  - the runner: accepted, provider error then retry then `failed`, rejected output then retry then `failed`, a duplicate job skipped
  - the queue: first in first out, delayed jobs wait, recovery after a crash, a timeout with nothing queued
  - the worker end to end (PostgreSQL, Redis and the fake provider): an upload returns `uploaded` at once and reaches `needs_review`; a provider that keeps failing ends in `failed` after the configured attempts with an audited reason
  - the sweep re-queues stuck uploads
  - the API: extract returns 202, and retrying a `failed` invoice records the user
  - migration 0004 up and down, with the refusal
- [ ] Layer 3 (system): `npm run check`, `npm run verify-feature -- feat-007`, plus a live run (API server and worker process with dev PostgreSQL and Redis containers: upload, then watch the status change)

## What Success Looks Like

With the API and `npm run dev:worker` running, uploading `samples/invoices/invoice-001.pdf` returns 201 with status `uploaded`, and a few moments later `GET /invoices/{id}` shows `needs_review` with the extracted fields. With a provider that keeps failing, the invoice ends up `failed`, with the attempt count and the last error in its audit trail.

## Dependencies

- [x] Depends on: feat-005, feat-006 (passing)
- [ ] Blocked by: none

## Risks

- A self-written queue is more code to own than a library; it is kept small, and its behaviour is pinned by tests against real Redis. RQ was ruled out because its worker needs `fork` and `SIGALRM`, which Windows lacks.
- Existing extraction API tests change, because extraction is no longer synchronous.

## Commit Plan

One commit: domain, migration, services, queue, worker, API change, tests, docs and harness state together.

---

_Signed off by: Claude (Opus 5.5) on 2026-10-13_
