# Sprint Contract

**Feature ID:** feat-014
**Feature Name:** Backend dependency locks
**Date:** 2026-10-14
**Estimated Duration:** 1 session

## What I Will Build

The backend's Python packages are installed from minimum versions (`fastapi>=0.121` and so on), so a new release can break a fresh `docker compose up --build`, `npm run setup:backend` or a CI run even though nothing in the project changed. The frontend already installs from `package-lock.json` with `npm ci`. This feature gives the backend the same guarantee.

- **Two lock files** in `repositories/backend/`, generated with `uv pip compile`:
  - `requirements.lock`: the runtime dependencies, for the Docker image.
  - `requirements-dev.lock`: runtime plus the `dev` extra, for `npm run setup:backend` and CI.

  Both are:
  - **Universal:** resolved once for every platform and Python version the project supports (3.10 and up), with environment markers. For example, `uvloop` comes with `uvicorn[standard]` on Linux only, so a lock resolved on Windows alone would miss it.
  - **Hashed:** every package has its SHA-256 hashes, and installs run with `--require-hashes`, so a changed or substituted file on the package index is refused.
- **`npm run lock:backend`** regenerates both. `uv` becomes a development dependency, and installing still needs only `pip`.
- **Installs from the locks:**
  - The `Dockerfile` installs `requirements.lock`, then the project with `--no-deps`. This replaces the stub-package trick and keeps the dependency layer cached.
  - `tools/py.mjs setup` installs `requirements-dev.lock`, then the project in editable mode with `--no-deps`.
  - CI caches pip by `requirements-dev.lock`.
- **A drift test:**
  - every dependency in `pyproject.toml` is pinned (`==`) in the matching lock, with hashes
  - every lock line is an exact pin
  - the locks say how they were generated
  
  Changing `pyproject.toml` without running `npm run lock:backend` fails the tests.

Out of scope: upgrading any package (the locks pin what resolves today), Dependabot or Renovate.

## How I Will Verify

- [x] Layer 1 (static): `npm run lint`, `npm run typecheck`, `npm run check-arch`
- [x] Layer 2 (runtime): `npm run test`, including the drift test (shown to fail on a planted mismatch)
- [x] Layer 3a: `npm run verify-all`
- [x] Layer 3 (system): `npm run check` and `npm run verify-feature -- feat-014`, plus:
  - a fresh `npm run setup:backend` (the venv deleted first) on Windows
  - `docker compose build --no-cache`, an install on Linux from the universal lock
  - `npm run compose:smoke`
- [ ] After the push (when the author agrees to commit): CI green, an install on Linux from the dev lock

## What Success Looks Like

Installing the backend gives the same package versions on every machine and every day, until someone runs `npm run lock:backend` and commits the result.

## Dependencies

- [x] Depends on: feat-013
- [ ] Blocked by: none

## Risks

- Universal resolution across Python 3.10–3.14: a package that dropped 3.10 gets a marker split. uv handles that, and the drift test checks the result.
- `pip --require-hashes` rejects an unhashed requirement. Installing the project itself therefore stays a separate `--no-deps` step.

## Commit Plan

One commit, after the author agrees (feat-015 follows in its own commit).

---

_Signed off by: Claude (Opus 5.5) on 2026-10-14_
