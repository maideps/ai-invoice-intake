# Repositories

Each subdirectory under `repositories/` is one execution domain with its own `scripts/verify`:

```
repositories/
  <name>/
    scripts/
      verify        # the repository's verification entrypoint (Node ≥ 18)
    src/            # the repository's own code (product-owned)
```

Rules:

- Every repository MUST have a `scripts/verify` that exits non-zero on failure — `verify-all` treats a missing verify script as SKIP, not PASS.
- A repository's verify script runs its own checks (harness check, tests, build) and prints its own PASS/SKIP/FAIL lines.
- The root `scripts/verify-all` (activated from `templates/multi-repo/verify-all`) runs every repository's verify and aggregates the results.

## Existing Repositories

- `backend/` — the FastAPI service, the worker, the migrations and their tools (Python). `scripts/verify`: ruff, ruff format, mypy --strict, pytest (needs Docker), compile check. Set up with `npm run setup:backend` from the root.
- `frontend/` — the React review dashboard (TypeScript). `scripts/verify`: ESLint, `tsc`, Vitest, production build. Set up with `npm run setup:frontend` from the root. The Playwright end-to-end tests need the whole stack and run from the root (`npm run e2e`).

The two share one contract, `contracts/openapi.json` (see `contracts/README.md`).
