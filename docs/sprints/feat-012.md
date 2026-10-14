# Sprint Contract

**Feature ID:** feat-012
**Feature Name:** README, diagram and demo
**Date:** 2026-10-13
**Estimated Duration:** 1 session

## What I Will Build

A README that puts the product first. A new reader sees what it does, runs it in under five minutes, understands how it is built and why, and finds the development details after that.

- **README structure:**
  1. Pitch, CI badge and a hero screenshot.
  2. "Run it in five minutes" with `docker compose up --build`.
  3. A walkthrough with screenshots: the queue, the review screen with the highlighted total, the export.
  4. The architecture as a Mermaid diagram (which GitHub renders), with the invoice lifecycle as a state diagram.
  5. Design decisions: a table with one line per decision and a link to its entry in `DECISIONS.md`.
  6. Development: local setup, the commands, tests, e2e, CI.
  7. How it was built, with the harness workflow and its command reference collapsed. The harness checks that table, so it stays.
- **Screenshots** in `docs/images/` (added to `productRoots`), taken at 1440 × 900 from the real Compose stack, in light and dark mode.
- **`tools/screenshots.mjs`** (`npm run screenshots`) regenerates the screenshots reproducibly, as `npm run samples` does for the PDFs:
  - It starts its own Compose project and waits for the seeded samples.
  - Through the API it corrects and approves some invoices and rejects one, so the queue shows every outcome.
  - It drives Chromium with Playwright and saves the images, then removes the project.
- **`tools/lib/compose-stack.mjs`**: the start, wait and teardown helpers shared by `compose-smoke.mjs` and `screenshots.mjs`.
- **`tools/check-docs.mjs`**, added to `npm run lint`, checks the README and the docs:
  - every relative link and image points to a file that exists
  - every `DECISIONS.md#...` anchor matches a heading
  - every `npm run <script>` mentioned exists in `package.json`

Out of scope: a hosted demo, a video, translating the README.

## How I Will Verify

- [x] Layer 1 (static): `npm run lint` (with the docs check, shown to fail on a broken link), `npm run typecheck`, `npm run check-arch`
- [x] Layer 2 (runtime): `npm run test`; `npm run compose:smoke` after the refactor
- [x] Layer 3 (system): `npm run check` and `npm run verify-feature -- feat-012`, plus the five-minute run:
  - Clone the repository into a fresh folder.
  - Follow only the README: `docker compose up --build`, images built without the layer cache.
  - Time it until the dashboard shows the 12 invoices in "Needs review".
- [ ] After the push: CI green; the README renders on GitHub (diagram, images, anchors).

## What Success Looks Like

A visitor on the GitHub page sees the product in the first screen. They understand its flow from three screenshots and one diagram. They run it with one command and reach the review queue in well under five minutes. Each design choice links to its reasoning.

## Dependencies

- [x] Depends on: feat-011 (Compose stack)
- [ ] Blocked by: none

## Risks

- Screenshot size: PNGs at 1440 px can be large; keep each under about 300 KB (Chromium's PNGs are already compressed; crop where it helps).
- The five-minute time depends on download speed for the base images. The measurement records what was cached, and the README states what the first start downloads.

## Commit Plan

One commit: README, images, tools, docs check, harness state and docs; then push and confirm CI and the rendered page.

---

_Signed off by: Claude (Opus 5.5) on 2026-10-13_
