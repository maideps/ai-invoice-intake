// Run the docker compose stack as a separate, throwaway project (D-015), for tools that need
// the real packaged product: the smoke test and the README screenshots. Each project gets
// its own ports, containers and volumes, so a stack you are using is never touched.

import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

export const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
export const SAMPLE_COUNT = 12;

export function check(condition, message) {
  if (!condition) throw new Error(message);
}

/** Poll until `probe` returns something truthy; errors count as "not yet". */
export async function eventually(what, probe, timeoutMs = 120_000) {
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

export async function json(url, init) {
  const response = await fetch(url, init);
  const body = await response.json();
  if (!response.ok) throw new Error(`${init?.method ?? "GET"} ${url}: ${response.status} ${JSON.stringify(body)}`);
  return body;
}

export class ComposeStack {
  constructor({ project, webPort, accountingPort, log }) {
    this.project = project;
    this.web = `http://localhost:${webPort}`;
    this.accounting = `http://localhost:${accountingPort}`;
    this.log = log;
    this.env = {
      ...process.env,
      INVOICE_INTAKE_WEB_PORT: String(webPort),
      INVOICE_INTAKE_ACCOUNTING_PORT: String(accountingPort),
    };
  }

  compose(args, options = {}) {
    return spawnSync("docker", ["compose", "-p", this.project, ...args], {
      cwd: root,
      env: this.env,
      stdio: "inherit",
      ...options,
    });
  }

  /** Build, start, and wait until the API answers through nginx and the samples are extracted. */
  async start() {
    if (spawnSync("docker", ["info"], { stdio: "ignore" }).status !== 0) {
      throw new Error("Docker is not running. Start Docker Desktop and rerun.");
    }
    this.stop();
    this.log("building and starting the stack");
    check(this.compose(["up", "--detach", "--build"]).status === 0, "docker compose up failed");
    this.log("waiting for the API through nginx");
    const health = await eventually("GET /api/health", async () => {
      const response = await fetch(`${this.web}/api/health`);
      return response.ok ? response.json() : null;
    });
    this.log(`waiting for the ${SAMPLE_COUNT} seeded samples to be extracted`);
    await eventually("the seeded samples in needs_review", async () => {
      const stats = await json(`${this.web}/api/invoices/stats`);
      return stats.by_status.needs_review === SAMPLE_COUNT ? stats : null;
    });
    return health;
  }

  /** Containers and volumes go; images stay cached for the next run. */
  stop() {
    this.compose(["down", "--volumes", "--remove-orphans"], { stdio: "ignore" });
  }

  logs() {
    this.compose(["logs", "--tail", "40"]);
  }

  api(pathname, init) {
    return json(`${this.web}/api${pathname}`, init);
  }

  /** Wait until the invoice satisfies `ready`, and return it. */
  until(id, what, ready) {
    return eventually(what, async () => {
      const invoice = await this.api(`/invoices/${id}`);
      return ready(invoice) ? invoice : null;
    });
  }

  post(pathname, body, user) {
    return this.api(pathname, {
      method: pathname.endsWith("/fields") ? "PATCH" : "POST",
      body: JSON.stringify(body),
      headers: { "Content-Type": "application/json", "X-User": user },
    });
  }
}

/** Run `main` with the stack, always tearing it down; exits the process with main's code. */
export async function withStack(stack, main) {
  let code = 1;
  const interrupted = () => {
    stack.stop();
    process.exit(130);
  };
  process.on("SIGINT", interrupted);
  try {
    code = await main(stack);
  } catch (error) {
    console.error(`FAIL: ${error.message}`);
    stack.logs();
  } finally {
    stack.log("removing the stack");
    stack.stop();
  }
  process.exit(code);
}
