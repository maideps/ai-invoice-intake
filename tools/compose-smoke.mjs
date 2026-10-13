#!/usr/bin/env node
// Smoke test of the docker compose stack (D-015): builds and starts it as its own compose
// project on other ports, checks the product works through nginx, then removes everything
// (containers and volumes), also when a check fails.
//
//   node tools/compose-smoke.mjs      (npm run compose:smoke; also a CI job)

import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const PROJECT = "invoice-intake-smoke";
const PORTS = { web: 8180, accounting: 9180 };
const WEB = `http://localhost:${PORTS.web}`;
const SAMPLE = path.join(root, "samples", "invoices", "invoice-007.pdf");
const SAMPLE_COUNT = 12;

const env = {
  ...process.env,
  INVOICE_INTAKE_WEB_PORT: String(PORTS.web),
  INVOICE_INTAKE_ACCOUNTING_PORT: String(PORTS.accounting),
};

function log(message) {
  console.log(`[compose-smoke] ${message}`);
}

function compose(args, options = {}) {
  return spawnSync("docker", ["compose", "-p", PROJECT, ...args], { cwd: root, env, stdio: "inherit", ...options })
    .status;
}

function check(condition, message) {
  if (!condition) throw new Error(message);
}

async function eventually(what, probe, timeoutMs = 120_000) {
  const deadline = Date.now() + timeoutMs;
  let last;
  while (Date.now() < deadline) {
    try {
      last = await probe();
      if (last) return last;
    } catch (error) {
      last = error.message;
    }
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  throw new Error(`timed out waiting for ${what}${last ? ` (last: ${JSON.stringify(last)})` : ""}`);
}

async function json(url, init) {
  const response = await fetch(url, init);
  const body = await response.json();
  if (!response.ok) throw new Error(`${init?.method ?? "GET"} ${url}: ${response.status} ${JSON.stringify(body)}`);
  return body;
}

const invoice = (id) => json(`${WEB}/api/invoices/${id}`);

async function main() {
  if (spawnSync("docker", ["info"], { stdio: "ignore" }).status !== 0) {
    console.error("The compose smoke test needs Docker running. Start Docker Desktop and rerun.");
    return 1;
  }
  compose(["down", "--volumes", "--remove-orphans"], { stdio: "ignore" });

  log("building and starting the stack");
  check(compose(["up", "--detach", "--build"]) === 0, "docker compose up failed");

  log("waiting for the API through nginx");
  const health = await eventually("GET /api/health", async () => {
    const response = await fetch(`${WEB}/api/health`);
    return response.ok ? response.json() : null;
  });
  check(health.export_configured === true, "export should be configured in the compose stack");

  log("checking the dashboard is served, including client-side routes");
  for (const route of ["/", "/invoices/00000000-0000-4000-8000-000000000000"]) {
    const page = await fetch(`${WEB}${route}`);
    const html = await page.text();
    check(page.ok && html.includes('<div id="root">'), `${route} should serve the app (got ${page.status})`);
  }

  log("checking every built asset is served with the right content type");
  const listed = spawnSync("docker", ["compose", "-p", PROJECT, "exec", "-T", "web", "ls", "/usr/share/nginx/html/assets"], {
    cwd: root,
    env,
    encoding: "utf8",
  });
  const assets = listed.stdout.split(/\s+/).filter(Boolean);
  check(listed.status === 0 && assets.length > 0, "could not list the built assets");
  const TYPES = { js: "javascript", mjs: "javascript", css: "text/css", woff2: "font/woff2" };
  for (const asset of assets) {
    const expected = TYPES[asset.split(".").pop()];
    if (!expected) continue;
    const response = await fetch(`${WEB}/assets/${asset}`);
    const type = response.headers.get("content-type") ?? "";
    check(response.ok && type.includes(expected), `/assets/${asset} served as "${type}" (${response.status})`);
  }

  log(`waiting for the ${SAMPLE_COUNT} seeded samples to be extracted`);
  await eventually("the seeded samples in needs_review", async () => {
    const stats = await json(`${WEB}/api/invoices/stats`);
    return stats.by_status.needs_review === SAMPLE_COUNT ? stats : null;
  });

  log("uploading a sample through nginx");
  const form = new FormData();
  form.append("file", new Blob([readFileSync(SAMPLE)], { type: "application/pdf" }), "invoice-007.pdf");
  const uploaded = await json(`${WEB}/api/invoices`, { method: "POST", body: form, headers: { "X-User": "smoke" } });
  const ready = await eventually("the upload in needs_review", async () => {
    const current = await invoice(uploaded.id);
    return current.status === "needs_review" ? current : null;
  });

  log("approving it and waiting for the export");
  await json(`${WEB}/api/invoices/${uploaded.id}/approve`, {
    method: "POST",
    body: JSON.stringify({ version: ready.version }),
    headers: { "Content-Type": "application/json", "X-User": "smoke" },
  });
  const exported = await eventually("the invoice exported", async () => {
    const current = await invoice(uploaded.id);
    return current.status === "exported" ? current : null;
  });
  check(exported.export?.state === "exported", "the export state should be exported");

  const deliveries = await json(`http://localhost:${PORTS.accounting}/deliveries`);
  const mine = deliveries.filter((delivery) => delivery.idempotency_key === uploaded.id);
  check(mine.length === 1, `expected one delivery for the invoice, got ${mine.length}`);
  check(mine[0].signed === true, "the delivery should be signed (the receiver checked the signature)");
  check(mine[0].payload.approved_by === "smoke", "the payload should name the approver");

  log("all checks passed");
  return 0;
}

let code = 1;
try {
  code = await main();
} catch (error) {
  console.error(`[compose-smoke] FAIL: ${error.message}`);
  compose(["logs", "--tail", "40"]);
} finally {
  log("removing the stack");
  compose(["down", "--volumes", "--remove-orphans"], { stdio: "ignore" });
}
process.exit(code);
