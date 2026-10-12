# Progress Log

Session continuity source of truth for this project. Update at the end of each session with verified state, blockers, and next steps.

Keep the "Current Verified State" block current at all times; the session log below it is append-only.

## Current Verified State

- Project root: ai-invoice-intake (harness adopter repo, created with create-harness)
- Primary startup command: ./init.sh
- Primary verification command: npm run check
- Current active feature (or none): none (feat-001 passing; next: feat-002)
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
