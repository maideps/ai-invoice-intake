# Session Handoff

Fill this at session end for large sessions; keep it current otherwise.

## Current Objective

- Goal: build AI Invoice Intake, a portfolio project (FastAPI + PostgreSQL + Redis worker + React/TypeScript, OpenAI extraction behind an interface, human approval before export, all data synthetic) using ai-harness-framework, one feature at a time.
- Current status: feat-001 (FastAPI service skeleton) is `passing`. Nothing else is started. feat-002 (invoice domain model and state machine) is next.
- Branch / commit: `main` at `191efcb`. Local repository only; there is no GitHub remote yet.

## Completed This Session

- [x] Scaffolded the project with `create-harness`; filled README, `docs/PRODUCT.md`, `docs/ARCHITECTURE.md`, quality document; wrote the 12-feature plan in `feature_list.json`.
- [x] feat-001: FastAPI app factory, `GET /health`, typed `INVOICE_INTAKE_*` settings, layer packages (`api`, `services`, `domain`, `infrastructure`), 12 tests, ruff, mypy --strict.
- [x] Wired the backend into the harness gates through `tools/py.mjs` (D-003); `e2e` is an explicit SKIP placeholder (D-004).
- [x] Fixed two bugs upstream in `ai-harness-framework` and applied them here with `harness-upgrade`: backup-id collisions (D-021, commit 53eaa48) and adoption-matrix fixtures breaking on customised scripts (D-022, commit 79bd6c4).

## Verification Evidence

| Check | Command | Result | Notes |
|---|---|---|---|
| Full verification | `npm run check` | pass | e2e layer reports SKIP (placeholder) |
| Architecture rules | `npm run check-arch` | pass | all rules |
| Feature gate | `npm run verify-feature -- feat-001` | pass | evidence in `.harness/state/feat-001.json` |
| Harness matrix | `node scripts/adoption-matrix.mjs` | pass | all cells, with this repo's customised `package.json` |
| Fresh-clone setup | `npm run setup:backend` then tests, ruff, mypy | pass | tested in a throwaway copy |

## Files Changed

- `backend/` (new): app, tests, `pyproject.toml`, `.env.example`
- `tools/py.mjs`, `tools/skip.mjs` (new); `package.json` scripts (`lint`, `typecheck`, `test`, `build`, `e2e`, `setup:backend`, `dev:backend`)
- `docs/`, `README.md`, `DECISIONS.md` (D-001 to D-004), `PROGRESS.md`, `feature_list.json`, `.harness/manifest.json` (`productRoots`)
- `scripts/` and `LICENSE` refreshed by `harness-upgrade` (CORE; do not edit by hand)

## Decisions Made

- D-002: stack and scope (invoices, React, synthetic data, AI behind an interface, human approval required).
- D-003: backend tooling runs through the `tools/py.mjs` launcher wired into the harness scripts.
- D-004: `e2e` stays a SKIP placeholder until real end-to-end tests exist (planned feat-009 / feat-011).

## Blockers / Risks

- On the author's Windows machine nothing has been run yet: run `npm run setup:backend` then `npm run check` first and fix anything platform-specific before starting feat-002.
- `LICENSE` is a CORE file, so `harness-upgrade` resets it to the framework's copyright line ("AI Harness Framework contributors"). Decide whether to keep it or set the author's name after each upgrade.
- The e2e layer is not verified; do not treat a green `npm run check` as end-to-end evidence yet.
- Docker was not available where this was built, so `docker compose` (feat-011) is untested.
- In the earlier sandbox, mypy's cache failed on a mounted drive; if mypy errors with a cache or sqlite message, set `MYPY_CACHE_DIR` to a normal local folder.

## Next Session Startup

1. Read `AGENTS.md`.
2. Read `feature_list.json` and `PROGRESS.md`.
3. Review this handoff.
4. Run `npm run setup:backend`, then the standard verification command (`npm run check`) before editing.

## Recommended Next Step

- Run the startup steps, then start feat-002: write the sprint contract in `docs/sprints/feat-002.md` (copy the shape of `feat-001.md`), set `.harness/state/feat-002.json` to `{"state": "active", "evidence": ""}`, implement the invoice, line item and audit event entities and the state machine in `backend/src/invoice_intake/domain/` with no imports from other layers, then run `npm run verify-feature -- feat-002`.
- Optional: create a GitHub repo for the project and push (`git remote add origin ...`), then wire CI in feat-011.
