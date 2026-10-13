import { Check, CircleCheck, LoaderCircle, RotateCw, Send, TriangleAlert, X } from "lucide-react";
import { useId, useState, type FormEvent } from "react";

import type { Invoice } from "@/api/client";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { formatDateTime, formatRelative } from "@/lib/format";
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
  /** null while unknown (health not loaded yet). */
  exportConfigured: boolean | null;
  onRetryExport: () => void;
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
      {invoice.export && <ExportState {...props} />}
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

/** Where the approved invoice is on its way to the accounting system. */
function ExportState({ invoice, exportConfigured, onRetryExport, busy }: Props) {
  const exp = invoice.export!;
  const tone = "mt-3 flex flex-wrap items-center gap-2 rounded-xl px-3 py-2 text-sm";
  if (exp.state === "exported") {
    return (
      <p className={`${tone} bg-[var(--status-good-soft)] text-[var(--status-good)]`}>
        <CircleCheck className="size-4" aria-hidden="true" />
        Exported to the accounting system{" "}
        {exp.exported_at && (
          <time dateTime={exp.exported_at} title={formatDateTime(exp.exported_at)}>
            {formatRelative(exp.exported_at)}
          </time>
        )}
      </p>
    );
  }
  if (exp.state === "failed") {
    return (
      <div role="alert" className={`${tone} bg-[var(--status-bad-soft)] text-[var(--status-bad)]`}>
        <TriangleAlert className="size-4" aria-hidden="true" />
        <span className="flex-1">
          Export failed after {exp.attempts} attempt{exp.attempts === 1 ? "" : "s"}: {exp.last_error}
        </span>
        <Button size="sm" onClick={onRetryExport} disabled={busy}>
          <RotateCw /> Retry export
        </Button>
      </div>
    );
  }
  if (exp.state === "retrying") {
    return (
      <p className={`${tone} bg-[var(--status-review-soft)] text-[var(--status-review)]`}>
        <TriangleAlert className="size-4" aria-hidden="true" />
        Delivery attempt {exp.attempts} failed: {exp.last_error}. Retrying on its own.
      </p>
    );
  }
  return exportConfigured === false ? (
    <p className={`${tone} bg-surface-muted text-muted`}>
      <Send className="size-4" aria-hidden="true" />
      Waiting to be exported. No export webhook is configured (INVOICE_INTAKE_EXPORT_WEBHOOK_URL).
    </p>
  ) : (
    <p className={`${tone} bg-surface-muted text-muted`}>
      <LoaderCircle className="size-4 motion-safe:animate-spin" aria-hidden="true" />
      Sending to the accounting system…
    </p>
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
