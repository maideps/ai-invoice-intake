/**
 * Find a field's value in the PDF's text layer. The extraction gives values, not positions, so
 * this searches the text for the ways the value is likely printed: invoices write amounts and
 * dates in local formats ("3 627,23", "14.02.2026") while fields hold normalised values.
 */

export type FieldKind = "text" | "number" | "money" | "date";

const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

/** How ``value`` might appear in the document, longest first. Empty when there is nothing to find. */
export function candidatesFor(kind: FieldKind, value: string | null | undefined): string[] {
  const trimmed = value?.trim();
  if (!trimmed) return [];
  const found =
    kind === "money"
      ? moneyForms(trimmed)
      : kind === "date"
        ? dateForms(trimmed)
        : kind === "number"
          ? [trimmed, trimmed.replace(".", ",")] // a quantity: 7.5 or 7,5
          : [trimmed];
  return [...new Set(found)].sort((a, b) => b.length - a.length);
}

function moneyForms(value: string): string[] {
  const match = /^(-?)(\d+)(?:\.(\d+))?$/.exec(value);
  if (!match) return [value];
  const [, sign = "", whole = "", fraction] = match;
  const cents = fraction === undefined ? "" : fraction.padEnd(2, "0");
  const groups = (separator: string) => whole.replace(/\B(?=(\d{3})+(?!\d))/g, separator);
  const forms = [value];
  for (const [group, decimal] of [
    [",", "."], // 1,234.56
    [".", ","], // 1.234,56
    [" ", ","], // 1 234,56
    [" ", ","], // 1 234,56 with a no-break space
    [" ", ","], // 1 234,56 with a narrow no-break space
    ["", ","], // 1234,56
    ["", "."], // 1234.56
  ] as const) {
    forms.push(sign + groups(group) + (cents ? decimal + cents : ""));
  }
  return forms;
}

function dateForms(value: string): string[] {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) return [value];
  const [, year = "", month = "", day = ""] = match;
  const monthName = MONTHS[Number(month) - 1] ?? "";
  const plainDay = String(Number(day));
  return [
    value,
    `${day}/${month}/${year}`,
    `${day}.${month}.${year}`,
    `${month}/${day}/${year}`,
    `${day}-${month}-${year}`,
    `${day} ${monthName} ${year}`,
    `${plainDay} ${monthName} ${year}`,
    `${monthName} ${day}, ${year}`,
    `${monthName} ${plainDay}, ${year}`,
  ];
}

const ESCAPES: Record<string, string> = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };

function escapeHtml(text: string): string {
  return text.replace(/[&<>"']/g, (char) => ESCAPES[char]!);
}

function escapeRegExp(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/**
 * The text item as HTML, with every occurrence of a candidate wrapped in <mark>. Everything
 * else is escaped, so document text can never inject markup.
 */
export function markMatches(text: string, candidates: string[]): string {
  if (candidates.length === 0) return escapeHtml(text);
  const pattern = new RegExp(candidates.map(escapeRegExp).join("|"), "gi");
  let html = "";
  let last = 0;
  for (const match of text.matchAll(pattern)) {
    const start = match.index;
    html += escapeHtml(text.slice(last, start)) + `<mark>${escapeHtml(match[0])}</mark>`;
    last = start + match[0].length;
  }
  return html + escapeHtml(text.slice(last));
}
