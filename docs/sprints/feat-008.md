# Sprint Contract

**Feature ID:** feat-008
**Feature Name:** Review queue UI
**Date:** 2026-10-13
**Estimated Duration:** 1 session

## What I Will Build

The first screen of the React + TypeScript dashboard: the review queue, in a calm, modern style (neutral greys, one accent colour, dark mode that follows the system setting), plus the frontend's place in the harness gates.

- **Frontend scaffold (`frontend/`)** (D-012):
  - Vite 7, React 19, TypeScript (strict), Tailwind CSS v4.
  - Small component primitives in the shadcn/ui style (Radix plus class-variance-authority), lucide icons, Motion for animation, sonner for toasts.
  - TanStack Query for server state; React Router.
  - The dev server proxies `/api` to the FastAPI backend, so no CORS setup is needed.
- **Typed API client:** `backend/tools/export_openapi.py` writes `frontend/src/api/openapi.json`, and `openapi-typescript` turns it into `schema.d.ts`; `openapi-fetch` uses those types. Two drift tests fail if either file falls behind (one in the backend, one in the frontend).
- **Queue screen:**
  - **Status strip:** a count per status that doubles as the filter, synced with the URL.
  - **Upload:** a drop zone (drag and drop or click, several files at once). New invoices appear at the top and visibly move through uploaded, extracting and needs review while the worker runs; the list refreshes every 2 seconds while anything is in progress.
  - **List:** file name, vendor, total formatted in its currency, an animated status badge, and how long ago it was uploaded, with pages of 20.
  - **States:** loading skeletons; an empty state that invites an upload (or offers to clear the filter); an error state with retry when the API is unreachable; server upload errors (400, 413, 415) shown in toasts with the server's message.
  - **"Acting as" picker:** sets the `X-User` header and is remembered in the browser.
  - **Theme toggle:** system, light or dark.
  - A placeholder detail route for each invoice; the full review screen is feat-009.
- **Backend:** `GET /invoices/stats` returns `{total, by_status}` with every status listed (zero when empty), from one grouped query.
- **Harness wiring:**
  - `tools/web.mjs` runs frontend commands and says clearly when `npm run setup:frontend` is needed or Node is too old.
  - The root `lint`, `typecheck`, `test` and `build` scripts also run the frontend (ESLint, `tsc`, Vitest, `vite build`).
  - New root scripts: `setup:frontend`, `dev:frontend`, `api:types`.

Out of scope: the review detail screen, the PDF viewer and the e2e tests (feat-009); authentication (non-goal).

## How I Will Verify

- [ ] Layer 1 (static): `npm run lint` (ruff plus ESLint with zero warnings), `npm run typecheck` (mypy plus `tsc` strict)
- [ ] Layer 2 (runtime): `npm run test`:
  - backend tests for `/invoices/stats` (repository against PostgreSQL, service, API) and the OpenAPI drift test
  - Vitest + Testing Library + MSW for:
    - rows rendered from the API, money and status formatting
    - the filter chips change the query and the URL
    - empty, filtered-empty and error states, with retry
    - an upload adds a row; server rejections show their message
    - the `X-User` header follows the picker
    - the theme toggle
    - polling only while something is in progress
    - `schema.d.ts` matches `openapi.json`
- [ ] Layer 3 (system): `npm run check`, `npm run check-arch`, `npm run verify-feature -- feat-008`, plus a live run in the browser pane (dev database, Redis, API, worker and Vite): upload samples, watch them move to needs review, filter. Screenshots in light and dark mode, and at phone width.

## What Success Looks Like

Opening the dashboard shows the queue with status counts. Dropping three sample PDFs adds three cards that move from uploaded to needs review without a reload. Filtering by status updates the list and the URL. Stopping the API shows a clear error with a retry button. It looks deliberate and consistent in light and dark mode.

## Dependencies

- [x] Depends on: feat-004 (passing) for the list and upload API, and feat-007 for live status changes
- [ ] Blocked by: none

## Risks

- `npm run check` now also needs `npm run setup:frontend` once, and Node 20.19 or newer for the frontend (the harness itself still runs on Node 18).
- The frontend's dependency tree is large; versions stay within known majors (React 19, Vite 7, Tailwind 4, Vitest 3).

## Commit Plan

One commit: frontend, backend stats endpoint, OpenAPI export, harness wiring, tests, docs and harness state together.

---

_Signed off by: Claude (Opus 5.5) on 2026-10-13_
