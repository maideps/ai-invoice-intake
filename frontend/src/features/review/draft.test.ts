import { describe, expect, it } from "vitest";

import { makeInvoice } from "@/test/server";

import {
  confidenceLevel,
  draftFrom,
  errorsByField,
  focusTarget,
  isDirty,
  missingForApproval,
  patchFrom,
} from "./draft";

const saved = {
  ...makeInvoice().fields,
  line_items: [{ description: "Hours", quantity: "7.5", unit_price: "120.00", amount: "900.00" }],
};

describe("patchFrom", () => {
  it("is empty when nothing changed", () => {
    expect(patchFrom(saved, draftFrom(saved))).toEqual({});
    expect(isDirty(saved, draftFrom(saved))).toBe(false);
  });

  it("sends only the changed fields, normalised", () => {
    const draft = { ...draftFrom(saved), total: " 6 400.00 ", currency: "eur", invoice_number: "" };

    expect(patchFrom(saved, draft)).toEqual({ total: "6400.00", currency: "EUR", invoice_number: null });
  });

  it("sends the whole line item list when any line changed", () => {
    const draft = draftFrom(saved);
    draft.line_items = [...draft.line_items, { description: "Travel", quantity: "1", unit_price: "50", amount: "50" }];

    expect(patchFrom(saved, draft)).toEqual({
      line_items: [
        { description: "Hours", quantity: "7.5", unit_price: "120.00", amount: "900.00" },
        { description: "Travel", quantity: "1", unit_price: "50", amount: "50" },
      ],
    });
  });
});

describe("focusTarget", () => {
  it("finds the value and kind for header fields and line item cells", () => {
    const draft = draftFrom(saved);
    expect(focusTarget(draft, "total")).toEqual({ kind: "money", value: "6370.86" });
    expect(focusTarget(draft, "issue_date")).toEqual({ kind: "date", value: "2026-06-01" });
    expect(focusTarget(draft, "line_items.0.quantity")).toEqual({ kind: "number", value: "7.5" });
    expect(focusTarget(draft, "line_items.0.description")).toEqual({ kind: "text", value: "Hours" });
    expect(focusTarget(draft, "line_items.9.amount")).toBeNull();
    expect(focusTarget(draft, null)).toBeNull();
  });
});

describe("errorsByField", () => {
  it("puts each server error under its field", () => {
    expect(
      errorsByField([
        "fields.total must be a decimal string like '1234.50'",
        "fields.line_items[0].amount must be a decimal string like '1234.50'",
        "fields: due_date must not be before issue_date",
        "something unexpected",
      ]),
    ).toEqual({
      total: ["fields.total must be a decimal string like '1234.50'"],
      line_items: ["fields.line_items[0].amount must be a decimal string like '1234.50'"],
      issue_date: ["fields: due_date must not be before issue_date"],
      general: ["something unexpected"],
    });
  });
});

describe("approval and confidence", () => {
  it("lists the empty fields approval needs", () => {
    const missing = missingForApproval({ ...saved, total: null, currency: null });
    expect(missing.map((def) => def.label)).toEqual(["Currency", "Total"]);
  });

  it("bands confidence", () => {
    expect([0.97, 0.9, 0.8, 0.74, 0].map(confidenceLevel)).toEqual(["high", "high", "medium", "low", "low"]);
  });
});
