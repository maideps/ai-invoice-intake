import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";

import type { Invoice } from "@/api/client";
import { STATUSES, type InvoiceStatus } from "@/lib/status";

/** An in-memory stand-in for the API, so component tests run the real fetch and query code. */
export const db: { invoices: Invoice[]; requests: Request[] } = { invoices: [], requests: [] };

let sequence = 0;

export function makeInvoice(overrides: Partial<Invoice> & { status?: InvoiceStatus } = {}): Invoice {
  sequence += 1;
  return {
    id: `00000000-0000-4000-8000-${String(sequence).padStart(12, "0")}`,
    filename: `invoice-${String(sequence).padStart(3, "0")}.pdf`,
    status: "needs_review",
    version: 4,
    uploaded_at: new Date(Date.now() - sequence * 60_000).toISOString(),
    fields: {
      vendor_name: "Maple Ridge Software Inc.",
      invoice_number: `MRS-${sequence}`,
      issue_date: "2026-06-01",
      due_date: "2026-07-16",
      currency: "CAD",
      subtotal: "5637.93",
      tax: "732.93",
      total: "6370.86",
      line_items: [],
    },
    confidence: null,
    events: [],
    ...overrides,
  };
}

export function resetDb(): void {
  db.invoices = [];
  db.requests = [];
  sequence = 0;
}

const summary = (invoice: Invoice) => ({
  id: invoice.id,
  filename: invoice.filename,
  status: invoice.status,
  uploaded_at: invoice.uploaded_at,
  vendor_name: invoice.fields.vendor_name,
  currency: invoice.fields.currency,
  total: invoice.fields.total,
});

export const handlers = [
  http.get("*/api/invoices/stats", () => {
    const by_status = Object.fromEntries(
      STATUSES.map((status) => [status, db.invoices.filter((i) => i.status === status).length]),
    );
    return HttpResponse.json({ total: db.invoices.length, by_status });
  }),

  http.get("*/api/invoices", ({ request }) => {
    db.requests.push(request.clone());
    const url = new URL(request.url);
    const status = url.searchParams.get("status");
    const limit = Number(url.searchParams.get("limit") ?? 50);
    const offset = Number(url.searchParams.get("offset") ?? 0);
    const matching = db.invoices.filter((invoice) => !status || invoice.status === status);
    return HttpResponse.json({
      items: matching.slice(offset, offset + limit).map(summary),
      total: matching.length,
      limit,
      offset,
    });
  }),

  http.get("*/api/invoices/:id", ({ params }) => {
    const invoice = db.invoices.find((i) => i.id === params.id);
    return invoice
      ? HttpResponse.json(invoice)
      : HttpResponse.json({ detail: `invoice ${String(params.id)} not found` }, { status: 404 });
  }),

  http.post("*/api/invoices", async ({ request }) => {
    db.requests.push(request.clone());
    // Read the multipart body as text: enough to find the file name and the PDF signature.
    const body = await request.text();
    const filename = /filename="([^"]+)"/.exec(body)?.[1];
    if (!filename) {
      return HttpResponse.json({ detail: "the file is empty" }, { status: 400 });
    }
    if (!body.includes("%PDF-")) {
      return HttpResponse.json({ detail: "only PDF, PNG and JPEG files are accepted" }, { status: 415 });
    }
    const invoice = makeInvoice({
      filename,
      status: "uploaded",
      version: 1,
      uploaded_at: new Date().toISOString(),
      fields: {
        vendor_name: null,
        invoice_number: null,
        issue_date: null,
        due_date: null,
        currency: null,
        subtotal: null,
        tax: null,
        total: null,
        line_items: [],
      },
    });
    db.invoices.unshift(invoice);
    return HttpResponse.json(invoice, { status: 201 });
  }),
];

export const server = setupServer(...handlers);
