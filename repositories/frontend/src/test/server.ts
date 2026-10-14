import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";

import type { Account, DemoAccount, Invoice, Permission, Role } from "@/api/client";
import { STATUSES, type InvoiceStatus } from "@/lib/status";

/** An in-memory stand-in for the API, so component tests run the real fetch and query code. */
export const db: {
  invoices: Invoice[];
  requests: Request[];
  exportConfigured: boolean;
  exportRequests: string[];
  /** Who is signed in (the session); null when signed out. */
  account: Account | null;
  accounts: Account[];
  passwords: Record<string, string>;
  demoAccounts: DemoAccount[];
} = {
  invoices: [],
  requests: [],
  exportConfigured: true,
  exportRequests: [],
  account: null,
  accounts: [],
  passwords: {},
  demoAccounts: [],
};

// The same role rules as the API (D-019).
const PERMISSIONS: Record<Role, Permission[]> = {
  viewer: ["read"],
  reviewer: ["read", "upload", "review"],
  admin: ["read", "upload", "review", "manage_accounts"],
};

export const PASSWORD = "correct horse battery";

/** Add an account (password: PASSWORD) and return it. */
export function addAccount(role: Role, username = `${role}-1`, display_name = `${role[0]!.toUpperCase()}${role.slice(1)} One`): Account {
  const account: Account = {
    id: `00000000-0000-4000-9000-${String(db.accounts.length + 1).padStart(12, "0")}`,
    username,
    display_name,
    role,
    active: true,
    created_at: new Date().toISOString(),
    permissions: PERMISSIONS[role],
  };
  db.accounts.push(account);
  db.passwords[username] = PASSWORD;
  return account;
}

/** Sign in (in the fake API) as a new account with this role. */
export function signInAs(role: Role, username?: string, display_name?: string): Account {
  db.account = addAccount(role, username, display_name);
  return db.account;
}

/** 401 when signed out, 403 when the role does not allow it, like the real API. */
function guard(permission: Permission): Response | null {
  const account = db.account && db.accounts.find((a) => a.id === db.account!.id && a.active);
  if (!account) return HttpResponse.json({ detail: "sign in first" }, { status: 401 });
  if (!account.permissions.includes(permission)) {
    return HttpResponse.json({ detail: `a ${account.role} can't do that` }, { status: 403 });
  }
  return null;
}

const actorName = () => db.account?.username ?? "nobody";

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
    export: null,
    events: [],
    ...overrides,
  };
}

export function resetDb(): void {
  db.invoices = [];
  db.requests = [];
  db.exportConfigured = true;
  db.exportRequests = [];
  db.accounts = [];
  db.passwords = {};
  db.demoAccounts = [];
  db.account = null;
  sequence = 0;
  // Most tests are about reviewing: start signed in as a reviewer.
  signInAs("reviewer", "maide", "Maide P");
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
    const denied = guard("read");
    if (denied) return denied;
    const by_status = Object.fromEntries(
      STATUSES.map((status) => [status, db.invoices.filter((i) => i.status === status).length]),
    );
    return HttpResponse.json({ total: db.invoices.length, by_status });
  }),

  http.get("*/api/invoices", ({ request }) => {
    const denied = guard("read");
    if (denied) return denied;
    db.requests.push(request.clone());
    const url = new URL(request.url);
    const status = url.searchParams.get("status");
    const limit = Number(url.searchParams.get("limit") ?? 50);
    const offset = Number(url.searchParams.get("offset") ?? 0);
    const matching = db.invoices
      .filter((invoice) => !status || invoice.status === status)
      .sort((a, b) => b.uploaded_at.localeCompare(a.uploaded_at)); // newest first, like the API
    return HttpResponse.json({
      items: matching.slice(offset, offset + limit).map(summary),
      total: matching.length,
      limit,
      offset,
    });
  }),

  http.get("*/api/invoices/:id", ({ params }) => {
    const denied = guard("read");
    if (denied) return denied;
    const invoice = db.invoices.find((i) => i.id === params.id);
    return invoice
      ? HttpResponse.json(invoice)
      : HttpResponse.json({ detail: `invoice ${String(params.id)} not found` }, { status: 404 });
  }),

  http.post("*/api/invoices", async ({ request }) => {
    const denied = guard("upload");
    if (denied) return denied;
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

// Review endpoints, following the real API's rules: version (409), status (409), 422 problems.

type Fields = Invoice["fields"];
const REQUIRED: (keyof Fields)[] = ["vendor_name", "invoice_number", "issue_date", "currency", "total"];

function reviewable(id: string, version: unknown): Invoice | Response {
  const invoice = db.invoices.find((i) => i.id === id);
  if (!invoice) return HttpResponse.json({ detail: `invoice ${id} not found` }, { status: 404 });
  if (version !== invoice.version) {
    return HttpResponse.json(
      { detail: `invoice ${id} is at version ${invoice.version}, not ${String(version)}; reload it and retry` },
      { status: 409 },
    );
  }
  if (invoice.status !== "needs_review") {
    return HttpResponse.json({ detail: `cannot record that while the invoice is ${invoice.status}` }, { status: 409 });
  }
  return invoice;
}

function problem(message: string, errors: string[]) {
  return HttpResponse.json({ detail: { message, errors } }, { status: 422 });
}

function addEvent(invoice: Invoice, event: Partial<Invoice["events"][number]>) {
  invoice.version += 1;
  invoice.events = [
    ...invoice.events,
    {
      sequence: invoice.version,
      occurred_at: new Date().toISOString(),
      actor_kind: "user",
      actor_name: actorName(),
      action: "status_changed",
      from_status: null,
      to_status: null,
      reason: null,
      details: null,
      ...event,
    },
  ];
}

handlers.push(
  http.patch("*/api/invoices/:id/fields", async ({ request, params }) => {
    const denied = guard("review");
    if (denied) return denied;
    const body = (await request.json()) as { version: number; fields: Partial<Fields> };
    const found = reviewable(String(params.id), body.version);
    if (found instanceof Response) return found;
    const errors = Object.entries(body.fields)
      .filter(
        ([name, value]) =>
          ["subtotal", "tax", "total"].includes(name) &&
          value !== null &&
          (typeof value !== "string" || !/^\d+(\.\d+)?$/.test(value)),
      )
      .map(([name]) => `fields.${name} must be a decimal string like '1234.50'`);
    if (errors.length) return problem("invalid field values", errors);
    const changes = Object.fromEntries(
      Object.entries(body.fields).map(([name, to]) => [name, { from: found.fields[name as keyof Fields], to }]),
    );
    found.fields = { ...found.fields, ...body.fields };
    addEvent(found, {
      action: "fields_edited",
      actor_name: actorName(),
      details: { changes },
    });
    return HttpResponse.json(found);
  }),

  http.post("*/api/invoices/:id/approve", async ({ request, params }) => {
    const denied = guard("review");
    if (denied) return denied;
    const body = (await request.json()) as { version: number };
    const found = reviewable(String(params.id), body.version);
    if (found instanceof Response) return found;
    const missing = REQUIRED.filter((name) => !found.fields[name]);
    if (missing.length) return problem("cannot approve until these fields are filled", missing);
    addEvent(found, { from_status: "needs_review", to_status: "approved" });
    found.status = "approved";
    return HttpResponse.json(found);
  }),

  http.post("*/api/invoices/:id/reject", async ({ request, params }) => {
    const denied = guard("review");
    if (denied) return denied;
    const body = (await request.json()) as { version: number; reason: string };
    const found = reviewable(String(params.id), body.version);
    if (found instanceof Response) return found;
    if (!body.reason.trim()) return problem("a rejection needs a reason", ["a rejection needs a reason"]);
    addEvent(found, { from_status: "needs_review", to_status: "rejected", reason: body.reason.trim() });
    found.status = "rejected";
    return HttpResponse.json(found);
  }),

  http.get("*/api/health", () =>
    HttpResponse.json({
      status: "ok",
      version: "test",
      environment: "test",
      export_configured: db.exportConfigured,
    }),
  ),

  http.post("*/api/invoices/:id/export", ({ params }) => {
    const denied = guard("review");
    if (denied) return denied;
    const invoice = db.invoices.find((i) => i.id === params.id);
    if (!invoice) return HttpResponse.json({ detail: "not found" }, { status: 404 });
    if (invoice.status !== "approved") {
      return HttpResponse.json({ detail: "only approved invoices are exported" }, { status: 409 });
    }
    db.exportRequests.push(invoice.id);
    return HttpResponse.json(invoice, { status: 202 });
  }),

  http.post("*/api/invoices/:id/extract", ({ params }) => {
    const denied = guard("review");
    if (denied) return denied;
    const invoice = db.invoices.find((i) => i.id === params.id);
    if (!invoice) return HttpResponse.json({ detail: "not found" }, { status: 404 });
    if (invoice.status === "failed") {
      addEvent(invoice, { from_status: "failed", to_status: "extracting" });
      invoice.status = "extracting";
    }
    return HttpResponse.json(invoice, { status: 202 });
  }),
);

// Sign-in and accounts (D-019)

handlers.push(
  http.get("*/api/auth/me", () =>
    db.account ? HttpResponse.json(db.account) : HttpResponse.json({ detail: "sign in first" }, { status: 401 }),
  ),

  http.post("*/api/auth/sign-in", async ({ request }) => {
    const body = (await request.json()) as { username: string; password: string };
    const account = db.accounts.find((a) => a.username === body.username.trim().toLowerCase());
    if (!account?.active || db.passwords[account.username] !== body.password) {
      return HttpResponse.json({ detail: "wrong username or password" }, { status: 401 });
    }
    db.account = account;
    return HttpResponse.json(account);
  }),

  http.post("*/api/auth/sign-out", () => {
    db.account = null;
    return new HttpResponse(null, { status: 204 });
  }),

  http.get("*/api/auth/demo-accounts", () => HttpResponse.json(db.demoAccounts)),

  http.get("*/api/accounts", () => guard("manage_accounts") ?? HttpResponse.json(db.accounts)),

  http.post("*/api/accounts", async ({ request }) => {
    const denied = guard("manage_accounts");
    if (denied) return denied;
    const body = (await request.json()) as { username: string; display_name: string; role: Role; password: string };
    const username = body.username.trim().toLowerCase();
    if (db.accounts.some((a) => a.username === username)) {
      return HttpResponse.json({ detail: `the username '${username}' is taken` }, { status: 409 });
    }
    if (body.password.length < 10) return problem("invalid account details", ["a password has 10 to 256 characters"]);
    const account = addAccount(body.role, username, body.display_name);
    db.passwords[username] = body.password;
    return HttpResponse.json(account, { status: 201 });
  }),

  http.patch("*/api/accounts/:id", async ({ request, params }) => {
    const denied = guard("manage_accounts");
    if (denied) return denied;
    const account = db.accounts.find((a) => a.id === params.id);
    if (!account) return HttpResponse.json({ detail: "not found" }, { status: 404 });
    const change = (await request.json()) as { role?: Role; active?: boolean; password?: string; display_name?: string };
    const next = { ...account, ...change };
    const admins = db.accounts.filter((a) => a.active && a.role === "admin").length;
    if (account.active && account.role === "admin" && !(next.active && next.role === "admin") && admins <= 1) {
      return HttpResponse.json(
        { detail: "keep at least one active admin, or no one can manage accounts" },
        { status: 409 },
      );
    }
    if (change.password !== undefined) db.passwords[account.username] = change.password;
    const updated: Account = {
      ...account,
      display_name: next.display_name,
      role: next.role,
      active: next.active,
      permissions: next.active ? PERMISSIONS[next.role] : [],
    };
    db.accounts = db.accounts.map((a) => (a.id === account.id ? updated : a));
    if (db.account?.id === account.id) db.account = updated.active ? updated : null;
    return HttpResponse.json(updated);
  }),
);

export const server = setupServer(...handlers);
