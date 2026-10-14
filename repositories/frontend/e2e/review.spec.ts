import { createHmac } from "node:crypto";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { expect, test } from "@playwright/test";

const SAMPLE = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../../samples/invoices/invoice-007.pdf",
);

const WEBHOOK = process.env.E2E_WEBHOOK_URL ?? "http://127.0.0.1:8101";
const SECRET = process.env.E2E_WEBHOOK_SECRET ?? "e2e-webhook-secret";

interface Delivery {
  path: string;
  headers: Record<string, string>;
  body: string;
}

test("a reviewer uploads, checks, corrects and approves an invoice, which is exported", async ({ page, request }) => {
  // Sign in as the demo reviewer; the audit trail records the username.
  await page.goto("/");
  await page.getByRole("button", { name: "Sign in as Sam Rivera (Reviewer)" }).click();
  await expect(page.getByRole("button", { name: "Signed in as Sam Rivera (Reviewer)" })).toBeVisible();

  // Upload through the drop zone's file picker; the worker extracts it in the background.
  await page.getByLabel("Upload invoices").setInputFiles(SAMPLE);
  await expect(page.getByText("invoice-007.pdf uploaded")).toBeVisible();
  const row = page.getByRole("link", { name: /invoice-007\.pdf/ });
  await expect(row).toContainText("Needs review", { timeout: 30_000 });
  await expect(row).toContainText("Atelier Lumière SARL");

  // The review screen: the PDF is rendered with a text layer beside the fields.
  await row.click();
  await expect(page.getByRole("heading", { name: "invoice-007.pdf" })).toBeVisible();
  await expect(page.locator(".react-pdf__Page canvas")).toBeVisible();

  // Selecting the total finds it in the document, printed the French way.
  await page.getByLabel("Total", { exact: true }).click();
  const mark = page.locator(".textLayer mark").first();
  await expect(mark).toBeAttached();
  await expect(mark).toHaveText("3 627,23");
  await expect(page.getByText("Highlighted in the document")).toBeVisible();

  // Correct a field and save.
  await page.getByLabel("Invoice number", { exact: true }).fill("F2026/3734-A");
  await page.getByRole("button", { name: /Save changes/ }).click();
  await expect(page.getByText("Changes saved", { exact: true })).toBeVisible();

  // Approve with the keyboard (focus outside the fields).
  await page.getByRole("heading", { name: "invoice-007.pdf" }).click();
  await page.keyboard.press("a");
  await expect(page.getByText("invoice-007.pdf approved")).toBeVisible();

  // The worker posts it to the accounting system's webhook; the screen follows along.
  await expect(page.getByText(/Exported to the accounting system/)).toBeVisible({ timeout: 30_000 });

  const trail = page.getByRole("region", { name: "Audit trail" });
  await expect(trail).toContainText("sam.rivera uploaded the invoice");
  await expect(trail).toContainText("fake:ground-truth read");
  await expect(trail).toContainText("sam.rivera changed invoice number");
  await expect(trail).toContainText("F2026/3734-A");
  await expect(trail).toContainText("sam.rivera approved it");
  await expect(trail).toContainText("export-service delivered it to the accounting system");

  // Exactly one delivery, signed, carrying the corrected fields.
  const deliveries = (await (await request.get(`${WEBHOOK}/deliveries`)).json()) as Delivery[];
  expect(deliveries).toHaveLength(1);
  const [delivery] = deliveries;
  const payload = JSON.parse(delivery.body) as { invoice_id: string; approved_by: string; fields: Record<string, unknown> };
  expect(delivery.path).toBe("/invoices");
  expect(delivery.headers["x-invoice-intake-signature"]).toBe(
    `sha256=${createHmac("sha256", SECRET).update(delivery.body).digest("hex")}`,
  );
  expect(delivery.headers["idempotency-key"]).toBe(payload.invoice_id);
  expect(payload.approved_by).toBe("sam.rivera");
  expect(payload.fields.invoice_number).toBe("F2026/3734-A");

  // Back in the queue, the invoice now counts as exported.
  await page.getByRole("link", { name: "Review queue" }).first().click();
  await expect(page.getByRole("button", { name: /^Exported\s*1$/ })).toBeVisible();
});

test("a viewer reads but cannot change anything, and the API agrees", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Sign in as Alex Chen (Viewer)" }).click();

  await expect(page.getByText(/signed in as a viewer/)).toBeVisible();
  await expect(page.getByLabel("Upload invoices")).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Users" })).toHaveCount(0);

  // Not just hidden: the API refuses the viewer's session too (page.request shares its cookie).
  const upload = await page.request.post("/api/invoices", {
    multipart: { file: { name: "x.pdf", mimeType: "application/pdf", buffer: Buffer.from("%PDF-1.4") } },
  });
  expect(upload.status()).toBe(403);

  // Signing out ends the session for the API as well.
  await page.getByRole("button", { name: /^Signed in as Alex Chen/ }).click();
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  expect((await page.request.get("/api/invoices")).status()).toBe(401);
});
