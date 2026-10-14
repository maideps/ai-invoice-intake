import { createContext, useContext } from "react";

import type { Account, Permission } from "@/api/client";

export const SessionContext = createContext<Account | null>(null);

/** The signed-in account. Only used below <SignedInOnly>, where there always is one. */
export function useAccount(): Account {
  const account = useContext(SessionContext);
  if (!account) throw new Error("useAccount() needs <SignedInOnly> above it");
  return account;
}

/** Whether the signed-in account's role allows this. The API checks it again on every request;
 * the UI uses it to show only what someone can actually do. */
export function useCan(permission: Permission): boolean {
  return useAccount().permissions.includes(permission);
}
