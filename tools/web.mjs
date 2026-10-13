#!/usr/bin/env node
// Runs the frontend's npm scripts from the repository root, the way tools/py.mjs runs the backend.
//
//   node tools/web.mjs setup        install frontend/ dependencies (npm ci) and Playwright's Chromium
//   node tools/web.mjs <script>     run a frontend/package.json script (lint, typecheck, test, build, dev)
//
// The harness gates (npm run lint / typecheck / test / build) call this launcher, so a missing
// install or a too-old Node says so plainly instead of failing deep inside a tool.

import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const frontend = path.join(root, "frontend");
const MIN_NODE = [20, 19];

function nodeIsRecentEnough() {
  const [major, minor] = process.versions.node.split(".").map(Number);
  return major > MIN_NODE[0] || (major === MIN_NODE[0] && minor >= MIN_NODE[1]);
}

function npm(args) {
  const result = spawnSync("npm", args, {
    cwd: frontend,
    stdio: "inherit",
    shell: process.platform === "win32", // npm is npm.cmd on Windows
  });
  return result.status ?? 1;
}

const [command, ...rest] = process.argv.slice(2);
if (!command) {
  console.error("usage: node tools/web.mjs setup | <frontend npm script>");
  process.exit(2);
}
if (!nodeIsRecentEnough()) {
  console.error(
    `The frontend needs Node ${MIN_NODE.join(".")} or newer (Vite 7); this is Node ${process.versions.node}.`,
  );
  process.exit(1);
}
if (command === "setup") {
  const installed = npm(["ci", "--no-audit", "--no-fund"]);
  // The end-to-end tests drive Chromium; Playwright downloads its own build once.
  process.exit(installed === 0 ? npm(["exec", "--", "playwright", "install", "chromium"]) : installed);
}
if (!existsSync(path.join(frontend, "node_modules"))) {
  console.error("Frontend dependencies are not installed. Run: npm run setup:frontend");
  process.exit(1);
}
process.exit(npm(["run", "--silent", command, ...(rest.length ? ["--", ...rest] : [])]));
