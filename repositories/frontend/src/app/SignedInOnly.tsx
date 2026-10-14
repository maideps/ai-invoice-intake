import { useQueryClient } from "@tanstack/react-query";
import { useEffect, type ReactNode } from "react";

import { authKeys, useMe } from "@/api/auth";
import { onSignedOut } from "@/api/client";
import { Skeleton } from "@/components/ui/skeleton";
import { SignInPage } from "@/features/auth/SignInPage";

import { SessionContext } from "./session";

/** Shows the app to a signed-in account, and the sign-in page to everyone else. */
export function SignedInOnly({ children }: { children: ReactNode }) {
  const me = useMe();
  const queryClient = useQueryClient();

  // A 401 anywhere means the session ended (expired, signed out elsewhere, account deactivated).
  useEffect(
    () =>
      onSignedOut(() => {
        if (queryClient.getQueryData(authKeys.me)) {
          queryClient.removeQueries({ predicate: (query) => query.queryKey[0] !== "auth" });
          queryClient.setQueryData(authKeys.me, null);
        }
      }),
    [queryClient],
  );

  if (me.isPending) {
    return (
      <div className="mx-auto max-w-sm space-y-3 px-4 py-24" aria-busy="true" aria-label="Loading">
        <Skeleton className="h-8 w-40" />
        <Skeleton className="h-48 rounded-2xl" />
      </div>
    );
  }
  if (me.isError) {
    // No answer at all (the API is down): the sign-in page says so and offers a retry.
    return <SignInPage unreachable={me.error.message} onRetry={() => void me.refetch()} />;
  }
  if (!me.data) return <SignInPage />;
  return <SessionContext.Provider value={me.data}>{children}</SessionContext.Provider>;
}
