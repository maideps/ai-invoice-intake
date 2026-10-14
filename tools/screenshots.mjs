#!/usr/bin/env node
// Regenerate the README screenshots in docs/images/ from the real docker compose stack.
//
//   node tools/screenshots.mjs        (npm run screenshots; needs Docker and npm run setup:frontend)
//
// It starts its own compose project (ports 8280 and 9280), waits for the seeded samples,
// gives the queue a realistic mix through the API (corrected and approved invoices, which the
// worker exports, and one rejection), then drives Chromium with Playwright at 1440 x 900.
// Everything is removed afterwards. Same data, same screens: rerun it after a UI change.

import { mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";

import { ComposeStack, root, withStack } from "./lib/compose-stack.mjs";

const OUT = path.join(root, "docs", "images");
const REVIEWER = "Sam Rivera";
const VIEWPORT = { width: 1440, height: 900 };

// Playwright is a frontend dev dependency; load it from there.
const { chromium } = createRequire(path.join(root, "frontend", "package.json"))("@playwright/test");

const stack = new ComposeStack({
  project: "invoice-intake-screenshots",
  webPort: 8280,
  accountingPort: 9280,
  log: (message) => console.log(`[screenshots] ${message}`),
});

async function prepareData() {
  const page = await stack.api("/invoices?limit=50");
  const byName = Object.fromEntries(page.items.map((item) => [item.filename, item.id]));
  const detail = (name) => stack.api(`/invoices/${byName[name]}`);

  stack.log("correcting and approving three invoices, rejecting one");
  const corrected = await detail("invoice-002.pdf");
  const edited = await stack.post(
    `/invoices/${corrected.id}/fields`,
    { version: corrected.version, fields: { invoice_number: `${corrected.fields.invoice_number}-A` } },
    REVIEWER,
  );
  await stack.post(`/invoices/${edited.id}/approve`, { version: edited.version }, REVIEWER);
  for (const name of ["invoice-001.pdf", "invoice-003.pdf"]) {
    const invoice = await detail(name);
    await stack.post(`/invoices/${invoice.id}/approve`, { version: invoice.version }, REVIEWER);
  }
  const duplicate = await detail("invoice-004.pdf");
  await stack.post(
    `/invoices/${duplicate.id}/reject`,
    { version: duplicate.version, reason: "Duplicate of an invoice paid last month" },
    REVIEWER,
  );
  for (const name of ["invoice-001.pdf", "invoice-002.pdf", "invoice-003.pdf"]) {
    await stack.until(byName[name], `${name} exported`, (invoice) => invoice.status === "exported");
  }
  return byName;
}

async function shoot(browser, colorScheme, steps) {
  // A fixed locale, so totals read the same whoever regenerates the images.
  const context = await browser.newContext({ viewport: VIEWPORT, colorScheme, locale: "en-US", reducedMotion: "reduce" });
  await context.addInitScript((name) => {
    window.localStorage.setItem("invoice-intake:acting-as", name);
  }, REVIEWER);
  const page = await context.newPage();
  try {
    await steps(page);
  } finally {
    await context.close();
  }
}

async function openReview(page, id, { highlightTotal = false } = {}) {
  await page.goto(`${stack.web}/invoices/${id}`);
  await page.locator(".react-pdf__Page canvas").waitFor();
  await page.locator(".textLayer span").first().waitFor();
  if (highlightTotal) {
    await page.getByLabel("Total", { exact: true }).click();
    await page.locator(".textLayer mark").first().waitFor();
    // Focusing the field scrolls the page a little; frame the screen from the top again.
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.waitForTimeout(300);
  }
}

await withStack(stack, async () => {
  await stack.start();
  const ids = await prepareData();
  mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch();
  try {
    await shoot(browser, "light", async (page) => {
      stack.log("queue.png");
      await page.goto(stack.web);
      await page.getByText("invoice-012.pdf").waitFor();
      await page.screenshot({ path: path.join(OUT, "queue.png") });

      stack.log("review.png");
      await openReview(page, ids["invoice-007.pdf"], { highlightTotal: true });
      await page.screenshot({ path: path.join(OUT, "review.png") });

      stack.log("exported.png");
      await openReview(page, ids["invoice-002.pdf"]);
      await page.getByText(/Exported to the accounting system/).waitFor();
      // The document stays in view (sticky) beside the audit trail with the delivery.
      await page.getByRole("region", { name: "Audit trail" }).evaluate((trail) => trail.scrollIntoView({ block: "end" }));
      await page.waitForTimeout(300);
      await page.screenshot({ path: path.join(OUT, "exported.png") });
    });
    await shoot(browser, "dark", async (page) => {
      stack.log("review-dark.png");
      await openReview(page, ids["invoice-007.pdf"], { highlightTotal: true });
      await page.screenshot({ path: path.join(OUT, "review-dark.png") });
    });
  } finally {
    await browser.close();
  }
  stack.log(`saved to ${path.relative(root, OUT)}`);
  return 0;
});
