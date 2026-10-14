# Quality Document

Rate each module on a scale of A (excellent) / B (good) / C (acceptable) / D (needs work) / F (failing).

## Modules

| Module | Test Coverage | Type Safety | Documentation | Arch Compliance | Performance |
|---|---|---|---|---|---|
| harness scaffold | B | n/a | B | B | n/a |
| backend (skeleton: app, settings, health) | B | A | B | A | n/a |
| backend domain (invoice, state machine, audit) | A | A | B | A | n/a |
| sample generator (backend/tools/samplegen, samples/) | A | A | A | A | n/a |
| persistence and intake API (infrastructure, services, api) | A | A | B | A | B |
| AI extraction (domain contract, providers, service, extract API) | A | A | A | A | B |
| review and approval (field values, review service, review API) | A | A | A | A | A |
| background extraction (queue, runner, worker) | A | A | A | A | B |
| frontend (shell, review queue) | A | A | B | A | B |
| frontend review screen and e2e | A | A | A | A | B |
| export webhook (domain, service, sender, worker, API, UI) | A | A | A | A | B |
| packaging and CI (Compose, images, smoke test, workflow) | A | n/a | A | A | B |
| README and documentation tooling (screenshots, docs check) | A | n/a | A | A | n/a |

## Summary

- **Overall Quality Grade:** A- (all twelve planned features passing; backend complete through review with background extraction; dashboard has the queue and the review screen; end-to-end tests run the real stack; approved invoices are exported to a signed webhook; one-command Compose stack and CI on every push)
- **Blockers:** none
- **Areas requiring attention:** the OpenAI provider has never been called with a real key; there is no authentication (the acting user is a trusted header); the test suite needs Docker (PostgreSQL and Redis); see `feature_list.json`

## Notes

- Session 001 created the harness scaffold and the feature plan; no product code yet.
- Session 002 (feat-001) added the backend skeleton: 12 tests, ruff clean, mypy --strict clean. Coverage graded B (health and settings covered; nothing else exists yet).
- Session 004 (feat-002) added the invoice domain: every status pair tested (5 allowed, 31 forbidden, 10 wrong-actor cases), value validation, and arch-007 (domain imports only the standard library), shown to fail on a planted import. 104 backend tests. Coverage graded A for the domain; documentation B (docstrings and ARCHITECTURE.md, no separate domain guide).
- Session 004 (feat-003) added the synthetic invoice generator: 12 committed samples (3 layouts, 4 languages, 5 currencies), byte-identical reruns, strict ground-truth loader with 15 rejection cases, and a drift test against the committed files. 129 backend tests. Documentation A (samples/README.md documents the format; D-006 the approach).
- Session 004 (feat-004) added PostgreSQL persistence (SQLAlchemy 2, Alembic, append-only audit trigger) and the intake API. 212 backend tests, 36 of them against a throwaway PostgreSQL container: migrations up/down/up, models match the schema, round trips in every status, stale saves refused, the database refusing UPDATE/DELETE on audit events, and the API end to end with a committed sample. Also checked live (server plus dev database, real upload and download). Performance B: lists load events per page (two extra queries), fine at this scale. Documentation B: README and ARCHITECTURE.md cover setup and design; no API guide beyond OpenAPI.
- Session 004 (feat-005) added AI extraction: one output contract and validator in the domain, `fake` and `openai` providers behind a startup-time factory, extraction audit events with JSON details (migration 0002), and `POST /invoices/{id}/extract`. 303 backend tests: every committed sample extracted with the fake provider matches its ground truth; 23 kinds of invalid output rejected and recorded; the OpenAI request shape and error mapping checked with a stub (no network). Checked live: sample extracted to `needs_review` with confidence, 409 on repeat, startup refused for `openai` without a key. Performance B: the fake reads all samples at startup (12 files) and documents travel inline as base64 to OpenAI (fine up to the 10 MB upload limit).
- Session 005 (feat-006) added human review: shared JSON field parsing (`domain/field_values.py`), audited edits with old/new values, approval requiring key fields, optimistic `version` checks, and `PATCH /fields`, `POST /approve`, `POST /reject`. 371 backend tests, including every review error status against PostgreSQL and migration 0003 up/down. Checked live: upload, extract, edit, stale approve (409), approve, reject without reason (422), approve without total (422), reject.
- Session 005 (feat-007) moved extraction to a worker: `failed` status and transitions, the runner's three short transactions, a reliable Redis queue (ready list, delayed set, per-worker processing list), enqueue after commit plus a sweep, and migration 0004. 426 backend tests, including the queue against real Redis and the worker loop end to end (upload returns at once, retries, `failed`, retry on request, sweep), repeated three times without flakiness. The worker test found a real race (a read pairing an old invoice row with newer events), fixed by loading reads in one statement. Performance B: reads join line items and events (a small cartesian product per invoice).
- Session 005 (feat-008) added the dashboard's first screen: the review queue (status overview and filters, drop-zone upload, live list with animated statuses, loading, empty, stale and error states, theme and "acting as"), the stats endpoint, and the generated API client. 25 frontend tests against an in-memory API plus a schema drift check; 432 backend tests. Checked live in light and dark mode at phone and tablet widths, including the queued-to-needs-review transition without a reload, the API going down and coming back, and filters in the URL. Documentation B (README, ARCHITECTURE.md, D-012; no component docs yet). Performance B: about 209 KB gzipped of JavaScript, split into cached library chunks; polling every 15 s when idle.
- Session 005 (feat-009) added the review screen: the pdf.js viewer with click-to-highlight, the field editor with confidence bands, a totals check in exact cents, decisions with version checks, a conflict banner, the audit timeline and keyboard shortcuts, plus real end-to-end tests (D-013). 55 frontend tests (pure logic and component tests against an in-memory API with the real rules); the Playwright run passes in about 5 s on the real stack and leaves no containers or processes behind. Checked at full resolution in light and dark mode: the total `3 627,23` is highlighted in the French sample. Performance B: pdf.js is lazy-loaded in its own chunk.
- Session 006 (feat-010) added export: a signed webhook delivery per approval from the same worker (queue jobs gained a `kind`), retries with the failures in the audit trail, an export state derived from the trail, `POST /invoices/{id}/export`, `export_configured` in health, and migration 0005 (D-014). 463 backend tests, including the sender against a real local HTTP server (signature, non-2xx, timeout, unreachable), "nothing exported before approval" for every other status, and the worker delivering to a local server on PostgreSQL and Redis (with 503s retried); 61 frontend tests; the Playwright run now checks exactly one signed delivery and the "Exported" state. The e2e found a real harness bug: Playwright ran through `spawnSync`, which blocked the in-process receiver. Performance B: one HTTP call per approval, short transactions around it.
- Session 007 (feat-011) added packaging and CI (D-015). It covers the Compose stack (migrate, api, worker, seed, demo accounting receiver, nginx web), the backend and web images, `npm run compose:smoke`, and a GitHub Actions workflow running `npm run check`, `check-arch` and the smoke test. The run has 470 backend tests: the new ones cover the demo receiver against the real webhook sender (valid, wrong and missing signatures) and the seed on PostgreSQL (12 uploads, then none). The non-Docker backend tests also pass on Linux in a `python:3.14-slim` container. The manual check in a browser found that nginx served pdf.js's `.mjs` worker as `application/octet-stream`, so the PDF could not render. That is fixed, and the smoke test now checks every built asset's content type. Performance B: the backend image is about 350 MB; the stack stops in about 3 s.
- Session 008 (feat-012) rewrote the README product-first, with a hero screenshot, "Run it in five minutes", a walkthrough, Mermaid component and lifecycle diagrams, and a decisions table linking each entry (D-016). New tools: `npm run screenshots` regenerates the four images from the real Compose stack (fixed data steps and locale, light and dark), and `tools/check-docs.mjs` runs in lint (shown to fail on a missing image, a bad anchor and an unknown script). The five-minute start was measured from a fresh clone of the public repository with an empty build cache. The first attempt failed once in the dependency layer and its pip output was lost; the next runs took 205 s and 299 s (with lint running on the same machine).

---

_Update this document at session close for modules touched in the session._
