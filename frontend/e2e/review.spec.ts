import path from "node:path";
import { fileURLToPath } from "node:url";

import { expect, test } from "@playwright/test";

const SAMPLE = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../samples/invoices/invoice-007.pdf",
);

test("a reviewer uploads, checks, corrects and approves an invoice", async ({ page }) => {
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
  await expect(page.getByText("Approved for export")).toBeVisible();

  const trail = page.getByRole("region", { name: "Audit trail" });
  await expect(trail).toContainText("e2e-reviewer uploaded the invoice");
  await expect(trail).toContainText("fake:ground-truth read");
  await expect(trail).toContainText("e2e-reviewer changed invoice number");
  await expect(trail).toContainText("F2026/3734-A");
  await expect(trail).toContainText("e2e-reviewer approved it");

  // Back in the queue, the invoice now counts as approved.
  await page.getByRole("link", { name: "Review queue" }).first().click();
  await expect(page.getByRole("button", { name: /^Approved\s*1$/ })).toBeVisible();
});
