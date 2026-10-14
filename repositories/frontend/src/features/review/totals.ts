/**
 * Do the invoice's numbers add up? Checked in exact cents (BigInt), never floats, with half-up
 * rounding as invoices use. A mismatch is a hint for the reviewer, not a reason to block (D-009).
 */

export interface LineValues {
  quantity: string;
  unit_price: string;
  amount: string;
}

export interface TotalsInput {
  subtotal: string | null;
  tax: string | null;
  total: string | null;
  line_items: LineValues[];
}

export type CheckResult =
  | { status: "ok"; label: string }
  | { status: "mismatch"; label: string; expected: string; actual: string }
  | { status: "skipped"; label: string; reason: string };

const SCALE = 4; // fixed-point digits: enough for quantities like 7.5 and prices in cents

/** "1234.5" → 12345000n (value × 10^4). Null for anything that is not a plain decimal. */
function toFixed(value: string | null | undefined): bigint | null {
  const match = /^(-?)(\d+)(?:\.(\d+))?$/.exec(value?.trim() ?? "");
  if (!match) return null;
  const [, sign, whole = "0", fraction = ""] = match;
  if (fraction.length > SCALE) return null;
  const units = BigInt(whole + fraction.padEnd(SCALE, "0"));
  return sign ? -units : units;
}

/** Round a fixed-point value to cents, half away from zero. */
function toCents(fixed: bigint): bigint {
  const divisor = 10n ** BigInt(SCALE - 2);
  const half = divisor / 2n;
  return fixed >= 0n ? (fixed + half) / divisor : -((-fixed + half) / divisor);
}

function money(cents: bigint): string {
  const negative = cents < 0n;
  const digits = (negative ? -cents : cents).toString().padStart(3, "0");
  return `${negative ? "-" : ""}${digits.slice(0, -2)}.${digits.slice(-2)}`;
}

export function checkTotals(input: TotalsInput): CheckResult[] {
  const results: CheckResult[] = [];

  input.line_items.forEach((line, index) => {
    const label = `Line ${index + 1}: quantity × unit price = amount`;
    const quantity = toFixed(line.quantity);
    const price = toFixed(line.unit_price);
    const amount = toFixed(line.amount);
    if (quantity === null || price === null || amount === null) {
      results.push({ status: "skipped", label, reason: "a value is missing or not a number" });
      return;
    }
    const expected = toCents((quantity * price) / 10n ** BigInt(SCALE));
    results.push(compare(label, expected, toCents(amount)));
  });

  const subtotal = toFixed(input.subtotal);
  const lineAmounts = input.line_items.map((line) => toFixed(line.amount));
  if (input.line_items.length > 0) {
    const label = "Lines add up to the subtotal";
    if (subtotal === null || lineAmounts.some((amount) => amount === null)) {
      results.push({ status: "skipped", label, reason: "the subtotal or a line amount is missing" });
    } else {
      const sum = lineAmounts.reduce<bigint>((total, amount) => total + toCents(amount!), 0n);
      results.push(compare(label, sum, toCents(subtotal)));
    }
  }

  const tax = toFixed(input.tax);
  const total = toFixed(input.total);
  const label = "Subtotal plus tax equals the total";
  if (subtotal === null || tax === null || total === null) {
    results.push({ status: "skipped", label, reason: "the subtotal, tax or total is missing" });
  } else {
    results.push(compare(label, toCents(subtotal) + toCents(tax), toCents(total)));
  }
  return results;
}

function compare(label: string, expected: bigint, actual: bigint): CheckResult {
  return expected === actual
    ? { status: "ok", label }
    : { status: "mismatch", label, expected: money(expected), actual: money(actual) };
}
