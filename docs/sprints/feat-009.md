# Sprint Contract

**Feature ID:** feat-009
**Feature Name:** Review detail UI
**Date:** 2026-10-13
**Estimated Duration:** 1 session

## What I Will Build

The review screen: the original document beside the extracted fields, so a person can check, correct, approve or reject an invoice quickly and with confidence. It also brings the first real end-to-end tests, replacing the SKIP placeholder (D-004).

- **Document viewer:**
  - PDFs render with pdf.js (react-pdf) including the text layer; images render directly.
  - Zoom, page navigation, and a link to the original file.
  - Loaded only on this screen, so the queue stays light.
- **Click a field, see it in the document:**
  - Focusing a field highlights its value in the PDF text layer and scrolls to it.
  - Local formats are tried too: `3 627,23`, `3.627,23`, `14/02/2026`, `14.02.2026`, `February 14, 2026`.
  - Best effort. Scanned images have no text layer, and the screen says so.
- **Field editor:**
  - All header fields and the line items (add, edit, remove rows).
  - Confidence per field: high, medium or low, with low tinted amber. A "Next low-confidence field" button walks through them.
  - Saving sends only the changed fields with the invoice `version`; Reset discards changes.
  - Server validation errors show under the field they concern.
  - Read-only unless the invoice is in `needs_review`.
- **Totals check:**
  - Do the lines add up to the subtotal, and the subtotal plus tax to the total?
  - Is each quantity × unit price equal to its amount?
  - Computed in exact cents, with half-up rounding as invoices use. A warning, never a block (D-009).
- **Decisions:**
  - Approve; Reject with a required reason.
  - The approval minimum is shown before you click.
  - "Retry extraction" for `failed` invoices.
- **Conflicts:** a 409 shows a banner ("this invoice changed since you opened it") with a Reload button, instead of an error.
- **Audit timeline:**
  - Every event with who acted (person, AI or system).
  - Edits show old → new values; AI output shows the model; rejected output shows why.
- **Keyboard:**
  - `J` / `K` for the next and previous invoice waiting for review.
  - `A` approve, `R` reject, `E` edit (first field), `S` save, `?` shortcut help.
  - Inactive while typing.
- **End-to-end tests (Playwright)** with `tools/e2e.mjs` (D-013):
  - Starts throwaway PostgreSQL and Redis containers, runs migrations, and starts the API, worker and Vite on spare ports.
  - Runs the browser tests, then tears everything down even on failure.
  - `npm run e2e` (and so `npm run check`) uses it instead of the SKIP.
  - Scenario: upload a sample in the UI, watch it reach review, open it, see the PDF, click the total and see it highlighted, correct a field, save, approve, and find both decisions in the timeline.

Out of scope: export (feat-010), authentication (non-goal), bounding-box highlights (the extraction does not return positions).

## How I Will Verify

- [ ] Layer 1 (static): `npm run lint`, `npm run typecheck`
- [ ] Layer 2 (runtime): `npm run test`:
  - unit tests for the highlight candidates and marking, and for the totals check (cents, rounding, missing values)
  - component tests against the in-memory API:
    - fields and confidence shown
    - edit and save sends only the changed fields with the version
    - a server error appears under its field
    - approve, approve blocked with the missing fields, reject with a reason
    - a 409 conflict banner with reload
    - read-only outside review
    - retry for failed invoices
    - keyboard shortcuts
    - the timeline renders each kind of event
- [ ] Layer 3 (system): `npm run e2e` approves an invoice through the UI on the real stack; `npm run check`, `npm run check-arch`, `npm run verify-feature -- feat-009`; screenshots of the review screen in light and dark mode

## What Success Looks Like

Open a sample in review. The PDF is on the left and the fields on the right, with low-confidence ones in amber. Clicking "Total" highlights `3 627,23 €` in the document. Changing a value and saving adds an "alice set total 3672.23 → 3627.23" entry to the timeline. Pressing `A` approves. The end-to-end test does the same in a real browser.

## Dependencies

- [x] Depends on: feat-006 (review API), feat-008 (dashboard)
- [ ] Blocked by: none

## Risks

- pdf.js is large; it is split into its own chunk and loaded only on the review screen.
- Highlighting matches text, not positions: a value that appears twice is highlighted twice; values the model normalised in an unexpected way may not be found.
- The end-to-end run needs Docker and Playwright's Chromium (installed by `npm run setup:frontend`); it fails with a clear message when either is missing.

## Commit Plan

One commit: review screen, highlight and totals logic, API mutations, e2e runner and tests, docs and harness state together.

---

_Signed off by: Claude (Opus 5.5) on 2026-10-13_
