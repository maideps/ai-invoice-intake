import { useSyncExternalStore } from "react";

import { readSetting, writeSetting } from "./storage";

/**
 * Who is using the dashboard. There is no login yet (a non-goal for the first version): the
 * name is sent as the `X-User` header, which the API records in the audit trail.
 */
const KEY = "acting-as";
const listeners = new Set<() => void>();
let current: string | null = readSetting(KEY);

export const MAX_NAME_LENGTH = 100;

export function getActingAs(): string | null {
  return current;
}

export function setActingAs(name: string | null): void {
  const cleaned = name?.trim().slice(0, MAX_NAME_LENGTH) || null;
  current = cleaned;
  writeSetting(KEY, cleaned);
  listeners.forEach((listener) => listener());
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function useActingAs(): string | null {
  return useSyncExternalStore(subscribe, getActingAs, getActingAs);
}
