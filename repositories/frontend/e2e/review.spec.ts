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
  await page.goto("/");

  // Who is acting: recorded in the audit trail.
  await page.getByRole("button", { name: /Acting as/ }).click();
  await page.getByRole("textbox", { name: "Acting as" }).fill("e2e-reviewer");
  await page.getByRole("button", { name: "Save" }).click();

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
  await expect(trail).toContainText("e2e-reviewer uploaded the invoice");
  await expect(trail).toContainText("fake:ground-truth read");
  await expect(trail).toContainText("e2e-reviewer changed invoice number");
  await expect(trail).toContainText("F2026/3734-A");
  await expect(trail).toContainText("e2e-reviewer approved it");
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
  expect(payload.approved_by).toBe("e2e-reviewer");
  expect(payload.fields.invoice_number).toBe("F2026/3734-A");

  // Back in the queue, the invoice now counts as exported.
  await page.getByRole("link", { name: "Review queue" }).first().click();
  await expect(page.getByRole("button", { name: /^Exported\s*1$/ })).toBeVisible();
});
