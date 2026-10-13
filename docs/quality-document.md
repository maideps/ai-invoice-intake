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
| frontend | not started | not started | not started | not started | not started |

## Summary

- **Overall Quality Grade:** B (backend complete through review: intake, extraction, edits and decisions; no worker, export or UI yet)
- **Blockers:** none
- **Areas requiring attention:** frontend not started; no worker or export yet; extraction runs only on request; the test suite needs Docker; see `feature_list.json`

## Notes

- Session 001 created the harness scaffold and the feature plan; no product code yet.
- Session 002 (feat-001) added the backend skeleton: 12 tests, ruff clean, mypy --strict clean. Coverage graded B (health and settings covered; nothing else exists yet).
- Session 004 (feat-002) added the invoice domain: every status pair tested (5 allowed, 31 forbidden, 10 wrong-actor cases), value validation, and arch-007 (domain imports only the standard library), shown to fail on a planted import. 104 backend tests. Coverage graded A for the domain; documentation B (docstrings and ARCHITECTURE.md, no separate domain guide).
- Session 004 (feat-003) added the synthetic invoice generator: 12 committed samples (3 layouts, 4 languages, 5 currencies), byte-identical reruns, strict ground-truth loader with 15 rejection cases, and a drift test against the committed files. 129 backend tests. Documentation A (samples/README.md documents the format; D-006 the approach).
- Session 004 (feat-004) added PostgreSQL persistence (SQLAlchemy 2, Alembic, append-only audit trigger) and the intake API. 212 backend tests, 36 of them against a throwaway PostgreSQL container: migrations up/down/up, models match the schema, round trips in every status, stale saves refused, the database refusing UPDATE/DELETE on audit events, and the API end to end with a committed sample. Also checked live (server plus dev database, real upload and download). Performance B: lists load events per page (two extra queries), fine at this scale. Documentation B: README and ARCHITECTURE.md cover setup and design; no API guide beyond OpenAPI.
- Session 004 (feat-005) added AI extraction: one output contract and validator in the domain, `fake` and `openai` providers behind a startup-time factory, extraction audit events with JSON details (migration 0002), and `POST /invoices/{id}/extract`. 303 backend tests: every committed sample extracted with the fake provider matches its ground truth; 23 kinds of invalid output rejected and recorded; the OpenAI request shape and error mapping checked with a stub (no network). Checked live: sample extracted to `needs_review` with confidence, 409 on repeat, startup refused for `openai` without a key. Performance B: the fake reads all samples at startup (12 files) and documents travel inline as base64 to OpenAI (fine up to the 10 MB upload limit).
- Session 005 (feat-006) added human review: shared JSON field parsing (`domain/field_values.py`), audited edits with old/new values, approval requiring key fields, optimistic `version` checks, and `PATCH /fields`, `POST /approve`, `POST /reject`. 371 backend tests, including every review error status against PostgreSQL and migration 0003 up/down. Checked live: upload, extract, edit, stale approve (409), approve, reject without reason (422), approve without total (422), reject.

---

_Update this document at session close for modules touched in the session._
