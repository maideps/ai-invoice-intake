# Sprint Contract

**Feature ID:** feat-013
**Feature Name:** Repositories layout
**Date:** 2026-10-13
**Estimated Duration:** 1 session

## What I Will Build

The author asked to move the frontend and the backend under `repositories/`, as folders in this same git repository, using the harness's multi-repo component. Each part becomes an execution domain with its own verification, and the root stays the control plane.

- **Move** (with `git mv`, so file history follows):
  - `backend/` to `repositories/backend/`
  - `frontend/` to `repositories/frontend/`
  - the OpenAPI document from `frontend/src/api/openapi.json` to `contracts/openapi.json`
  
  The template's `repositories/example` is removed.
- **Contract:** `contracts/openapi.json`, owned by the backend (`npm run api:types` writes it) and consumed by the frontend (types generated from it). `contracts/README.md` records the owner, the consumer and the rule: change it only together with both sides. The drift tests on both sides read it from there.
- **Repository gates:** `repositories/backend/scripts/verify` and `repositories/frontend/scripts/verify`, which `npm run verify-all` runs.
  - Backend: ruff, ruff format, mypy --strict, pytest (with Docker), compile check.
  - Frontend: ESLint, `tsc`, Vitest, `vite build`.
  
  Each finds its own toolchain (the backend's `.venv`, the frontend's `node_modules`) and says how to set it up when it is missing. The `verify` file only loads `verify.mjs`, so it works whatever module type Node assumes for it.
- **Paths updated everywhere:**
  - the launchers (`tools/py.mjs`, `tools/web.mjs`), `tools/e2e.mjs`, `tools/screenshots.mjs`
  - `docker-compose.yml` and the Dockerfile notes, the CI workflow (caches, working directory, artifacts)
  - the architecture rules' texts and `productRoots` in the manifest
  - in code: the repository root in settings and tests, the sample paths, the OpenAPI export target, the e2e sample
  - `.env.example`, README, ARCHITECTURE, samples README, `repositories/README.md`
  
  Past sprint contracts, decisions and progress entries stay as written (they record history).
- **Local toolchains:**
  - Python: the backend's `.venv` is recreated with `npm run setup:backend`, because an editable install records its path.
  - Node: the frontend's `node_modules` moves with it.

Out of scope: separate git repositories or submodules (the author chose folders in one repository), splitting CI per repository.

## How I Will Verify

- [x] Layer 1 (static): `npm run lint` (with the docs check), `npm run typecheck`, `npm run check-arch` (the layer rules now read `repositories/backend`)
- [x] Layer 2 (runtime): `npm run test`; both drift tests against `contracts/openapi.json`
- [x] Layer 3a: `npm run verify-all` runs both repositories and passes, with no SKIP
- [x] Layer 3 (system): `npm run check` and `npm run verify-feature -- feat-013`, plus:
  - `npm run compose:smoke`
  - no tracked file outside history documents mentions the old `backend/` or `frontend/` root paths
- [x] After the push (when the author agrees to commit): CI green (run 38500026949)

## What Success Looks Like

`repositories/` holds `backend` and `frontend`, each verifiable alone with `node repositories/<name>/scripts/verify`. `contracts/openapi.json` is the one API contract. Every root command works as before: `docker compose up --build`, `npm run check`, `npm run dev:*`.

## Dependencies

- [x] Depends on: feat-012
- [ ] Blocked by: none

## Risks

- Missing a path reference. Mitigation: search the tracked files for the old paths after the move, and run every gate (check, verify-all, smoke, CI).
- Git history: `git mv` keeps it, and `git log --follow` works per file.

## Commit Plan

One commit after the author agrees: move, path updates, repository gates, contract, docs and harness state.

---

_Signed off by: Claude (Opus 5.5) on 2026-10-13_
