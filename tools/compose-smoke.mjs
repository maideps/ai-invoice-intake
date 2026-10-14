#!/usr/bin/env node
// Smoke test of the docker compose stack (D-015): builds and starts it as its own compose
// project on other ports, checks the product works through nginx, then removes everything
// (containers and volumes), also when a check fails.
//
//   node tools/compose-smoke.mjs      (npm run compose:smoke; also a CI job)

import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import path from "node:path";

import { ComposeStack, check, json, root, withStack } from "./lib/compose-stack.mjs";

const SAMPLE = path.join(root, "samples", "invoices", "invoice-007.pdf");
const TYPES = { js: "javascript", mjs: "javascript", css: "text/css", woff2: "font/woff2" };

const stack = new ComposeStack({
  project: "invoice-intake-smoke",
  webPort: 8180,
  accountingPort: 9180,
  log: (message) => console.log(`[compose-smoke] ${message}`),
});

await withStack(stack, async () => {
  const health = await stack.start();
  check(health.export_configured === true, "export should be configured in the compose stack");

  stack.log("checking sign-in: demo accounts listed, nothing readable without a session");
  const demo = await json(`${stack.web}/api/auth/demo-accounts`);
  check(demo.map((a) => a.role).sort().join() === "admin,reviewer,viewer", "one demo account per role");
  check((await fetch(`${stack.web}/api/invoices`)).status === 401, "signed out, the API should answer 401");

  stack.log("checking the dashboard is served, including client-side routes");
  for (const route of ["/", "/invoices/00000000-0000-4000-8000-000000000000"]) {
    const page = await fetch(`${stack.web}${route}`);
    const html = await page.text();
    check(page.ok && html.includes('<div id="root">'), `${route} should serve the app (got ${page.status})`);
  }

  stack.log("checking every built asset is served with the right content type");
  const listed = spawnSync("docker", ["compose", "-p", stack.project, "exec", "-T", "web", "ls", "/usr/share/nginx/html/assets"], {
    cwd: root,
    env: stack.env,
    encoding: "utf8",
  });
  const assets = listed.stdout.split(/\s+/).filter(Boolean);
  check(listed.status === 0 && assets.length > 0, "could not list the built assets");
  for (const asset of assets) {
    const expected = TYPES[asset.split(".").pop()];
    if (!expected) continue;
    const response = await fetch(`${stack.web}/assets/${asset}`);
    const type = response.headers.get("content-type") ?? "";
    check(response.ok && type.includes(expected), `/assets/${asset} served as "${type}" (${response.status})`);
  }

  stack.log("uploading a sample through nginx");
  const form = new FormData();
  form.append("file", new Blob([readFileSync(SAMPLE)], { type: "application/pdf" }), "invoice-007.pdf");
  const uploaded = await stack.api("/invoices", { method: "POST", body: form });
  const ready = await stack.until(uploaded.id, "the upload in needs_review", (i) => i.status === "needs_review");

  stack.log("approving it and waiting for the export");
  await stack.post(`/invoices/${uploaded.id}/approve`, { version: ready.version });
  const exported = await stack.until(uploaded.id, "the invoice exported", (i) => i.status === "exported");
  check(exported.export?.state === "exported", "the export state should be exported");

  const deliveries = await json(`${stack.accounting}/deliveries`);
  const mine = deliveries.filter((delivery) => delivery.idempotency_key === uploaded.id);
  check(mine.length === 1, `expected one delivery for the invoice, got ${mine.length}`);
  check(mine[0].signed === true, "the delivery should be signed (the receiver checked the signature)");
  check(mine[0].payload.approved_by === "sam.rivera", "the payload should name the signed-in approver");

  stack.log("all checks passed");
  return 0;
});
