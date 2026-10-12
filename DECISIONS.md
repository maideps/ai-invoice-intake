# Architectural Decisions Log

This file records significant architectural decisions, their context, alternatives considered, and consequences. It serves as durable cross-session memory for why the codebase is structured the way it is.

## Decision Template

```
### D-XXX: [Decision Title]

**Date:** YYYY-MM-DD
**Status:** proposed | accepted | deprecated | superseded by D-YYY
**Context:** [What problem are we solving? What constraints exist?]
**Decision:** [What did we decide to do?]
**Alternatives considered:**
- Alternative 1: [description] — Rejected because [reason]
**Consequences:**
- Positive: [benefits gained]
- Negative: [tradeoffs accepted]
```

## Recorded Decisions

<!-- Add decision records here, newest last. Expand long records into docs/decisions/ and link back from here. -->

### D-001: Known baseline flake from the framework's backup tests

**Date:** 2026-10-12
**Status:** resolved 2026-10-12 (fixed upstream in ai-harness-framework D-021, applied via harness-upgrade)
**Context:** `npm run check` runs the shipped runner tests. `tests/harness-backup.test.mjs` fails intermittently (1-2 tests) because `createBackup` derives the backup id from `new Date().toISOString()` (millisecond resolution), so two backups in the same millisecond share a directory. Reproduced 5/5 runs in the framework repo itself.
**Decision:** Do not edit CORE files in this repo. Fix the id generation upstream in ai-harness-framework, then apply it here with `harness-upgrade`. Until then, treat these two tests as a known flake and do not mark features passing on a run where they are the only failures without re-running.
**Alternatives considered:**
- Patch scripts/harness-backup.mjs here — Rejected because CORE files must not be edited in adopter repos and the change would be lost on upgrade.
**Consequences:**
- Positive: the harness contract stays intact and the bug gets fixed at its source.
- Negative: the baseline is not reliably green until the upstream fix lands.

### D-002: Tech stack and scope for the portfolio project

**Date:** 2026-10-12
**Status:** accepted (provider selection refined by D-005)
**Context:** The goal is a public portfolio piece showing full-stack and AI-automation skills without using any employer code or data.
**Decision:** FastAPI + PostgreSQL + Redis worker + React/TypeScript, invoices as the document type, all data synthetic, AI extraction behind an interface with a deterministic fake for tests, human approval required before any export.
**Alternatives considered:**
- CVs as the document type — Rejected because it is too close to prior private work (HireLens).
- Vue frontend — Rejected in favour of React for wider hiring recognition.
**Consequences:**
- Positive: clear, verifiable features; no NDA exposure.
- Negative: a larger stack to keep green in CI.

### D-003: Backend tooling runs through a small Node launcher wired into the harness scripts

**Date:** 2026-10-12
**Status:** accepted
**Context:** The harness resolves product verification layers from the root `package.json` scripts (the root is a Node project), but the backend is Python. The author works on Windows, where virtualenv paths differ (`.venv/Scripts` vs `.venv/bin`).
**Decision:** `tools/py.mjs` finds the right interpreter (`$INVOICE_INTAKE_PYTHON`, then `backend/.venv`, then the system Python), prints a clear hint when dependencies are missing, and offers a `setup` command that creates `backend/.venv`. The root `lint`, `typecheck`, `test` and `build` scripts keep the harness's own check and append the backend command with `&&`, so the harness gates cover both. Dev dependency `httpx2` replaces `httpx` because the current Starlette test client deprecates `httpx`.
**Alternatives considered:**
- Add a `pyproject.toml` at the repo root so stack detection picks Python — Rejected: it would shadow the harness's own Node runtime and skip its checks.
- Document the Python commands only in the README — Rejected: the harness gates would not verify the backend.
**Consequences:**
- Positive: one command surface (`npm run check`) covers harness and backend on every OS.
- Negative: a fresh clone must run `npm run setup:backend` once before the gates can pass; the launcher says so when it is missing.

### D-004: The `e2e` layer is an explicit SKIP placeholder until the product has end-to-end tests

**Date:** 2026-10-12
**Status:** accepted (temporary, until feat-009 / feat-011)
**Context:** The harness ships `scripts.e2e` as `node scripts/framework-check.mjs e2e`, which runs the framework's own adoption matrix: it generates throwaway adopter repos from this repository's `package.json` and runs the harness in each. Once this project customised its `package.json` scripts (D-003), the matrix fixtures referenced `tools/py.mjs` and `backend/`, which the fixtures do not contain, so the matrix failed (6 failures) even though the product itself was healthy.
**Decision:** Point `scripts.e2e` at `tools/skip.mjs`, which prints a visible `[SKIP]` and exits 0, so `npm run check` stays runnable and honest about what is not verified. Replace it with real end-to-end tests when the UI exists.
**Alternatives considered:**
- Keep the framework's matrix as the e2e layer — Rejected: it tests the framework, not this product, and breaks on any customised `package.json`.
- Delete the `e2e` script — Rejected: `npm run check` chains `npm run e2e` and would fail with a missing-script error.
**Consequences:**
- Positive: `npm run check` is green and the skipped layer is stated in its output.
- Negative: layer 3b is unverified until real e2e tests exist; the feature gate must not be read as end-to-end evidence yet.
- Follow-up (resolved 2026-10-12): the framework's matrix no longer breaks on customised scripts (ai-harness-framework D-022, commit 79bd6c4), and the matrix passes in this repo after `harness-upgrade`. The placeholder stays anyway: the default e2e layer tests the harness, not this product, so it is replaced only when real end-to-end tests exist.

### D-005: The AI extraction provider is chosen by configuration

**Date:** 2026-10-12
**Status:** accepted
**Context:** D-002 put AI extraction behind an interface but named OpenAI as the only real implementation. The author wants to be able to run the pipeline on other providers (for example Anthropic, Gemini or a local model) without touching the worker, services or review flow.
**Decision:** The `INVOICE_INTAKE_EXTRACTION_PROVIDER` setting names the provider (`openai`, `fake`, and later others). One factory in the infrastructure layer maps that name to an implementation of the domain's `ExtractionProvider` interface; nothing else imports a concrete provider. Each provider reads its own API key and model settings. The default is `fake`, so a fresh clone, the tests and CI run without an API key or network access. An unknown name or a missing key for the chosen provider fails at startup, not on the first invoice. feat-005 ships `openai` and `fake`; each extra provider is a new class plus a factory entry.
**Alternatives considered:**
- Hard-wire OpenAI and swap in the fake only in tests — Rejected: changing provider would mean code changes outside infrastructure.
- Use a multi-provider wrapper library (for example LiteLLM) — Rejected for now: it hides the structured-output and document-input differences between providers that the extraction step depends on, and adds a dependency before there is a second provider.
**Consequences:**
- Positive: adding a provider touches only infrastructure and settings; the default runs offline.
- Negative: providers differ in document input, structured-output support and confidence signals, so each implementation must map its output into the same validated `ExtractionResult`, and each one needs its own tests.
