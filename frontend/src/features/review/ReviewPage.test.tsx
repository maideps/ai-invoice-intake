import { act, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { Invoice } from "@/api/client";
import { renderApp } from "@/test/render";
import { db, makeInvoice } from "@/test/server";

// pdf.js needs a real canvas; component tests check what the viewer is asked to highlight.
vi.mock("./DocumentViewer", () => ({
  default: ({ highlight }: { highlight: string[] }) => (
    <div data-testid="document" data-highlight={highlight.join("|")} />
  ),
}));

const CONFIDENCE = {
  vendor_name: 0.94,
  invoice_number: 0.91,
  issue_date: 0.62,
  due_date: 0.88,
  currency: 0.65,
  subtotal: 0.72,
  tax: 0.66,
  total: 0.97,
  line_items: 0.91,
};

function seed(overrides: Partial<Invoice> = {}): Invoice {
  const invoice = makeInvoice({ confidence: CONFIDENCE, ...overrides });
  db.invoices.push(invoice);
  return invoice;
}

async function open(invoice: Invoice) {
  const app = renderApp(`/invoices/${invoice.id}`);
  await screen.findByRole("heading", { name: invoice.filename });
  return app;
}

const field = (label: string) => screen.getByLabelText(label, { selector: "input" });

describe("review screen", () => {
  it("shows the extracted fields with their confidence, low ones flagged", async () => {
    await open(seed());

    expect(field("Vendor")).toHaveValue("Maple Ridge Software Inc.");
    expect(field("Total")).toHaveValue("6370.86");
    expect(field("Issue date")).toHaveAttribute("data-confidence", "low");
    expect(screen.getByText("Low · 0.62")).toBeInTheDocument();
    expect(screen.getByText("High · 0.97")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Next low-confidence field \(4\)/ })).toBeInTheDocument();
  });

  it("looks for the focused field's value in the document", async () => {
    const { user } = await open(seed());
    const viewer = await screen.findByTestId("document");

    await user.click(field("Total"));
    expect(viewer.dataset.highlight).toContain("6 370,86");
    expect(viewer.dataset.highlight).toContain("6,370.86");

    await user.click(field("Issue date"));
    expect(viewer.dataset.highlight).toContain("01/06/2026");
  });

  it("saves only the changed fields with the version, then shows the edit in the trail", async () => {
    const invoice = seed();
    const versionBefore = invoice.version;
    const { user } = await open(invoice);

    await user.clear(field("Total"));
    await user.type(field("Total"), "6400.00");
    expect(screen.getByText("Unsaved changes")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Save changes/ }));

    expect(await screen.findByText("Changes saved")).toBeInTheDocument();
    expect(db.invoices[0]!.fields.total).toBe("6400.00");
    expect(db.invoices[0]!.version).toBe(versionBefore + 1);
    const trail = screen.getByRole("region", { name: "Audit trail" });
    expect(within(trail).getByText(/changed total/)).toBeInTheDocument();
    expect(within(trail).getByText("6370.86")).toBeInTheDocument(); // old value, struck through
    expect(screen.getByText("All changes saved")).toBeInTheDocument();
  });

  it("shows a server error under the field it is about", async () => {
    const { user } = await open(seed());

    await user.clear(field("Total"));
    await user.type(field("Total"), "lots");
    await user.click(screen.getByRole("button", { name: /Save changes/ }));

    expect(await screen.findByText("fields.total must be a decimal string like '1234.50'")).toBeInTheDocument();
    expect(field("Total")).toHaveAttribute("aria-invalid", "true");
  });

  it("approves, after which the invoice is read-only", async () => {
    const { user } = await open(seed());

    await user.click(screen.getByRole("button", { name: /Approve/ }));

    await waitFor(() => expect(db.invoices[0]!.status).toBe("approved"));
    expect(await screen.findByText("Approved for export")).toBeInTheDocument();
    expect(field("Total")).toHaveAttribute("readonly");
    expect(screen.queryByRole("button", { name: /Approve/ })).not.toBeInTheDocument();
  });

  it("explains what approval needs, and shows the server's list when tried anyway", async () => {
    const invoice = seed();
    invoice.fields = { ...invoice.fields, total: null, currency: null };
    const { user } = await open(invoice);

    expect(screen.getByText("Approval needs: currency, total.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Approve/ }));

    expect(await screen.findByText("Couldn't approve")).toBeInTheDocument();
    expect(db.invoices[0]!.status).toBe("needs_review");
  });

  it("asks for a reason before rejecting", async () => {
    const { user } = await open(seed());

    await user.click(screen.getByRole("button", { name: /^Reject$/ }));
    await user.click(screen.getByRole("button", { name: "Reject invoice" }));
    expect(screen.getByText("Give a reason, so the next person knows why.")).toBeInTheDocument();

    await user.type(screen.getByLabelText("Why are you rejecting it?"), "Duplicate of INV-4410");
    await user.click(screen.getByRole("button", { name: "Reject invoice" }));

    await waitFor(() => expect(db.invoices[0]!.status).toBe("rejected"));
    expect(await screen.findByText("“Duplicate of INV-4410”")).toBeInTheDocument();
  });

  it("explains a conflict and reloads the latest version", async () => {
    const invoice = seed();
    const { user } = await open(invoice);
    // Someone else edits the invoice after we opened it.
    db.invoices[0] = { ...invoice, version: invoice.version + 1, fields: { ...invoice.fields, tax: "700.00" } };

    await user.click(screen.getByRole("button", { name: /Approve/ }));

    const banner = await screen.findByText(/This invoice changed since you opened it/);
    expect(db.invoices[0].status).toBe("needs_review");
    await user.click(within(banner.parentElement!).getByRole("button", { name: /Reload/ }));

    await waitFor(() => expect(screen.queryByText(/This invoice changed/)).not.toBeInTheDocument());
    expect(field("Tax")).toHaveValue("700.00");
  });

  it("offers another extraction attempt for a failed invoice", async () => {
    const { user } = await open(seed({ status: "failed" }));

    await user.click(screen.getByRole("button", { name: /Retry extraction/ }));

    expect(await screen.findByText("Queued for another extraction attempt")).toBeInTheDocument();
    expect(db.invoices[0]!.status).toBe("extracting");
  });

  it("supports keyboard shortcuts, but not while typing", async () => {
    const first = seed();
    const second = seed({ filename: "second.pdf" });
    first.uploaded_at = new Date(Date.now() - 3_600_000).toISOString(); // oldest: first in review order
    const { user, location } = await open(first);

    await user.keyboard("?");
    expect(screen.getByRole("region", { name: "Keyboard shortcuts" })).toBeInTheDocument();

    await user.click(field("Vendor"));
    await user.keyboard("a"); // typed into the field, not a shortcut
    expect(db.invoices[0]!.status).toBe("needs_review");
    await user.keyboard("{Escape}");
    act(() => (document.activeElement as HTMLElement).blur());

    await user.keyboard("j");
    await waitFor(() => expect(location().pathname).toBe(`/invoices/${second.id}`));
  });

  it("tells the story of the invoice in the audit trail", async () => {
    await open(
      seed({
        events: [
          event(1, { actor_name: "maide", to_status: "uploaded" }),
          event(2, { actor_kind: "system", actor_name: "extraction-service", from_status: "uploaded", to_status: "extracting" }),
          event(3, {
            actor_kind: "ai",
            actor_name: "openai:gpt-test",
            action: "extraction_rejected",
            details: { errors: ["output must be a JSON object", "fields is missing total"] },
          }),
          event(4, {
            actor_kind: "ai",
            actor_name: "fake:ground-truth",
            action: "extraction_recorded",
            details: { fields: { vendor_name: "Acme", total: "1.00", tax: null, line_items: [] } },
          }),
        ],
      }),
    );
    const trail = screen.getByRole("region", { name: "Audit trail" });

    expect(within(trail).getByText(/uploaded the invoice/)).toBeInTheDocument();
    expect(within(trail).getByText(/moved it to extracting/)).toBeInTheDocument();
    expect(within(trail).getByText("output must be a JSON object (and 1 more)")).toBeInTheDocument();
    expect(within(trail).getByText(/read 2 fields from the document/)).toBeInTheDocument();
  });
});

function event(sequence: number, overrides: Partial<Invoice["events"][number]>): Invoice["events"][number] {
  return {
    sequence,
    occurred_at: new Date().toISOString(),
    actor_kind: "user",
    actor_name: "someone",
    action: "status_changed",
    from_status: null,
    to_status: null,
    reason: null,
    details: null,
    ...overrides,
  };
}

describe("export state", () => {
  const approved = (exportState: Invoice["export"], events: Invoice["events"] = []) =>
    seed({ status: "approved", export: exportState, events });

  it("says the invoice is on its way while export is pending", async () => {
    await open(approved({ state: "pending", attempts: 0, last_error: null, exported_at: null }));

    expect(await screen.findByText("Sending to the accounting system…")).toBeInTheDocument();
  });

  it("explains when no export webhook is configured", async () => {
    db.exportConfigured = false;
    await open(approved({ state: "pending", attempts: 0, last_error: null, exported_at: null }));

    expect(await screen.findByText(/No export webhook is configured/)).toBeInTheDocument();
  });

  it("shows a failing delivery while it retries", async () => {
    await open(approved({ state: "retrying", attempts: 1, last_error: "HTTP 503: down", exported_at: null }));

    expect(screen.getByText("Delivery attempt 1 failed: HTTP 503: down. Retrying on its own.")).toBeInTheDocument();
  });

  it("offers to retry an export that gave up", async () => {
    const invoice = approved({ state: "failed", attempts: 5, last_error: "HTTP 500", exported_at: null });
    const { user } = await open(invoice);

    expect(screen.getByRole("alert")).toHaveTextContent("Export failed after 5 attempts: HTTP 500");
    await user.click(screen.getByRole("button", { name: /Retry export/ }));

    expect(await screen.findByText("Queued for another delivery attempt")).toBeInTheDocument();
    expect(db.exportRequests).toEqual([invoice.id]);
  });

  it("confirms when the invoice reached the accounting system", async () => {
    const at = new Date().toISOString();
    await open(seed({ status: "exported", export: { state: "exported", attempts: 0, last_error: null, exported_at: at } }));

    expect(screen.getByText(/Exported to the accounting system/)).toBeInTheDocument();
  });

  it("lists failed deliveries in the audit trail", async () => {
    await open(
      approved({ state: "failed", attempts: 2, last_error: "HTTP 503: down", exported_at: null }, [
        event(1, { actor_name: "maide", to_status: "uploaded" }),
        event(2, {
          actor_kind: "system",
          actor_name: "export-service",
          action: "export_failed",
          details: { attempt: 2, error: "HTTP 503: down", final: true, status_code: 503 },
        }),
      ]),
    );
    const trail = screen.getByRole("region", { name: "Audit trail" });

    expect(within(trail).getByText(/couldn't deliver it, attempt 2 \(no more automatic retries\)/)).toBeInTheDocument();
    expect(within(trail).getByText("HTTP 503: down")).toBeInTheDocument();
  });
});
