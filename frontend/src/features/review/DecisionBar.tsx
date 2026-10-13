import { Check, LoaderCircle, RotateCw, X } from "lucide-react";
import { useId, useState, type FormEvent } from "react";

import type { Invoice } from "@/api/client";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { STATUS_META } from "@/lib/status";

import { missingForApproval } from "./draft";

interface Props {
  invoice: Invoice;
  dirty: boolean;
  busy: boolean;
  rejectOpen: boolean;
  onRejectOpenChange: (open: boolean) => void;
  onApprove: () => void;
  onReject: (reason: string) => void;
  onRetry: () => void;
}

/** What can happen next, given the invoice's status. */
export function DecisionBar(props: Props) {
  const { invoice } = props;
  const missing = missingForApproval(invoice.fields);

  return (
    <section aria-label="Decision" className="rounded-2xl border border-border bg-surface px-5 py-4">
      <div className="flex flex-wrap items-center gap-3">
        <StatusBadge status={invoice.status} />
        <span className="flex-1 text-sm text-muted">{STATUS_META[invoice.status].description}</span>
        {invoice.status === "needs_review" && (
          <div className="flex gap-2">
            <RejectButton {...props} />
            <Button variant="primary" onClick={props.onApprove} disabled={props.busy} aria-keyshortcuts="A">
              <Check /> Approve
            </Button>
          </div>
        )}
        {invoice.status === "failed" && (
          <Button onClick={props.onRetry} disabled={props.busy}>
            <RotateCw /> Retry extraction
          </Button>
        )}
        {(invoice.status === "uploaded" || invoice.status === "extracting") && (
          <span className="flex items-center gap-2 text-sm text-muted">
            <LoaderCircle className="size-4 motion-safe:animate-spin" aria-hidden="true" /> Updates on its own
          </span>
        )}
      </div>
      {invoice.status === "needs_review" && (missing.length > 0 || props.dirty) && (
        <p className="mt-3 text-xs text-[var(--status-review)]">
          {props.dirty
            ? "Save or reset your changes before deciding."
            : `Approval needs: ${missing.map((def) => def.label.toLowerCase()).join(", ")}.`}
        </p>
      )}
    </section>
  );
}

function RejectButton({ rejectOpen, onRejectOpenChange, onReject, busy }: Props) {
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const id = useId();

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!reason.trim()) {
      setError("Give a reason, so the next person knows why.");
      return;
    }
    onReject(reason.trim());
  }

  return (
    <Popover
      open={rejectOpen}
      onOpenChange={(open) => {
        onRejectOpenChange(open);
        if (open) setError(null);
      }}
    >
      <PopoverTrigger asChild>
        <Button disabled={busy} aria-keyshortcuts="R">
          <X /> Reject
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-80">
        <form onSubmit={submit} className="space-y-3">
          <label htmlFor={id} className="text-sm font-medium">
            Why are you rejecting it?
          </label>
          <textarea
            id={id}
            value={reason}
            onChange={(event) => {
              setReason(event.target.value);
              setError(null);
            }}
            rows={3}
            placeholder="Duplicate of INV-4410"
            aria-invalid={error ? true : undefined}
            className="w-full resize-none rounded-lg border border-border-strong bg-surface px-3 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
          />
          {error && <p className="text-xs text-[var(--status-bad)]">{error}</p>}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" size="sm" onClick={() => onRejectOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" size="sm" disabled={busy}>
              Reject invoice
            </Button>
          </div>
        </form>
      </PopoverContent>
    </Popover>
  );
}
