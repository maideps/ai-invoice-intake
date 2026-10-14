// @vitest-environment node
import { readFile } from "node:fs/promises";

import openapiTS, { astToString } from "openapi-typescript";
import { expect, it } from "vitest";

// The backend checks contracts/openapi.json against the API; this checks schema.d.ts against it.
it("schema.d.ts is generated from the committed contracts/openapi.json", async () => {
  const spec = new URL("../../../../contracts/openapi.json", import.meta.url);
  const generated = astToString(await openapiTS(spec));
  const committed = await readFile(new URL("./schema.d.ts", import.meta.url), "utf8");

  expect(normalise(committed), "run: npm run api:types").toBe(normalise(generated));
});

/** The CLI adds a banner comment; compare the declarations only. */
function normalise(source: string): string {
  return source
    .replace(/^\/\*\*[\s\S]*?\*\/\s*/, "")
    .replace(/\r\n/g, "\n")
    .trim();
}
