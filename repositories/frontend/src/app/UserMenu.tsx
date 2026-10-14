import { LogOut } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { useSignOut } from "@/api/auth";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { initials } from "@/lib/format";
import { ROLE_META } from "@/lib/roles";

import { useAccount } from "./session";

/** Who is signed in, what their role allows, and signing out. */
export function UserMenu() {
  const account = useAccount();
  const signOut = useSignOut();
  const [open, setOpen] = useState(false);
  const role = ROLE_META[account.role];

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="ghost"
          className="gap-2 px-2"
          aria-label={`Signed in as ${account.display_name} (${role.label})`}
        >
          <span
            className="flex size-7 items-center justify-center rounded-full bg-accent-soft text-xs font-semibold text-accent"
            aria-hidden="true"
          >
            {initials(account.display_name)}
          </span>
          <span className="hidden max-w-36 truncate text-foreground sm:inline">{account.display_name}</span>
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-72">
        <div className="space-y-3">
          <div>
            <p className="font-medium">{account.display_name}</p>
            <p className="font-mono text-xs text-muted">{account.username}</p>
          </div>
          <div className="rounded-lg bg-surface-muted px-3 py-2 text-xs">
            <span className="font-medium">{role.label}</span>
            <span className="text-muted"> · {role.description}</span>
          </div>
          <Button
            className="w-full"
            disabled={signOut.isPending}
            onClick={() =>
              signOut.mutate(undefined, {
                onError: () => toast.message("Signed out on this device"),
              })
            }
          >
            <LogOut /> Sign out
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  );
}
