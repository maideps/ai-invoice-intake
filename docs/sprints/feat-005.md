# Sprint Contract

**Feature ID:** feat-005
**Feature Name:** AI extraction service
**Date:** 2026-10-12
**Estimated Duration:** 1 session

## What I Will Build

AI extraction behind a domain interface, with the provider chosen by configuration (D-005), and an audit trail that keeps every model output, whether it was accepted or rejected.

- **Domain (`domain/extraction.py`):**
  - The extraction output contract as a JSON schema (`OUTPUT_SCHEMA`: invoice fields, plus a confidence between 0 and 1 for each field).
  - `ExtractionProvider` interface: `extract(document) -> RawExtraction`, the model's parsed output with provider and model names.
  - `parse_extraction`: a strict validator that turns the raw output into an `ExtractionResult` or raises `ExtractionOutputError` listing every problem.
  - `ExtractionProviderError` for provider failures (network, API).
- **Audit trail:**
  - Two new actions: `extraction_recorded` and `extraction_rejected`. Both are allowed only while `extracting` and only for an `ai` actor.
  - Audit events gain a JSON `details` payload (the model output, its confidence, the errors). Status fields are now only set on `status_changed` events.
  - `Invoice.record_extraction` stores the extracted fields. `Invoice.record_rejected_extraction` keeps the invalid output and its errors.
  - `Invoice.restore` replays the new actions with the same rules.
  - `Invoice.extraction_confidence` exposes the latest per-field confidence.
- **Service (`services/extraction.py`):** `ExtractionService.extract(invoice_id)`.
  - Moves `uploaded` to `extracting`, calls the provider, and validates the output.
  - Valid output: records it and moves to `needs_review`.
  - Invalid output: records the rejection and stays in `extracting`, so a retry (feat-007) can continue from there.
  - Provider errors roll back and propagate.
- **Providers (`infrastructure/extraction/`):**
  - `fake` (the default): deterministic. It looks a document up by SHA-256 among the synthetic samples and returns their ground truth with stable per-field confidence. An unknown document gets empty fields with zero confidence, which a reviewer fills in.
  - `openai`: Responses API with a strict JSON-schema output format; a PDF goes in as `input_file`, PNG or JPEG as `input_image`. Default model `gpt-5.4-mini`, configurable.
  - `make_extraction_provider(settings)`: the single factory. It fails at startup on an unknown provider name, a missing OpenAI key, or a missing samples folder.
- **Persistence:** Alembic migration 0002 adds `audit_events.details` (jsonb), makes the status columns nullable, extends the `action` check, and adds a check tying status columns to `status_changed`. The downgrade refuses if extraction events exist, because the trail is append-only.
- **API:**
  - `POST /invoices/{id}/extract` runs extraction now and returns the invoice and whether the output was accepted: 404 for an unknown id, 409 when the status is wrong, 502 when the provider fails.
  - Invoice responses gain `confidence`, and audit events gain `details`.
- **Settings:** `INVOICE_INTAKE_EXTRACTION_PROVIDER` (default `fake`), `INVOICE_INTAKE_OPENAI_API_KEY`, `INVOICE_INTAKE_OPENAI_MODEL`, `INVOICE_INTAKE_OPENAI_TIMEOUT_SECONDS`, `INVOICE_INTAKE_FAKE_SAMPLES_DIR`.

Out of scope: running extraction automatically after upload, retries and a `failed` status (feat-007); editing fields (feat-006). Tests never call the real model (product constraint): the OpenAI provider is tested with a stub client.

## How I Will Verify

- [ ] Layer 1 (static): `npm run lint`, `npm run typecheck`
- [ ] Layer 2 (runtime): `npm run test`:
  - every committed sample extracted with the fake provider matches its ground truth and ends in `needs_review` with the expected four-event trail
  - invalid model outputs are rejected, recorded with their errors, and leave the invoice in `extracting`: not JSON, missing or extra keys, bad decimals, bad dates, confidence out of range, a domain rule broken
  - the factory returns the configured provider and fails on an unknown name or a missing key or folder
  - the OpenAI provider builds a strict JSON-schema request with the document attached, parses the reply, and maps SDK errors to `ExtractionProviderError`
  - restore and the repository round-trip the new events, including `details` through jsonb
  - migration 0002 upgrades, downgrades and upgrades again, and refuses to downgrade when extraction events exist
  - API extract endpoint: success, rejection, 404, 409, 502
- [ ] Layer 3 (system): `npm run check`, `npm run check-arch`, `npm run verify-feature -- feat-005`, plus a live run with the fake provider (upload a sample, extract, read the fields and confidence back)

## What Success Looks Like

Uploading `samples/invoices/invoice-001.pdf` and calling `POST /invoices/{id}/extract` with the default configuration returns status `needs_review`, the ground-truth fields, per-field confidence, and an `extraction_recorded` audit event that holds the output. Setting `INVOICE_INTAKE_EXTRACTION_PROVIDER=openai` without a key stops the app at startup with a message naming the missing variable.

## Dependencies

- [x] Depends on: feat-003 (passing), feat-004 (passing)
- [ ] Blocked by: none

## Risks

- Confidence from the OpenAI provider is the model's own estimate, not a calibrated probability; the UI should present it as a hint.
- The default OpenAI model name will age; it is a setting.
- With the default fake provider, a document that is not one of the samples comes back with empty fields; the reviewer fills them in.

## Commit Plan

One commit: domain, migration, providers, service, API, tests, docs and harness state together.

---

_Signed off by: Claude (Opus 5.5) on 2026-10-12_
