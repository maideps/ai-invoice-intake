import { describe, expect, it } from "vitest";

import { candidatesFor, markMatches } from "./highlight";
import { checkTotals } from "./totals";

describe("candidatesFor", () => {
  it("covers the ways amounts are printed", () => {
    const forms = candidatesFor("money", "3627.23");
    for (const printed of ["3,627.23", "3.627,23", "3 627,23", "3 627,23", "3627,23", "3627.23"]) {
      expect(forms).toContain(printed);
    }
  });

  it("covers the ways dates are printed", () => {
    const forms = candidatesFor("date", "2026-02-14");
    for (const printed of ["14/02/2026", "14.02.2026", "02/14/2026", "14 February 2026", "February 14, 2026"]) {
      expect(forms).toContain(printed);
    }
  });

  it("puts longer forms first, so the most specific match wins", () => {
    const forms = candidatesFor("money", "1234.50");
    expect(forms[0]!.length).toBeGreaterThanOrEqual(forms.at(-1)!.length);
  });

  it("has nothing to find for an empty value", () => {
    expect(candidatesFor("text", null)).toEqual([]);
    expect(candidatesFor("money", "  ")).toEqual([]);
  });
});

describe("markMatches", () => {
  it("wraps each match in <mark>", () => {
    expect(markMatches("Total à payer 3 627,23 €", candidatesFor("money", "3627.23"))).toBe(
      "Total à payer <mark>3 627,23</mark> €",
    );
    expect(markMatches("N° F2026/3734", ["F2026/3734"])).toBe("N° <mark>F2026/3734</mark>");
  });

  it("matches text case-insensitively", () => {
    expect(markMatches("ATELIER LUMIÈRE", ["Atelier Lumière"])).toBe("<mark>ATELIER LUMIÈRE</mark>");
  });

  it("escapes document text so it cannot inject markup", () => {
    expect(markMatches('<img src=x onerror="1">', [])).toBe("&lt;img src=x onerror=&quot;1&quot;&gt;");
    expect(markMatches("a < b", ["b"])).toBe("a &lt; <mark>b</mark>");
  });

  it("treats candidates literally, not as patterns", () => {
    expect(markMatches("1x2 and 1.2", ["1.2"])).toBe("1x2 and <mark>1.2</mark>");
  });
});

describe("checkTotals", () => {
  const lines = [
    { quantity: "23.5", unit_price: "107.19", amount: "2518.97" }, // 2518.965 rounds half up
    { quantity: "2", unit_price: "100.00", amount: "200.00" },
  ];

  it("passes a consistent invoice, rounding half up in exact cents", () => {
    const results = checkTotals({ subtotal: "2718.97", tax: "516.60", total: "3235.57", line_items: lines });
    expect(results.map((r) => r.status)).toEqual(["ok", "ok", "ok", "ok"]);
  });

  it("reports what was expected when a sum is off", () => {
    const results = checkTotals({ subtotal: "2718.97", tax: "516.60", total: "3253.57", line_items: lines });
    expect(results.at(-1)).toEqual({
      status: "mismatch",
      label: "Subtotal plus tax equals the total",
      expected: "3235.57",
      actual: "3253.57",
    });
  });

  it("flags a line whose amount does not match quantity × price", () => {
    const [line] = checkTotals({
      subtotal: null,
      tax: null,
      total: null,
      line_items: [{ quantity: "3", unit_price: "10.00", amount: "31.00" }],
    });
    expect(line).toMatchObject({ status: "mismatch", expected: "30.00", actual: "31.00" });
  });

  it("skips checks it cannot do instead of guessing", () => {
    const results = checkTotals({ subtotal: null, tax: null, total: "10.00", line_items: [] });
    expect(results).toEqual([
      { status: "skipped", label: "Subtotal plus tax equals the total", reason: "the subtotal, tax or total is missing" },
    ]);
  });
});
