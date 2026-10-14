import { useId, useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { initials } from "@/lib/format";
import { MAX_NAME_LENGTH, setActingAs, useActingAs } from "@/lib/identity";

/** Choose the name recorded in the audit trail for your uploads and decisions. */
export function ActingAsPicker() {
  const name = useActingAs();
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState(name ?? "");
  const inputId = useId();

  function save(event: FormEvent) {
    event.preventDefault();
    setActingAs(draft);
    setOpen(false);
  }

  return (
    <Popover
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (next) setDraft(name ?? "");
      }}
    >
      <PopoverTrigger asChild>
        <Button variant="ghost" className="gap-2 px-2" aria-label={`Acting as ${name ?? "anonymous"}`}>
          <span
            className="flex size-7 items-center justify-center rounded-full bg-accent-soft text-xs font-semibold text-accent"
            aria-hidden="true"
          >
            {name ? initials(name) : "?"}
          </span>
          <span className="hidden max-w-36 truncate text-foreground sm:inline">{name ?? "Anonymous"}</span>
        </Button>
      </PopoverTrigger>
      <PopoverContent>
        <form onSubmit={save} className="space-y-3">
          <div className="space-y-1">
            <label htmlFor={inputId} className="text-sm font-medium">
              Acting as
            </label>
            <p className="text-xs text-muted">
              Recorded in the audit trail for your uploads and decisions. There's no sign-in yet.
            </p>
          </div>
          <input
            id={inputId}
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            maxLength={MAX_NAME_LENGTH}
            placeholder="alex@company.com"
            className="h-9 w-full rounded-lg border border-border-strong bg-surface px-3 text-sm outline-none placeholder:text-muted focus-visible:ring-2 focus-visible:ring-ring"
          />
          <div className="flex justify-end gap-2">
            {name && (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => {
                  setActingAs(null);
                  setOpen(false);
                }}
              >
                Clear
              </Button>
            )}
            <Button type="submit" variant="primary" size="sm">
              Save
            </Button>
          </div>
        </form>
      </PopoverContent>
    </Popover>
  );
}
