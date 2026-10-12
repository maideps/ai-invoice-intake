# Sprint Contract

**Feature ID:** feat-002
**Feature Name:** Invoice domain model and state machine
**Date:** 2026-10-12
**Estimated Duration:** 1 session

## What I Will Build

The invoice domain in `backend/src/invoice_intake/domain/`, using only the standard library:

- `InvoiceStatus` (`uploaded`, `extracting`, `needs_review`, `approved`, `rejected`, `exported`) and a transition table that also states which kind of actor may make each move. Approve and reject require a human (`user`) actor, which encodes the product rule that nothing is exported without explicit human approval. `rejected` and `exported` are terminal.
- `Invoice` entity: identity, file name, upload time, status, extracted header fields (vendor, number, dates, currency, totals) and line items. Status changes only through `Invoice.transition_to`, which checks the table, requires a reason for rejection, and appends an audit event.
- `LineItem` value object: description, quantity, unit price and amount as `Decimal` (floats rejected).
- `AuditEvent` value object (append-only, numbered from 1, timezone-aware timestamps) and `Actor` (`system`, `ai` or `user` plus a name). Creating an invoice records the first event.
- Domain errors: `InvalidTransitionError`, `ActorNotPermittedError`, `InvalidInvoiceDataError`.
- Architecture rule `arch-007`: a checker (`backend/tools/check_domain_imports.py`) fails if any domain module imports something other than the standard library or the domain package itself.

Out of scope: persistence (feat-004), the extraction result and confidence model (feat-005), field edits and their audit events (feat-006), and a `failed` status for extraction errors (feat-007 adds it with the worker).

## How I Will Verify

- [ ] Layer 1 (static): `npm run lint` (ruff, harness lint) and `npm run typecheck` (mypy --strict, now also covering `backend/tools/`)
- [ ] Layer 2 (runtime): `npm run test`: every allowed transition succeeds and is audited; every forbidden pair (all 36 status pairs minus the 5 allowed) raises and leaves the invoice unchanged; wrong actor kinds are refused; line item and invoice validation; the import checker passes on the real domain and fails on a planted bad import
- [ ] Layer 3 (system): `npm run check` and `npm run check-arch` (including arch-007) pass; `npm run verify-feature -- feat-002` passes

## What Success Looks Like

The full lifecycle `uploaded -> extracting -> needs_review -> approved -> exported` runs in a test and leaves five ordered audit events; no other status change is possible; only a user can approve or reject; the domain package imports nothing outside the standard library, and `check-arch` proves it.

## Dependencies

- [x] Depends on: feat-001 (passing)
- [ ] Blocked by: none

## Risks

- The state set is fixed by the feature declaration; the worker (feat-007) will need a `failed` status and the transitions into and out of it.
- Domain rules that later features rely on (who may approve, rejection needs a reason) are decided here; feat-006 enforces them through the API rather than re-implementing them.

## Commit Plan

One commit: domain code, tests, import checker, arch rule, docs and harness state together.

---

_Signed off by: Claude (Opus 5.5) on 2026-10-12_
