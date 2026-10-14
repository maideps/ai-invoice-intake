# Sprint Contract

**Feature ID:** polish-portfolio
**Feature Name:** Portfolio polish
**Date:** 2026-10-14
**Estimated Duration:** 1 session

## What I Will Build

The author's task list (`claude-code-tasks.md`, Part B) for presenting the finished project on GitHub. Part A, the profile README in `maideps/maideps`, is done outside this repository: commit `4ab7425` there.

- **B1, metadata:**
  - Add the topics `fastapi`, `react`, `typescript`, `postgresql`, `redis`, `docker`, `openai`, `human-in-the-loop`, `invoice-processing`, `ai-automation`.
  - Keep the description; add no homepage, since there is no live demo.
  - Pins can't be set through the API, so the author gets the clicks.
- **B2, CI:** the latest run on `main` must be green, and the badge must point at `ci.yml`. Run 38594156191 is green.
- **B3, README:**
  - The decisions table in numeric order, adding the missing D-017 and D-020.
  - The harness command reference (verification layers and the make/npm table) moves to `docs/HARNESS.md` (declared in `productRoots`), with a one-line link in the README.
  - "How it was built" becomes a short "Built with ai-harness-framework" section. It explains why `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `codex.md`, `claude-progress.md`, `PROGRESS.md` and `session-handoff.md` sit in the root: they are the process record, not product code.
  - No numbers that aren't computed from the repository.
  - Every image has alt text. `tools/check-docs.mjs` gains that check, so it stays true.
  - Two items in the task list, a "README" link to `#` and a duplicate "About" block, are GitHub's own page interface: the README panel's tab buttons and the About sidebar rendered for wide and narrow screens. Nothing in the repository produces them, so nothing changes.
- **B4, release:** after the commits are pushed and CI is green, tag `v1.0.0` and create a GitHub release. Its notes say what it is, how to run it (`docker compose up --build`) and the main decisions.
- **B5, fresh check:** clone into an empty folder and follow only the README's quick start, without the layer cache. It must reach the sign-in page with the demo accounts and the 12 invoices. Anything unclear gets fixed.

## How I Will Verify

- [x] Layer 1 (static): `npm run lint` (the docs check, shown to fail on an image without alt text), `npm run typecheck`, `npm run check-arch`
- [x] Layer 2 (runtime): `npm run test`
- [x] Layer 3 (system): `npm run check` before every commit; `npm run verify-feature -- polish-portfolio`
- [x] After the push: CI green (run 38606616294); the fresh clone works; the release is created on the commit with these records

## Dependencies

- [x] Depends on: feat-015
- [ ] Blocked by: none

## Commit Plan

One commit per logical change: the docs check (alt text), the README and `docs/HARNESS.md`, then the harness records. Topics and the release are GitHub settings, not commits.

---

_Signed off by: Claude (Opus 5.5) on 2026-10-14_
