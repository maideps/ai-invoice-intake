import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, ApiError, unwrap, type Account, type DemoAccount, type Role } from "./client";

export const authKeys = {
  me: ["auth", "me"] as const,
  demo: ["auth", "demo-accounts"] as const,
  accounts: ["accounts"] as const,
};

/** Who is signed in: the account, or null when nobody is (a 401 is an answer, not an error). */
export function useMe() {
  return useQuery({
    queryKey: authKeys.me,
    queryFn: async (): Promise<Account | null> => {
      try {
        return await unwrap<Account>(api.GET("/auth/me"));
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) return null;
        throw error;
      }
    },
    staleTime: 60_000,
  });
}

/** The demo accounts, listed on the sign-in page only where the server turns them on. */
export function useDemoAccounts() {
  return useQuery({
    queryKey: authKeys.demo,
    queryFn: () => unwrap<DemoAccount[]>(api.GET("/auth/demo-accounts")),
    staleTime: Infinity,
  });
}

export function useSignIn() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: { username: string; password: string }) =>
      unwrap<Account>(api.POST("/auth/sign-in", { body })),
    onSuccess: (account) => {
      queryClient.removeQueries({ predicate: (query) => query.queryKey[0] !== "auth" });
      queryClient.setQueryData(authKeys.me, account);
    },
  });
}

export function useSignOut() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => unwrap<unknown>(api.POST("/auth/sign-out")),
    onSettled: () => {
      // Whatever the answer, forget everything shown to this account.
      queryClient.removeQueries({ predicate: (query) => query.queryKey[0] !== "auth" });
      queryClient.setQueryData(authKeys.me, null);
    },
  });
}

// Account management (admins only; the API refuses everyone else)

export function useAccounts() {
  return useQuery({
    queryKey: authKeys.accounts,
    queryFn: () => unwrap<Account[]>(api.GET("/accounts")),
  });
}

export interface NewAccount {
  username: string;
  display_name: string;
  role: Role;
  password: string;
}

export function useCreateAccount() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: NewAccount) => unwrap<Account>(api.POST("/accounts", { body })),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: authKeys.accounts }),
  });
}

export interface AccountChange {
  display_name?: string;
  role?: Role;
  active?: boolean;
  password?: string;
}

export function useUpdateAccount() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, change }: { id: string; change: AccountChange }) =>
      unwrap<Account>(
        api.PATCH("/accounts/{account_id}", { params: { path: { account_id: id } }, body: change }),
      ),
    onSuccess: (account) => {
      void queryClient.invalidateQueries({ queryKey: authKeys.accounts });
      // Changing your own account (name, role) shows at once.
      const me = queryClient.getQueryData<Account | null>(authKeys.me);
      if (me?.id === account.id) queryClient.setQueryData(authKeys.me, account);
    },
  });
}
