# Progress Log

Session continuity source of truth for this project. Update at the end of each session with verified state, blockers, and next steps.

Keep the "Current Verified State" block current at all times; the session log below it is append-only.

## Current Verified State

- Project root: ai-invoice-intake (harness adopter repo, created with create-harness)
- Primary startup command: ./init.sh
- Primary verification command: npm run check
- Current active feature (or none): none (feat-001 to feat-003 passing; next: feat-004)
- Current blocker (or none): none (baseline green after harness-upgrade; see D-001)

## Session Log

<!-- Append one session entry per session. Example fields below. -->

### Session 001 — 2026-10-12

- Goal: scaffold the project with ai-harness-framework and plan the features.
- Completed: create-harness scaffold; project-specific README, docs/PRODUCT.md, docs/ARCHITECTURE.md (product section), docs/quality-document.md; 12-feature plan in feature_list.json; productRoots declared in the manifest; LICENSE holder and .gitignore updated.
- Verification run: npm run check-arch (all rules pass); npm run check (65 runner tests, 1-2 intermittent failures in harness-backup tests).
- Evidence captured: none yet (no feature activated).
- Commits: none yet (repo initialised on branch main, nothing committed).
- Files or artifacts updated: README.md, docs/*, feature_list.json, .harness/manifest.json, LICENSE, .gitignore, DECISIONS.md.
- Known risk or unresolved issue: none open. The backup-id collision (flaky harness-backup tests) was fixed upstream in ai-harness-framework (D-021, commit 53eaa48) and applied here with harness-upgrade; npm run check and check-arch pass. harness-upgrade also reset LICENSE (a CORE surface) to the framework's copyright line.
- Next best step: activate feat-001 (FastAPI service skeleton), fill a sprint contract, implement, then verify-feature.

### Session 002 — 2026-10-12

- Goal: feat-001, the FastAPI service skeleton, with the backend covered by the harness gates.
- Completed:
  - Sprint contract in `docs/sprints/feat-001.md`.
  - `backend/`: FastAPI app factory, `GET /health`, typed settings (`INVOICE_INTAKE_*`), layer packages (`api`, `services`, `domain`, `infrastructure`), 12 tests (health, settings, layers), ruff, mypy --strict.
  - `tools/py.mjs` launcher (interpreter lookup, `setup` command, missing-dependency hint) and `tools/skip.mjs`; root `lint`, `typecheck`, `test`, `build` scripts now also run the backend; `setup:backend` and `dev:backend` added (D-003).
  - `e2e` layer set to an explicit SKIP placeholder because the framework's adoption matrix breaks on a customised `package.json` (D-004).
  - README backend quick start, quality document, `productRoots` (`tools/`, `docs/sprints/`).
- Verification run: `npm run check` (all layers pass; e2e reports SKIP); fresh-clone path tested in a throwaway copy (`setup` then tests, ruff, mypy all pass).
- Evidence captured: `.harness/state/feat-001.json` (written by `npm run verify-feature -- feat-001`).
- Commits: none yet.
- Files or artifacts updated: backend/, tools/, package.json, README.md, DECISIONS.md, docs/quality-document.md, docs/sprints/feat-001.md, .harness/manifest.json, .gitignore, PROGRESS.md.
- Known risk or unresolved issue: layer 3b (e2e) is SKIP until feat-009/feat-011; docker is not available in the sandbox used so far, so the compose stack cannot be exercised there; mypy's cache needs a normal writable folder (it fails on the sandbox's mounted drive; set `MYPY_CACHE_DIR` there).
- Next best step: activate feat-002 (invoice domain model and state machine), sprint contract first.

### Session 003 — 2026-10-12

- Goal: take the upstream e2e fix (ai-harness-framework D-022) and confirm it in this repo.
- Completed: `harness-upgrade` applied (scripts/ refreshed; backup 2026-10-12T18-51-02-153Z); the adoption matrix now passes against this repo's customised `package.json` (all cells); D-004 follow-up updated.
- Verification run: `node scripts/adoption-matrix.mjs` (all cells pass); `npm run check` and `npm run check-arch`.
- Evidence captured: this entry.
- Commits: see git log.
- Files or artifacts updated: scripts/ (CORE, via upgrade), LICENSE (CORE, reset by upgrade to the framework's copyright line), DECISIONS.md, PROGRESS.md.
- Known risk or unresolved issue: the e2e layer is still the SKIP placeholder (by design, D-004).
- Next best step: feat-002 (invoice domain model and state machine), sprint contract first.

### Session 004 — 2026-10-12

- Goal: first run on the author's Windows machine, provider-by-config plan change, then feat-002 (invoice domain model and state machine) and feat-003 (synthetic invoice generator).
- Completed:
  - Windows baseline: `npm run setup:backend` and `npm run check` pass (Python 3.14 venv); the earlier mypy cache issue did not occur.
  - D-005: the extraction provider is chosen by `INVOICE_INTAKE_EXTRACTION_PROVIDER` through one factory (default `fake`); feat-005 declaration, ARCHITECTURE.md and README updated (commit f48a0b4).
  - feat-002: sprint contract `docs/sprints/feat-002.md`; domain package (`actors`, `status`, `audit`, `invoice`, `errors`) with the state machine, actor rules (only a user approves or rejects), required rejection reason, append-only audit trail, Decimal-only money, timezone-aware times.
  - feat-003: sprint contract `docs/sprints/feat-003.md`; generator in `backend/tools/samplegen/` (7 fictional vendors, 4 languages, 5 currencies, 3 layouts), `npm run samples`, strict ground-truth loader, 12 committed samples in `samples/invoices/` with `samples/README.md` and `samples/.gitattributes`; ReportLab 4.5.1 pinned (D-006). PDFs checked visually in the browser pane.
  - arch-007 in `.harness/arch-rules.json`: `backend/tools/check_domain_imports.py` fails on any domain import outside the standard library or the domain package; shown to fail on a planted `invoice_intake.config` import.
- Verification run: `npm run verify-feature -- feat-002` and `-- feat-003` (layers 1-3 pass, e2e SKIP placeholder); `npm run check-arch` (all 7 rules pass); 129 backend tests, ruff, mypy --strict on src, tests and tools.
- Evidence captured: `.harness/state/feat-002.json` and `.harness/state/feat-003.json` (written by verify-feature).
- Commits: f48a0b4 (D-005), 44a0fc1 (feat-002); feat-003 is the next commit.
- Files or artifacts updated: backend/src/invoice_intake/domain/, backend/tests/ (domain tests), backend/tools/, backend/pyproject.toml (pytest and mypy paths), .harness/arch-rules.json, docs/ARCHITECTURE.md, docs/quality-document.md, docs/sprints/feat-002.md, PROGRESS.md, session-handoff.md.
- Known risk or unresolved issue: the state set has no `failed` status; feat-007 (worker) must add it with its transitions. The `Invoice` entity can only be created as a new upload; feat-004 needs a way to rebuild one from stored events. Field edits and their audit actions belong to feat-006. The ground-truth helpers live in `backend/tools/samplegen/`; if the fake extraction provider (feat-005) needs them at runtime, move them into the app package. Upgrading ReportLab means regenerating the samples.
- Next best step: feat-004 (PostgreSQL persistence and upload API), sprint contract first; it needs Docker or a local PostgreSQL for integration tests.
