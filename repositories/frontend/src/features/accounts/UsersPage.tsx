import { KeyRound, RefreshCw, UserPlus } from "lucide-react";
import { useId, useState, type FormEvent } from "react";
import { toast } from "sonner";

import { useAccounts, useCreateAccount, useUpdateAccount, type AccountChange, type NewAccount } from "@/api/auth";
import { ApiError, type Account, type Role } from "@/api/client";
import { useAccount, useCan } from "@/app/session";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Skeleton } from "@/components/ui/skeleton";
import { initials } from "@/lib/format";
import { ROLE_META, ROLES } from "@/lib/roles";
import { cn } from "@/lib/utils";

const input =
  "h-9 w-full rounded-lg border border-border-strong bg-surface px-3 text-sm outline-none placeholder:text-muted focus-visible:ring-2 focus-visible:ring-ring";

/** What went wrong, in one line: the server's reasons when it gave some. */
function reason(error: Error): string {
  return error instanceof ApiError && error.errors.length ? error.errors.join("; ") : error.message;
}

export function UsersPage() {
  const isAdmin = useCan("manage_accounts");
  if (!isAdmin) {
    return (
      <div role="alert" className="rounded-2xl border border-border bg-surface p-8 text-center">
        <h1 className="font-medium">Only admins manage accounts</h1>
        <p className="mt-1 text-sm text-muted">Ask an admin if you need another role.</p>
      </div>
    );
  }
  return <Users />;
}

function Users() {
  const accounts = useAccounts();

  return (
    <div className="space-y-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">Users</h1>
        <p className="text-sm text-muted">
          Who can sign in, and what they can do. Every upload and decision is recorded under the
          person's username.
        </p>
      </header>

      <AddAccount />

      <section aria-label="Accounts" className="overflow-hidden rounded-2xl border border-border bg-surface">
        {accounts.isPending ? (
          <div className="space-y-2 p-4" aria-busy="true">
            <Skeleton className="h-12" />
            <Skeleton className="h-12" />
          </div>
        ) : accounts.isError ? (
          <div role="alert" className="p-8 text-center text-sm">
            <p>{accounts.error.message}</p>
            <Button className="mt-3" onClick={() => void accounts.refetch()}>
              <RefreshCw /> Try again
            </Button>
          </div>
        ) : (
          <ul className="divide-y divide-border">
            {accounts.data.map((account) => (
              <AccountRow key={account.id} account={account} />
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

const EMPTY: NewAccount = { username: "", display_name: "", role: "reviewer", password: "" };

function AddAccount() {
  const create = useCreateAccount();
  const [draft, setDraft] = useState<NewAccount>(EMPTY);
  const ids = { username: useId(), name: useId(), role: useId(), password: useId() };
  const set = (change: Partial<NewAccount>) => setDraft((current) => ({ ...current, ...change }));

  function submit(event: FormEvent) {
    event.preventDefault();
    create.mutate(draft, {
      onSuccess: (account) => {
        toast.success(`Added ${account.display_name}`, {
          description: `They sign in as ${account.username} with the starting password you chose.`,
        });
        setDraft(EMPTY);
      },
    });
  }

  return (
    <section aria-labelledby="add-heading" className="rounded-2xl border border-border bg-surface px-5 py-4">
      <h2 id="add-heading" className="mb-3 font-medium">
        Add an account
      </h2>
      <form onSubmit={submit} className="grid gap-3 sm:grid-cols-2 lg:grid-cols-[1fr_1fr_10rem_1fr_auto] lg:items-end">
        <div className="space-y-1">
          <label htmlFor={ids.username} className="text-xs font-medium text-muted">
            Username
          </label>
          <input
            id={ids.username}
            value={draft.username}
            onChange={(event) => set({ username: event.target.value })}
            placeholder="kim.lee"
            autoCapitalize="none"
            spellCheck={false}
            required
            className={input}
          />
        </div>
        <div className="space-y-1">
          <label htmlFor={ids.name} className="text-xs font-medium text-muted">
            Display name
          </label>
          <input
            id={ids.name}
            value={draft.display_name}
            onChange={(event) => set({ display_name: event.target.value })}
            placeholder="Kim Lee"
            required
            className={input}
          />
        </div>
        <div className="space-y-1">
          <label htmlFor={ids.role} className="text-xs font-medium text-muted">
            Role
          </label>
          <select
            id={ids.role}
            value={draft.role}
            onChange={(event) => set({ role: event.target.value as Role })}
            className={input}
          >
            {ROLES.map((role) => (
              <option key={role} value={role}>
                {ROLE_META[role].label}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-1">
          <label htmlFor={ids.password} className="text-xs font-medium text-muted">
            Starting password
          </label>
          <input
            id={ids.password}
            type="password"
            value={draft.password}
            onChange={(event) => set({ password: event.target.value })}
            placeholder="At least 10 characters"
            autoComplete="new-password"
            required
            className={input}
          />
        </div>
        <Button type="submit" variant="primary" disabled={create.isPending}>
          <UserPlus /> Add
        </Button>
      </form>
      {create.error && (
        <p role="alert" className="mt-3 text-sm text-[var(--status-bad)]">
          Couldn't add the account: {reason(create.error)}
        </p>
      )}
    </section>
  );
}

function AccountRow({ account }: { account: Account }) {
  const me = useAccount();
  const update = useUpdateAccount();
  const roleId = useId();
  const isMe = account.id === me.id;

  function change(changeSet: AccountChange, done: string) {
    update.mutate(
      { id: account.id, change: changeSet },
      {
        onSuccess: () => toast.success(done),
        onError: (error) => toast.error(`Couldn't change ${account.display_name}`, { description: reason(error) }),
      },
    );
  }

  return (
    <li className={cn("flex flex-wrap items-center gap-3 px-5 py-3", !account.active && "opacity-60")}>
      <span
        className="flex size-9 shrink-0 items-center justify-center rounded-full bg-accent-soft text-xs font-semibold text-accent"
        aria-hidden="true"
      >
        {initials(account.display_name)}
      </span>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium">
          {account.display_name}
          {isMe && <span className="font-normal text-muted"> (you)</span>}
          {!account.active && (
            <span className="ml-2 rounded-md bg-surface-muted px-1.5 py-0.5 text-xs font-normal text-muted">
              Inactive
            </span>
          )}
        </p>
        <p className="truncate font-mono text-xs text-muted">{account.username}</p>
      </div>
      <label htmlFor={roleId} className="sr-only">
        Role for {account.display_name}
      </label>
      <select
        id={roleId}
        value={account.role}
        disabled={update.isPending}
        onChange={(event) => {
          const role = event.target.value as Role;
          change({ role }, `${account.display_name} is now ${ROLE_META[role].label.toLowerCase()}`);
        }}
        className={cn(input, "w-32")}
      >
        {ROLES.map((role) => (
          <option key={role} value={role}>
            {ROLE_META[role].label}
          </option>
        ))}
      </select>
      <SetPassword account={account} onSave={(password) => change({ password }, `New password set for ${account.display_name}`)} />
      <Button
        size="sm"
        variant="ghost"
        disabled={update.isPending}
        onClick={() =>
          change(
            { active: !account.active },
            account.active
              ? `${account.display_name} can no longer sign in`
              : `${account.display_name} can sign in again`,
          )
        }
      >
        {account.active ? "Deactivate" : "Reactivate"}
      </Button>
    </li>
  );
}

function SetPassword({ account, onSave }: { account: Account; onSave: (password: string) => void }) {
  const [open, setOpen] = useState(false);
  const [password, setPassword] = useState("");
  const id = useId();

  return (
    <Popover
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        setPassword("");
      }}
    >
      <PopoverTrigger asChild>
        <Button size="sm" variant="ghost" aria-label={`Set a password for ${account.display_name}`}>
          <KeyRound /> Password
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-72">
        <form
          onSubmit={(event) => {
            event.preventDefault();
            onSave(password);
            setOpen(false);
          }}
          className="space-y-3"
        >
          <div className="space-y-1">
            <label htmlFor={id} className="text-sm font-medium">
              New password for {account.display_name}
            </label>
            <p className="text-xs text-muted">They are signed out everywhere and use this one next.</p>
          </div>
          <input
            id={id}
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete="new-password"
            minLength={10}
            required
            className={input}
          />
          <div className="flex justify-end">
            <Button type="submit" variant="primary" size="sm">
              Set password
            </Button>
          </div>
        </form>
      </PopoverContent>
    </Popover>
  );
}
