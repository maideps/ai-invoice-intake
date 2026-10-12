# Sprint Contract

**Feature ID:** feat-001
**Feature Name:** FastAPI service skeleton
**Date:** 2026-10-12
**Estimated Duration:** 1 session

## What I Will Build

A FastAPI application in `backend/` with the four layer packages from `docs/ARCHITECTURE.md` (`api`, `services`, `domain`, `infrastructure`), a `GET /health` endpoint, typed settings read from environment variables, and the backend's lint, typecheck, test and build commands wired into the root npm scripts so the harness gates cover the backend.

## How I Will Verify

- [ ] Layer 1 (static): `npm run lint` runs the harness lint plus `ruff check` and `ruff format --check`; `npm run typecheck` runs `mypy --strict` on the backend
- [ ] Layer 2 (runtime): `npm run test` runs the harness tests plus backend `pytest` (health endpoint, settings defaults, env override, invalid value rejected, layer packages importable)
- [ ] Layer 3 (system): `npm run check` passes end to end; `npm run verify-feature -- feat-001` passes

## What Success Looks Like

`GET /health` returns 200 with `{"status": "ok", "version": ..., "environment": ...}` in a test; settings come from `INVOICE_INTAKE_*` environment variables and reject invalid values; a fresh clone can run `npm run setup:backend` then `npm run check`; the harness gates cover the backend (not just the framework tests).

## Dependencies

- [x] Depends on: none
- [ ] Blocked by: none

## Risks

- The harness runs product layers from root `package.json` scripts; backend commands must work on Windows and Linux (handled by a small Node launcher, `tools/py.mjs`).
- Backend dependencies must be installed before the gates can run; the launcher prints a clear hint when they are missing.

## Commit Plan

One commit: backend skeleton, launcher, npm script wiring, docs and harness state together.

---

_Signed off by: Claude (Sonnet 5.5) on 2026-10-12_
