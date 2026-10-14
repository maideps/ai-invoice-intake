import type { components } from "@/api/schema";

import type { FieldKind } from "./highlight";

type Fields = components["schemas"]["FieldsOut"];

export type HeaderField =
  | "vendor_name"
  | "invoice_number"
  | "issue_date"
  | "due_date"
  | "currency"
  | "subtotal"
  | "tax"
  | "total";

export interface FieldDef {
  name: HeaderField;
  label: string;
  kind: FieldKind;
  input: "text" | "date" | "money" | "currency";
}

export const HEADER_FIELDS: FieldDef[] = [
  { name: "vendor_name", label: "Vendor", kind: "text", input: "text" },
  { name: "invoice_number", label: "Invoice number", kind: "text", input: "text" },
  { name: "issue_date", label: "Issue date", kind: "date", input: "date" },
  { name: "due_date", label: "Due date", kind: "date", input: "date" },
  { name: "currency", label: "Currency", kind: "text", input: "currency" },
  { name: "subtotal", label: "Subtotal", kind: "money", input: "money" },
  { name: "tax", label: "Tax", kind: "money", input: "money" },
  { name: "total", label: "Total", kind: "money", input: "money" },
];

/** Mirrors the backend rule (REQUIRED_FOR_APPROVAL, D-009). */
export const REQUIRED_FOR_APPROVAL: HeaderField[] = [
  "vendor_name",
  "invoice_number",
  "issue_date",
  "currency",
  "total",
];

export interface LineDraft {
  description: string;
  quantity: string;
  unit_price: string;
  amount: string;
}

/** The form's state: every value as the text in its input ("" for empty). */
export type Draft = Record<HeaderField, string> & { line_items: LineDraft[] };

export function draftFrom(fields: Fields): Draft {
  const draft = {} as Draft;
  for (const { name } of HEADER_FIELDS) draft[name] = fields[name] ?? "";
  draft.line_items = fields.line_items.map((line) => ({
    description: line.description,
    quantity: String(line.quantity),
    unit_price: String(line.unit_price),
    amount: String(line.amount),
  }));
  return draft;
}

function normalise(def: FieldDef, value: string): string | null {
  const trimmed = value.trim();
  if (!trimmed) return null;
  if (def.input === "currency") return trimmed.toUpperCase();
  if (def.input === "money") return trimmed.replace(/\s/g, "");
  return trimmed;
}

/** Only what changed, in the API's field format ("" clears a field to null). */
export function patchFrom(saved: Fields, draft: Draft): Record<string, unknown> {
  const patch: Record<string, unknown> = {};
  for (const def of HEADER_FIELDS) {
    const value = normalise(def, draft[def.name]);
    if (value !== (saved[def.name] ?? null)) patch[def.name] = value;
  }
  const lines = draft.line_items.map((line) => ({
    description: line.description.trim(),
    quantity: line.quantity.trim(),
    unit_price: line.unit_price.trim(),
    amount: line.amount.trim(),
  }));
  if (JSON.stringify(lines) !== JSON.stringify(draftFrom(saved).line_items)) {
    patch.line_items = lines;
  }
  return patch;
}

/** What to look for in the document for a focused field key ("total", "line_items.0.amount"). */
export function focusTarget(draft: Draft, key: string | null): { kind: FieldKind; value: string } | null {
  if (!key) return null;
  const header = HEADER_FIELDS.find((def) => def.name === key);
  if (header) return { kind: header.kind, value: draft[header.name] };
  const match = /^line_items\.(\d+)\.(\w+)$/.exec(key);
  const line = match ? draft.line_items[Number(match[1])] : undefined;
  if (!match || !line) return null;
  const column = match[2] as keyof LineDraft;
  const kind: FieldKind = column === "description" ? "text" : column === "quantity" ? "number" : "money";
  return { kind, value: line[column] };
}

export function isDirty(saved: Fields, draft: Draft): boolean {
  return Object.keys(patchFrom(saved, draft)).length > 0;
}

export function missingForApproval(fields: Fields): FieldDef[] {
  return HEADER_FIELDS.filter((def) => REQUIRED_FOR_APPROVAL.includes(def.name) && !fields[def.name]);
}

const FIELD_NAMES = [...HEADER_FIELDS.map((def) => def.name), "line_items"];

/**
 * Sort the API's error messages by the field they are about ("fields.total must be …" → total),
 * so each shows under its input. Anything else goes to "general".
 */
export function errorsByField(errors: string[]): Record<string, string[]> {
  const grouped: Record<string, string[]> = {};
  for (const error of errors) {
    const named = /^fields\.(\w+)/.exec(error)?.[1];
    const mentioned = FIELD_NAMES.find((name) => new RegExp(`\\b${name}\\b`).test(error));
    const key = named && FIELD_NAMES.includes(named) ? named : (mentioned ?? "general");
    (grouped[key] ??= []).push(error);
  }
  return grouped;
}

export type ConfidenceLevel = "high" | "medium" | "low";

export function confidenceLevel(value: number): ConfidenceLevel {
  return value >= 0.9 ? "high" : value >= 0.75 ? "medium" : "low";
}
