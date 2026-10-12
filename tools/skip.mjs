#!/usr/bin/env node
// Reports a verification layer as SKIP (not configured) and exits 0.
// A SKIP does not count as verified; it only keeps the `npm run check` chain
// running until the layer has real tests. Usage: node tools/skip.mjs "<reason>"

console.log(`[SKIP] ${process.argv.slice(2).join(" ") || "layer not configured"}`);
console.log("       This layer is not verified until real tests replace this placeholder.");
