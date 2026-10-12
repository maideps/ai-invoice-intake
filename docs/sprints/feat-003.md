# Sprint Contract

**Feature ID:** feat-003
**Feature Name:** Synthetic invoice generator
**Date:** 2026-10-12
**Estimated Duration:** 1 session

## What I Will Build

A seeded generator that writes synthetic invoices to `samples/invoices/`: for each invoice a PDF and a ground-truth JSON file holding the values an extractor should find.

- Code in `backend/tools/samplegen/` (catalog, invoice builder, PDF layouts, ground-truth format) with a thin entry point `backend/tools/generate_samples.py` and an `npm run samples` script. It lives under `backend/` so ruff, mypy --strict and pytest cover it.
- Seven fictional vendors in five currencies (USD, EUR, GBP, CAD, NOK) and four languages (English, German, French, Norwegian), each with its own date format, number format, tax label and invoice-number pattern; Letter or A4 paper.
- Three layouts: `classic` (two-column header, ruled table), `banner` (coloured header band, shaded rows, boxed totals) and `compact` (monospace, single column, items as text lines).
- Ground truth built from the domain's `InvoiceFields` and `LineItem`, so every sample is valid domain data. Money as decimal strings, dates as ISO strings; arithmetic is consistent (line amount = quantity x unit price, subtotal = sum of lines, total = subtotal + tax).
- A strict ground-truth loader that rejects missing or unknown keys, wrong types, non-decimal money and bad dates.
- Reproducibility: one `random.Random` per invoice seeded from `(seed, index)`, fixed date range, and PDFs written with ReportLab's invariant mode and no page compression (so output does not depend on the platform's zlib). ReportLab is pinned exactly.
- The default set (seed 42, 12 invoices) is committed, with `samples/.gitattributes` keeping the files byte-exact on every OS. Every PDF carries a "synthetic sample" footer.

Out of scope: scanned or image invoices, multi-page invoices, and noise or OCR artefacts. The extraction result format with confidence belongs to feat-005.

## How I Will Verify

- [ ] Layer 1 (static): `npm run lint` and `npm run typecheck` (mypy --strict over `backend/tools/` too)
- [ ] Layer 2 (runtime): `npm run test`: two runs with the same seed give byte-identical files; a different seed gives different invoices; invoice N is the same whatever the count; every ground-truth file passes the strict loader and its arithmetic holds; every PDF is a PDF and contains its invoice number and the synthetic marker; the default set covers all layouts, vendors and five currencies; the loader rejects malformed documents; the committed samples match a fresh run
- [ ] Layer 3 (system): `npm run check` and `npm run check-arch` pass; `npm run verify-feature -- feat-003` passes

## What Success Looks Like

`npm run samples` writes 12 PDF and JSON pairs to `samples/invoices/`; running it again changes nothing in git; the PDFs open and look like plausible invoices in three distinct styles and four languages.

## Dependencies

- [x] Depends on: feat-002 (passing)
- [ ] Blocked by: none

## Risks

- Byte-exact PDFs depend on the ReportLab version, so it is pinned; an upgrade means regenerating the samples (the drift test says so).
- The fake extraction provider (feat-005) will read this ground truth; if it needs the JSON helpers inside the app package, they move there in feat-005.

## Commit Plan

One commit: generator, tests, committed samples, npm script, docs and harness state together.

---

_Signed off by: Claude (Opus 5.5) on 2026-10-12_
