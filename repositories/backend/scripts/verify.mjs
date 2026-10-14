// The backend repository's own gate (run by `npm run verify-all`, or `node scripts/verify`):
// ruff, ruff format, mypy --strict, pytest and a compile check, with this repository's
// Python. Exits non-zero on the first failure.
//
// Python: $INVOICE_INTAKE_PYTHON, then .venv here (made by `npm run setup:backend` from the
// root). The database and queue tests need Docker running, as in the root `npm run test`.

import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const repo = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

const python =
  process.env.INVOICE_INTAKE_PYTHON ||
  [path.join(repo, ".venv", "bin", "python"), path.join(repo, ".venv", "Scripts", "python.exe")].find(existsSync);
if (!python) {
  console.log("  [FAIL] backend: no .venv; run `npm run setup:backend` from the repository root");
  process.exit(1);
}

const steps = [
  ["lint", ["-m", "ruff", "check", "."]],
  ["format", ["-m", "ruff", "format", "--check", "."]],
  ["typecheck", ["-m", "mypy"]],
  ["test", ["-m", "pytest", "-q"]],
  ["build", ["-m", "compileall", "-q", "src"]],
];

for (const [name, args] of steps) {
  const result = spawnSync(python, args, { cwd: repo, stdio: "inherit" });
  if (result.error || result.status !== 0) {
    console.log(`  [FAIL] backend ${name}`);
    process.exit(1);
  }
  console.log(`  [PASS] backend ${name}`);
}
