import { describe, expect, it } from "vitest";

import { formatMoney, formatRelative, initials } from "./format";

describe("formatMoney", () => {
  it("formats decimal strings in their currency", () => {
    expect(formatMoney("6370.86", "CAD")).toBe("CA$6,370.86");
    expect(formatMoney("3627.23", "EUR")).toBe("€3,627.23");
  });

  it("shows a dash when there is no amount, and plain numbers without a currency", () => {
    expect(formatMoney(null, "EUR")).toBe("—");
    expect(formatMoney("12.5", null)).toBe("12.50");
  });

  it("falls back gracefully for unknown currencies and non-numbers", () => {
    expect(formatMoney("10", "XYZ1")).toBe("10.00 XYZ1");
    expect(formatMoney("lots", "EUR")).toBe("lots");
  });
});

describe("formatRelative", () => {
  const now = new Date("2026-10-13T12:00:00Z");

  it("says now for the last few seconds", () => {
    expect(formatRelative("2026-10-13T11:59:30Z", now)).toBe("now");
  });

  it("uses the largest sensible unit", () => {
    expect(formatRelative("2026-10-13T11:55:00Z", now)).toBe("5 minutes ago");
    expect(formatRelative("2026-10-13T09:00:00Z", now)).toBe("3 hours ago");
    expect(formatRelative("2026-10-12T12:00:00Z", now)).toBe("yesterday");
  });
});

describe("initials", () => {
  it("takes two letters from names and email addresses", () => {
    expect(initials("Maidelin Prieto")).toBe("MP");
    expect(initials("alice.smith@example.com")).toBe("AS");
    expect(initials("bob")).toBe("BO");
  });
});
