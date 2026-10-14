/**
 * Browser storage for per-viewer conveniences (theme). Storage can be
 * missing or throw (private windows, blocked site data), so every access is guarded and the
 * app works without it.
 */
const PREFIX = "invoice-intake:";

export function readSetting(key: string): string | null {
  try {
    return window.localStorage.getItem(PREFIX + key);
  } catch {
    return null;
  }
}

export function writeSetting(key: string, value: string | null): void {
  try {
    if (value === null) window.localStorage.removeItem(PREFIX + key);
    else window.localStorage.setItem(PREFIX + key, value);
  } catch {
    // Not saved; the setting still applies for this visit.
  }
}
