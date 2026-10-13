#!/usr/bin/env node
// End-to-end tests on the real stack (D-013): throwaway PostgreSQL and Redis containers, the
// API, the worker, the Vite dev server and a local export webhook receiver, then Playwright in
// Chromium.
//
//   node tools/e2e.mjs            (npm run e2e; part of npm run check)
//
// Everything runs on its own ports so it never touches a development database, and everything
// is torn down afterwards, also when a test fails or the run is interrupted.

import { spawn, spawnSync } from "node:child_process";
import { mkdtempSync, openSync } from "node:fs";
import { createServer } from "node:http";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const frontend = path.join(root, "frontend");
const windows = process.platform === "win32";

const PORTS = { postgres: 5434, redis: 6380, api: 8100, web: 5174, webhook: 8101 };
// Synthetic secret for the e2e receiver only; the spec checks the signature with it.
const WEBHOOK_SECRET = "e2e-webhook-secret";
const CONTAINERS = { postgres: "invoice-intake-e2e-postgres", redis: "invoice-intake-e2e-redis" };
const logs = mkdtempSync(path.join(tmpdir(), "invoice-intake-e2e-"));
const children = [];

const backendEnv = {
  ...process.env,
  INVOICE_INTAKE_ENVIRONMENT: "test",
  INVOICE_INTAKE_DATABASE_URL: `postgresql+psycopg://invoice_intake:invoice_intake@localhost:${PORTS.postgres}/invoice_intake`,
  INVOICE_INTAKE_REDIS_URL: `redis://localhost:${PORTS.redis}/0`,
  INVOICE_INTAKE_EXTRACTION_PROVIDER: "fake",
  INVOICE_INTAKE_EXTRACTION_RETRY_BASE_SECONDS: "1",
  INVOICE_INTAKE_WORKER_ID: "e2e",
  INVOICE_INTAKE_EXPORT_WEBHOOK_URL: `http://127.0.0.1:${PORTS.webhook}/invoices`,
  INVOICE_INTAKE_EXPORT_WEBHOOK_SECRET: WEBHOOK_SECRET,
  INVOICE_INTAKE_EXPORT_RETRY_BASE_SECONDS: "1",
};

/**
 * The accounting system's side: accepts POST /invoices and lists what it received at
 * GET /deliveries, so the spec can check what was sent and how often.
 */
const deliveries = [];
const webhook = createServer((request, response) => {
  if (request.method === "GET" && request.url === "/deliveries") {
    response.writeHead(200, { "Content-Type": "application/json" });
    response.end(JSON.stringify(deliveries));
    return;
  }
  const chunks = [];
  request.on("data", (chunk) => chunks.push(chunk));
  request.on("end", () => {
    deliveries.push({ path: request.url, headers: request.headers, body: Buffer.concat(chunks).toString("utf8") });
    response.writeHead(200, { "Content-Type": "text/plain" });
    response.end("ok");
  });
});

function log(message) {
  console.log(`[e2e] ${message}`);
}

/**
 * npm and npx are .cmd scripts on Windows and need a shell; give the shell one quoted command
 * line. Everything else (docker, node, taskkill) runs directly, without a shell.
 */
function command(name, args) {
  if (!windows || !["npm", "npx"].includes(name)) return { file: name, args, shell: false };
  const quoted = args.map((arg) => (/[\s"]/.test(arg) ? `"${arg.replace(/"/g, '\\"')}"` : arg));
  return { file: [name, ...quoted].join(" "), args: [], shell: true };
}

function run(name, args, options = {}) {
  const { file, args: argv, shell } = command(name, args);
  return spawnSync(file, argv, { stdio: "inherit", shell, ...options }).status ?? 1;
}

function runAsync(name, args, options = {}) {
  const { file, args: argv, shell } = command(name, args);
  return new Promise((resolve) => {
    const child = spawn(file, argv, { stdio: "inherit", shell, ...options });
    child.on("error", () => resolve(1));
    child.on("exit", (code) => resolve(code ?? 1));
  });
}

function quiet(name, args) {
  return run(name, args, { stdio: "ignore" });
}

/** Start a long-running process with its output in a log file. */
function start(name, executable, args, options = {}) {
  const file = path.join(logs, `${name}.log`);
  const out = openSync(file, "a");
  const { file: program, args: argv, shell } = command(executable, args);
  const child = spawn(program, argv, {
    stdio: ["ignore", out, out],
    shell,
    detached: !windows, // its own process group, so the whole tree can be stopped
    ...options,
  });
  children.push({ name, child, file });
  return child;
}

/** Stop a process and everything it started (npm → node/python children). */
function stop({ child }) {
  if (child.exitCode !== null || child.pid === undefined) return;
  if (windows) quiet("taskkill", ["/PID", String(child.pid), "/T", "/F"]);
  else {
    try {
      process.kill(-child.pid, "SIGTERM");
    } catch {
      // already gone
    }
  }
}

function removeContainers() {
  quiet("docker", ["rm", "-f", CONTAINERS.postgres, CONTAINERS.redis]);
}

let cleaned = false;
function cleanUp() {
  if (cleaned) return;
  cleaned = true;
  children.forEach(stop);
  webhook.close();
  removeContainers();
}
process.on("SIGINT", () => {
  cleanUp();
  process.exit(130);
});

async function waitFor(what, check, timeoutMs = 60_000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await check()) return;
    const died = children.find(({ child }) => child.exitCode !== null);
    if (died) throw new Error(`${died.name} stopped early; see ${died.file}`);
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error(`timed out waiting for ${what}`);
}

const answers = (url) => () =>
  fetch(url).then(
    (response) => response.status < 500,
    () => false,
  );

async function main() {
  if (quiet("docker", ["info"]) !== 0) {
    console.error("End-to-end tests need Docker running (for PostgreSQL and Redis). Start Docker Desktop and rerun.");
    return 1;
  }
  removeContainers();
  log("starting PostgreSQL and Redis");
  const pg = run("docker", [
    "run", "-d", "--name", CONTAINERS.postgres, "-p", `${PORTS.postgres}:5432`,
    "-e", "POSTGRES_USER=invoice_intake", "-e", "POSTGRES_PASSWORD=invoice_intake",
    "-e", "POSTGRES_DB=invoice_intake", "postgres:16-alpine",
  ], { stdio: "ignore" });
  const redis = run("docker", ["run", "-d", "--name", CONTAINERS.redis, "-p", `${PORTS.redis}:6379`, "redis:7-alpine"], {
    stdio: "ignore",
  });
  if (pg !== 0 || redis !== 0) throw new Error("could not start the containers (are the ports free?)");
  await waitFor("PostgreSQL", () =>
    quiet("docker", ["exec", CONTAINERS.postgres, "pg_isready", "-U", "invoice_intake", "-d", "invoice_intake"]) === 0,
  );
  // pg_isready can answer just before the server accepts the real connection; give it a moment.
  await new Promise((resolve) => setTimeout(resolve, 1000));

  log("applying migrations");
  if (run("node", ["tools/py.mjs", "-m", "alembic", "upgrade", "head"], { cwd: root, env: backendEnv, stdio: "ignore" }) !== 0) {
    throw new Error("migrations failed");
  }

  await new Promise((resolve, reject) => {
    webhook.once("error", reject);
    webhook.listen(PORTS.webhook, "127.0.0.1", resolve);
  });

  log(`starting the API, the worker and the web app (logs in ${logs})`);
  start("api", "node", ["tools/py.mjs", "-m", "uvicorn", "invoice_intake.main:app", "--port", String(PORTS.api)], {
    cwd: root,
    env: backendEnv,
  });
  start("worker", "node", ["tools/py.mjs", "-m", "invoice_intake.worker"], { cwd: root, env: backendEnv });
  start("web", "npm", ["run", "dev", "--", "--port", String(PORTS.web), "--strictPort"], {
    cwd: frontend,
    env: { ...process.env, INVOICE_INTAKE_API_URL: `http://localhost:${PORTS.api}` },
  });
  await waitFor("the API", answers(`http://localhost:${PORTS.api}/health`));
  await waitFor("the web app", answers(`http://localhost:${PORTS.web}/`));

  log("running Playwright");
  // Asynchronously: the webhook receiver lives in this process and must keep answering.
  return runAsync("npx", ["playwright", "test"], {
    cwd: frontend,
    env: {
      ...process.env,
      E2E_BASE_URL: `http://localhost:${PORTS.web}`,
      E2E_WEBHOOK_URL: `http://127.0.0.1:${PORTS.webhook}`,
      E2E_WEBHOOK_SECRET: WEBHOOK_SECRET,
    },
  });
}

let code = 1;
try {
  code = await main();
} catch (error) {
  console.error(`[e2e] ${error.message}`);
  for (const { name, file } of children) console.error(`[e2e] ${name} log: ${file}`);
} finally {
  cleanUp();
}
process.exit(code);
