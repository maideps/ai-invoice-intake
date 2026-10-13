# Sprint Contract

**Feature ID:** feat-010
**Feature Name:** Export webhook
**Date:** 2026-10-13
**Estimated Duration:** 1 session

## What I Will Build

Approved invoices are delivered to a configured webhook, the stand-in for an accounting system. The worker retries failed deliveries with backoff, and the export state is visible in the API, the review screen and the audit trail. Nothing is ever exported before a person approves it.

- **Domain:**
  - A new audit action, `export_failed`: allowed only while `approved`, only for the `system`, with the attempt, the error, whether it was the last attempt, and the HTTP status if there was one.
  - `Invoice.export_status`, derived from the trail: `pending`, `retrying`, `failed` or `exported`, with the attempt count, the last error and when it was exported.
  - `approved → exported` already exists and stays the only way to `exported`.
- **Payload** (version 1, JSON): invoice id, file name, who approved it and when, the fields in the API's JSON format, and the audit version. Headers:
  - `Idempotency-Key` (the invoice id, the same on every attempt, so receivers can drop duplicates)
  - `X-Invoice-Intake-Delivery` (unique per attempt)
  - `X-Invoice-Intake-Signature: sha256=<HMAC of the body>` when a secret is set
- **Services:**
  - `ExportService`: `begin` (only for `approved`, which builds the payload), `complete` (moves to `exported`), `record_failure`, `request` (a person asks to try again), and a sweep for approvals whose job was lost.
  - `ExportRunner`: one delivery attempt, then delivered, retry, failed or skipped.
  - Approving puts an export job on the queue after the commit.
- **Queue:** jobs gain a `kind` (`extract` or `export`); one worker handles both. Older jobs without a kind count as extraction.
- **Infrastructure:** `HttpWebhookSender` (httpx2). Any non-2xx response, timeout or connection error is a failed attempt, and the message keeps the status and a short piece of the response body.
- **Settings:**
  - `INVOICE_INTAKE_EXPORT_WEBHOOK_URL`: unset means export is off and approved invoices wait.
  - `INVOICE_INTAKE_EXPORT_WEBHOOK_SECRET`
  - `INVOICE_INTAKE_EXPORT_MAX_ATTEMPTS`: default 5
  - `INVOICE_INTAKE_EXPORT_RETRY_BASE_SECONDS`: default 10, doubling
  - `INVOICE_INTAKE_EXPORT_TIMEOUT_SECONDS`: default 10
- **API:**
  - Invoice responses gain `export` (state, attempts, last error, exported at).
  - `POST /invoices/{id}/export` (202) retries an approved invoice's export; 409 otherwise.
  - `GET /health` reports `export_configured`.
- **Persistence:** migration 0005 adds `export_failed` to the action check. Its downgrade refuses while such events exist.
- **UI:**
  - On approved invoices the decision area shows the export state: waiting, retrying (attempt and error), failed with a "Retry export" button, or exported (when), plus a note when export isn't configured.
  - The timeline shows failed attempts.
- **End-to-end:** the Playwright run adds a local webhook receiver; after approval the invoice reaches `exported` in the UI, and the receiver got exactly one signed delivery.

Out of scope: several destinations, batching, a dead-letter queue, editing an invoice after export.

## How I Will Verify

- [x] Layer 1 (static): `npm run lint`, `npm run typecheck`, `npm run check-arch`
- [x] Layer 2 (runtime): `npm run test`:
  - payload shape and signature against a real local HTTP server
  - non-2xx, timeouts and connection errors become delivery errors
  - the runner: delivered (moves to `exported`), retry with the failure recorded, failed after the last attempt, skipped for any status other than `approved` (nothing exported before approval)
  - `export_status` for every state
  - approve queues an export
  - the export endpoint (202, 409, 404)
  - the worker delivers end to end to a local server (PostgreSQL, Redis)
  - migration 0005 up, down and refusal
  - frontend: export states and the retry button
- [x] Layer 3 (system): `npm run check` with the extended Playwright scenario; `npm run verify-feature -- feat-010`

## What Success Looks Like

Approving an invoice delivers one signed POST to the webhook, and a few seconds later the invoice shows "Exported". If the receiver returns 503, the screen shows "Delivery attempt 1 failed: HTTP 503: … Retrying on its own." and the audit trail records each failed attempt. After the last attempt, "Retry export" starts again.

## Dependencies

- [x] Depends on: feat-006 (approval), feat-007 (worker and queue)
- [ ] Blocked by: none

## Risks

- Delivery is at least once: a crash between delivering and recording can send twice. Receivers should de-duplicate on `Idempotency-Key`, which is documented.
- The webhook URL is configuration, not user input, so no protection against server-side request forgery is needed in this version; that would matter if users could enter URLs.

## Commit Plan

One commit: domain, migration, services, sender, worker, API, UI, tests, docs and harness state together.

---

_Signed off by: Claude (Opus 5.5) on 2026-10-13_
