/** Numbers follow the viewer's own habits (their browser locale): "1,234.56" or "1.234,56". */
function locale(): string | undefined {
  return typeof navigator === "undefined" ? undefined : navigator.language;
}

/** Words ("5 minutes ago", month names) match the interface, which is in English. */
function uiLanguage(): string {
  return (typeof document === "undefined" ? "" : document.documentElement.lang) || "en";
}

/** Money arrives as a decimal string; it is only turned into a number for display. */
export function formatMoney(amount: string | null, currency: string | null): string {
  if (amount === null) return "—";
  const value = Number(amount);
  if (!Number.isFinite(value)) return amount;
  if (currency === null) {
    return value.toLocaleString(locale(), { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  try {
    return new Intl.NumberFormat(locale(), { style: "currency", currency }).format(value);
  } catch {
    return `${value.toFixed(2)} ${currency}`; // an unknown currency code
  }
}

const UNITS: [Intl.RelativeTimeFormatUnit, number][] = [
  ["year", 365 * 24 * 3600],
  ["month", 30 * 24 * 3600],
  ["week", 7 * 24 * 3600],
  ["day", 24 * 3600],
  ["hour", 3600],
  ["minute", 60],
];

/** "now", "5 minutes ago", "yesterday" … in the viewer's language. */
export function formatRelative(iso: string, now: Date = new Date()): string {
  const seconds = Math.round((new Date(iso).getTime() - now.getTime()) / 1000);
  const format = new Intl.RelativeTimeFormat(uiLanguage(), { numeric: "auto" });
  if (Math.abs(seconds) < 45) return format.format(0, "second");
  for (const [unit, size] of UNITS) {
    if (Math.abs(seconds) >= size) return format.format(Math.round(seconds / size), unit);
  }
  return format.format(Math.round(seconds / 60), "minute");
}

export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString(uiLanguage(), { dateStyle: "medium", timeStyle: "short" });
}

export function initials(name: string): string {
  const parts = name.replace(/@.*/, "").split(/[\s._-]+/).filter(Boolean);
  const letters = parts.length > 1 ? parts[0]![0]! + parts[1]![0]! : (parts[0] ?? "?").slice(0, 2);
  return letters.toUpperCase();
}
