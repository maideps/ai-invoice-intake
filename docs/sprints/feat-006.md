# Sprint Contract

**Feature ID:** feat-006
**Feature Name:** Review and approval API
**Date:** 2026-10-13
**Estimated Duration:** 1 session

## What I Will Build

Endpoints for a reviewer to correct extracted fields, approve or reject an invoice. The state machine is enforced, and every human decision is recorded in the audit trail with who made it and what changed.

- **Domain:**
  - The JSON field parsing moves to `domain/field_values.py`, so AI output and reviewer edits share one set of checks.
  - `parse_field_patch` applies a partial edit (`null` clears a field; `line_items` replaces the whole list).
  - `Invoice.edit_fields` records a new `fields_edited` audit event with the before and after value of each changed field. It is only allowed in `needs_review` and only for a `user`; an edit that changes nothing records nothing.
  - Approval requires the key fields: vendor name, invoice number, issue date, currency and total.
  - `Invoice.version` is the number of audit events, for optimistic concurrency.
- **Service:** `ReviewService` with `edit`, `approve` and `reject`. Each takes the `version` the reviewer saw and refuses if the invoice has changed since, so nobody approves or overwrites something they have not seen.
- **API** (the acting user comes from `X-User`):
  - `PATCH /invoices/{id}/fields` with body `{version, fields}`
  - `POST /invoices/{id}/approve` with body `{version}`
  - `POST /invoices/{id}/reject` with body `{version, reason}`
  - Responses: 200 with the invoice; 404 for an unknown id; 409 for a stale version or a wrong status; 422 with `{"message", "errors": [...]}` for invalid values, missing approval fields or a missing reason.
  - Invoice responses gain `version`.
- **Persistence:** migration 0003 adds `fields_edited` to the action check. Its downgrade refuses while such events exist.

Out of scope: exporting approved invoices (feat-010), the review UI (feat-009), authentication (non-goal).

## How I Will Verify

- [ ] Layer 1 (static): `npm run lint`, `npm run typecheck`, `npm run check-arch`
- [ ] Layer 2 (runtime): `npm run test`:
  - edits are allowed only in `needs_review` and only by a user; partial edits, clearing with `null`, and replacing line items work
  - before and after values are recorded; a no-op edit records nothing
  - invalid values are rejected with every error listed
  - approval needs the key fields; rejection needs a reason
  - a stale `version` is refused for edit, approve and reject
  - restore replays `fields_edited`
  - jsonb round trip; migration 0003 up and down, refusing to drop `fields_edited` events
  - API happy path upload, extract, edit, approve, with the full audit trail; every error status
- [ ] Layer 3 (system): `npm run check`, `npm run verify-feature -- feat-006`, plus a live run (upload, extract, edit, approve, and a reject path)

## What Success Looks Like

A reviewer can correct a field, approve, and read back an audit trail that says who changed what (with the old and new values) and who approved, and when. Approving with a stale version, approving an invoice with no total, or rejecting without a reason is refused with a clear message.

## Dependencies

- [x] Depends on: feat-002, feat-004, feat-005 (passing)
- [ ] Blocked by: none

## Risks

- The acting user is still a trusted `X-User` header (no authentication, a documented non-goal).
- Requiring key fields for approval is a new product rule, recorded in D-009.

## Commit Plan

One commit: domain, migration, service, API, tests, docs and harness state together.

---

_Signed off by: Claude (Opus 5.5) on 2026-10-13_
