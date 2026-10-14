#!/usr/bin/env node
// Checks that the project's documentation points at things that exist (part of npm run lint):
//
// - every relative link and image resolves to a file in the repository
// - every #anchor matches a heading in its target document (with GitHub's heading ids)
// - every `npm run <script>` mentioned exists in the root package.json
//
// Links to other sites are not fetched: the check runs offline and gives the same answer
// every time.

import { existsSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const DOCS = ["README.md", "docs/ARCHITECTURE.md", "docs/PRODUCT.md", "samples/README.md"];
const scripts = new Set(Object.keys(JSON.parse(readFileSync(path.join(root, "package.json"), "utf8")).scripts));

/** GitHub's id for a heading: lower case, punctuation dropped, spaces to hyphens, -1 for repeats. */
function headingIds(markdown) {
  const ids = new Set();
  const seen = new Map();
  for (const line of withoutCodeBlocks(markdown).split("\n")) {
    const heading = /^#{1,6}\s+(.+?)\s*#*\s*$/.exec(line);
    if (!heading) continue;
    const text = heading[1].replace(/`/g, "").replace(/\[([^\]]*)\]\([^)]*\)/g, "$1");
    const base = text
      .toLowerCase()
      .replace(/[^\p{L}\p{N}\s_-]/gu, "")
      .replace(/\s/g, "-");
    const count = seen.get(base) ?? 0;
    seen.set(base, count + 1);
    ids.add(count ? `${base}-${count}` : base);
  }
  return ids;
}

function withoutCodeBlocks(markdown) {
  return markdown.replace(/^(```|~~~)[\s\S]*?^\1/gm, "");
}

function links(markdown) {
  const prose = withoutCodeBlocks(markdown).replace(/`[^`\n]*`/g, "");
  const found = [];
  for (const match of prose.matchAll(/!?\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+"[^"]*")?\s*\)/g)) found.push(match[1]);
  for (const match of prose.matchAll(/<img\s[^>]*src="([^"]+)"/g)) found.push(match[1]);
  return found;
}

const problems = [];
const idsCache = new Map();
const idsOf = (file) => {
  if (!idsCache.has(file)) idsCache.set(file, headingIds(readFileSync(file, "utf8")));
  return idsCache.get(file);
};

for (const doc of DOCS) {
  const file = path.join(root, doc);
  const markdown = readFileSync(file, "utf8");

  for (const target of links(markdown)) {
    if (/^[a-z][a-z0-9+.-]*:/i.test(target)) continue; // https:, mailto: and the like
    const [rawPath, anchor] = target.split("#");
    const resolved = rawPath ? path.resolve(path.dirname(file), decodeURIComponent(rawPath)) : file;
    if (!existsSync(resolved)) {
      problems.push(`${doc}: link to a missing file: ${target}`);
      continue;
    }
    if (anchor && resolved.endsWith(".md") && statSync(resolved).isFile() && !idsOf(resolved).has(anchor)) {
      problems.push(`${doc}: no heading for the anchor: ${target}`);
    }
  }

  for (const match of markdown.matchAll(/npm run ([\w:-]+)/g)) {
    if (!scripts.has(match[1])) problems.push(`${doc}: mentions \`npm run ${match[1]}\`, which package.json does not define`);
  }
}

if (problems.length) {
  for (const problem of problems) console.error(`[check-docs] ${problem}`);
  process.exit(1);
}
console.log(`[check-docs] ${DOCS.length} documents: links, anchors and npm scripts all resolve`);
