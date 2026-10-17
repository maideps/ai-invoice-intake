import { FileCheck2, LogIn, RefreshCw } from "lucide-react";
import { useId, useState, type FormEvent } from "react";

import { useDemoAccounts, useSignIn } from "@/api/auth";
import { ApiError } from "@/api/client";
import { Button } from "@/components/ui/button";
import { ROLE_META } from "@/lib/roles";

interface Props {
  /** Set when the API could not be reached at all. */
  unreachable?: string;
  onRetry?: () => void;
}

const field =
  "h-10 w-full rounded-lg border border-border-strong bg-surface px-3 text-sm outline-none placeholder:text-muted focus-visible:ring-2 focus-visible:ring-ring";

function sentence(text: string): string {
  const capitalised = text.charAt(0).toUpperCase() + text.slice(1);
  return capitalised.endsWith(".") ? capitalised : `${capitalised}.`;
}

export function SignInPage({ unreachable, onRetry }: Props) {
  const signIn = useSignIn();
  const demo = useDemoAccounts();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const usernameId = useId();
  const passwordId = useId();

  const error = signIn.error;
  const message =
    error instanceof ApiError && error.status === 401
      ? "Wrong username or password."
      : error instanceof ApiError && error.status === 429
        ? sentence(error.message) // "too many failed sign-ins; try again in about 13 minutes" (D-022)
        : error
          ? error.message
          : null;

  function submit(event: FormEvent) {
    event.preventDefault();
    signIn.mutate({ username, password });
  }

  return (
    <main className="flex min-h-dvh items-start justify-center px-4 py-16 sm:items-center sm:py-8">
      <div className="w-full max-w-sm space-y-6">
        <div className="flex items-center gap-2.5 font-semibold tracking-tight">
          <span className="flex size-8 items-center justify-center rounded-lg bg-accent text-accent-foreground">
            <FileCheck2 className="size-4" aria-hidden="true" />
          </span>
          Invoice intake
        </div>

        <section className="rounded-2xl border border-border bg-surface p-6 shadow-sm">
          <h1 className="text-xl font-semibold tracking-tight">Sign in</h1>
          <p className="mt-1 text-sm text-muted">Every upload and decision is recorded under your name.</p>

          {unreachable ? (
            <div role="alert" className="mt-5 space-y-3 text-sm">
              <p>{unreachable}</p>
              <Button onClick={onRetry}>
                <RefreshCw /> Try again
              </Button>
            </div>
          ) : (
            <form onSubmit={submit} className="mt-5 space-y-4">
              <div className="space-y-1.5">
                <label htmlFor={usernameId} className="text-sm font-medium">
                  Username
                </label>
                <input
                  id={usernameId}
                  value={username}
                  onChange={(event) => setUsername(event.target.value)}
                  autoComplete="username"
                  autoCapitalize="none"
                  spellCheck={false}
                  required
                  className={field}
                />
              </div>
              <div className="space-y-1.5">
                <label htmlFor={passwordId} className="text-sm font-medium">
                  Password
                </label>
                <input
                  id={passwordId}
                  type="password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  autoComplete="current-password"
                  required
                  className={field}
                />
              </div>
              {message && (
                <p role="alert" className="text-sm text-[var(--status-bad)]">
                  {message}
                </p>
              )}
              <Button type="submit" variant="primary" className="w-full" disabled={signIn.isPending}>
                <LogIn /> {signIn.isPending ? "Signing in…" : "Sign in"}
              </Button>
            </form>
          )}
        </section>

        {!unreachable && demo.data && demo.data.length > 0 && (
          <section aria-labelledby="demo-heading" className="space-y-3">
            <div>
              <h2 id="demo-heading" className="text-sm font-medium">
                Demo accounts
              </h2>
              <p className="text-xs text-muted">This demo runs on synthetic invoices. Pick a role to try it.</p>
            </div>
            <ul className="divide-y divide-border rounded-2xl border border-border bg-surface">
              {demo.data.map((account) => (
                <li key={account.username} className="flex items-center gap-3 px-4 py-3">
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium">
                      {account.display_name}{" "}
                      <span className="font-normal text-muted">· {ROLE_META[account.role].label}</span>
                    </p>
                    <p className="text-xs text-muted">{ROLE_META[account.role].description}</p>
                    <p className="mt-0.5 font-mono text-xs text-muted">
                      {account.username} / {account.password}
                    </p>
                  </div>
                  <Button
                    size="sm"
                    disabled={signIn.isPending}
                    onClick={() => signIn.mutate({ username: account.username, password: account.password })}
                    aria-label={`Sign in as ${account.display_name} (${ROLE_META[account.role].label})`}
                  >
                    Sign in
                  </Button>
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>
    </main>
  );
}
