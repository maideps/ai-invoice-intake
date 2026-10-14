// The frontend repository's own gate (run by `npm run verify-all`, or `node scripts/verify`):
// ESLint, tsc, Vitest and the production build. Exits non-zero on the first failure.
// The Playwright end-to-end tests need the whole stack and run from the root (`npm run e2e`).

import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const repo = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

if (!existsSync(path.join(repo, "node_modules"))) {
  console.log("  [FAIL] frontend: no node_modules; run `npm run setup:frontend` from the repository root");
  process.exit(1);
}

for (const script of ["lint", "typecheck", "test", "build"]) {
  // npm is a .cmd script on Windows and needs a shell; the command line is fixed text.
  const result = spawnSync(`npm run ${script}`, { cwd: repo, stdio: "inherit", shell: true });
  if (result.error || result.status !== 0) {
    console.log(`  [FAIL] frontend ${script}`);
    process.exit(1);
  }
  console.log(`  [PASS] frontend ${script}`);
}
