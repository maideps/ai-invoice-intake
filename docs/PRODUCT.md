# Product Overview

## Purpose

AI Invoice Intake turns incoming invoices into reviewed, structured records. An AI service extracts vendor, dates, totals and line items; a person confirms or corrects the result before anything is exported. The goal is to automate the repetitive reading and typing while keeping accountability with a human.

## Primary Users

- **Accounts-payable reviewer** — works the review queue, corrects extraction errors, approves or rejects.
- **Finance lead** — checks the audit trail and the export status.
- **Developer / integrator** — consumes the REST API and export webhooks.

## Key User Flows

- Upload an invoice (PDF or image) and see it appear in the queue with a processing status.
- Open a document in the review queue, compare the extracted fields with the source, edit any field, and approve or reject it.
- Approved invoices are exported to a configured webhook; failures are retried and visible.
- Inspect the audit log for any invoice: model output, confidence, edits, who decided what, and when.

## Non-Goals

- No real accounting, payment or tax logic.
- No real customer data: the project uses synthetic invoices only.
- No multi-tenant billing, SSO or production-grade access control in the first version.

## Product Constraints

- AI output is always a draft: nothing is exported without an explicit human approval.
- Tests never call the real model; the extraction provider sits behind an interface and is mocked.
- The whole system must start with a single command (`docker compose up`) and run on synthetic data.
- Secrets are read from environment variables and never committed.
