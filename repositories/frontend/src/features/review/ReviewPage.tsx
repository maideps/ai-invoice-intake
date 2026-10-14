import { ArrowLeft, Keyboard, RefreshCw, TriangleAlert } from "lucide-react";
import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { toast } from "sonner";

import { ApiError, type Invoice } from "@/api/client";
import {
  useApprove,
  useEditFields,
  useHealth,
  useInvoice,
  useReject,
  useRequestExport,
  useRequestExtraction,
  useReviewQueue,
} from "@/api/queries";
import { useCan } from "@/app/session";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDateTime } from "@/lib/format";

import { AuditTimeline } from "./AuditTimeline";
import { DecisionBar } from "./DecisionBar";
import {
  confidenceLevel,
  draftFrom,
  errorsByField,
  focusTarget,
  HEADER_FIELDS,
  isDirty,
  patchFrom,
  type Draft,
} from "./draft";
import { FieldsEditor } from "./FieldsEditor";
import { candidatesFor } from "./highlight";
import { TotalsCheck } from "./TotalsCheck";

// pdf.js is large: load it only when a review screen opens.
const DocumentViewer = lazy(() => import("./DocumentViewer"));

const SHORTCUTS: [string, string][] = [
  ["J / K", "Next / previous invoice waiting for review"],
  ["E", "Edit: jump to the first field"],
  ["S", "Save changes"],
  ["A", "Approve"],
  ["R", "Reject"],
  ["?", "Show or hide these shortcuts"],
];

export function ReviewPage() {
  const { invoiceId = "" } = useParams();
  const invoice = useInvoice(invoiceId);

  return (
    <div className="space-y-5">
      <Button variant="ghost" size="sm" asChild className="-ml-3">
        <Link to="/">
          <ArrowLeft /> Review queue
        </Link>
      </Button>
      {invoice.isPending ? (
        <div className="grid gap-6 lg:grid-cols-2" aria-busy="true" aria-label="Loading the invoice">
          <Skeleton className="h-[70vh] rounded-2xl" />
          <div className="space-y-4">
            <Skeleton className="h-16 rounded-2xl" />
            <Skeleton className="h-96 rounded-2xl" />
          </div>
        </div>
      ) : invoice.isError ? (
        <div role="alert" className="rounded-2xl border border-border bg-surface p-8 text-center">
          <h1 className="font-medium">Couldn't load this invoice</h1>
          <p className="mt-1 text-sm text-muted">{invoice.error.message}</p>
          <Button className="mt-4" onClick={() => void invoice.refetch()}>
            <RefreshCw /> Try again
          </Button>
        </div>
      ) : (
        <Review invoice={invoice.data} onReload={() => invoice.refetch()} />
      )}
    </div>
  );
}

function Review({ invoice, onReload }: { invoice: Invoice; onReload: () => Promise<unknown> }) {
  const navigate = useNavigate();
  const { draft, setDraft, dirty, changedElsewhere, adopt } = useDraft(invoice);
  const [focusKey, setFocusKey] = useState<string | null>(null);
  const [errors, setErrors] = useState<Record<string, string[]>>({});
  const [conflict, setConflict] = useState(false);
  const [rejectOpen, setRejectOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);

  const edit = useEditFields(invoice.id);
  const approve = useApprove(invoice.id);
  const reject = useReject(invoice.id);
  const retry = useRequestExtraction(invoice.id);
  const retryExport = useRequestExport(invoice.id);
  const health = useHealth();
  const queue = useReviewQueue();
  const busy =
    edit.isPending || approve.isPending || reject.isPending || retry.isPending || retryExport.isPending;
  const canReview = useCan("review");
  const editable = canReview && invoice.status === "needs_review";

  const target = focusTarget(draft, focusKey);
  const highlight = useMemo(
    () => (target ? candidatesFor(target.kind, target.value) : []),
    [target?.kind, target?.value], // eslint-disable-line react-hooks/exhaustive-deps
  );

  /** One place to turn API failures into the right feedback. */
  const failed = useCallback((error: Error, action: string) => {
    if (error instanceof ApiError && error.status === 409) {
      setConflict(true);
    } else if (error instanceof ApiError && error.status === 422) {
      setErrors(errorsByField(error.errors.length ? error.errors : [error.message]));
      toast.error(`Couldn't ${action}`, { description: error.message });
    } else {
      toast.error(`Couldn't ${action}`, { description: error.message });
    }
  }, []);

  const save = useCallback(() => {
    const fields = patchFrom(invoice.fields, draft);
    if (Object.keys(fields).length === 0) return;
    edit.mutate(
      { version: invoice.version, fields },
      {
        onSuccess: (updated) => {
          adopt(updated);
          setErrors({});
          toast.success("Changes saved");
        },
        onError: (error) => failed(error, "save your changes"),
      },
    );
  }, [adopt, draft, edit, failed, invoice]);

  const doApprove = useCallback(() => {
    if (!canReview || invoice.status !== "needs_review") return;
    if (dirty) {
      toast.warning("Save or reset your changes first");
      return;
    }
    approve.mutate(invoice.version, {
      onSuccess: () => toast.success(`${invoice.filename} approved`),
      onError: (error) => failed(error, "approve"),
    });
  }, [approve, canReview, dirty, failed, invoice]);

  const doReject = useCallback(
    (reason: string) =>
      reject.mutate(
        { version: invoice.version, reason },
        {
          onSuccess: () => {
            setRejectOpen(false);
            toast.success(`${invoice.filename} rejected`);
          },
          onError: (error) => {
            setRejectOpen(false);
            failed(error, "reject");
          },
        },
      ),
    [failed, invoice, reject],
  );

  const reload = useCallback(async () => {
    await onReload();
    setConflict(false);
    setErrors({});
  }, [onReload]);

  useEffect(() => {
    if (changedElsewhere) setConflict(true);
  }, [changedElsewhere]);

  // After a reload the latest saved values replace the draft.
  useEffect(() => {
    if (!conflict) adopt(invoice);
  }, [conflict]); // eslint-disable-line react-hooks/exhaustive-deps

  const goToNeighbour = useCallback(
    (step: 1 | -1) => {
      const ids = queue.data ?? [];
      const at = ids.indexOf(invoice.id);
      const next = at === -1 ? ids[0] : ids[at + step];
      if (next) void navigate(`/invoices/${next}`);
      else toast.message(step === 1 ? "No more invoices waiting for review" : "This is the first one");
    },
    [invoice.id, navigate, queue.data],
  );

  const focusField = (name: string) => document.getElementById(`field-${name}`)?.focus();

  const nextLowConfidence = () => {
    const low = HEADER_FIELDS.filter(
      (def) => confidenceLevel(invoice.confidence?.[def.name] ?? 1) === "low",
    ).map((def) => def.name);
    const after = low.findIndex((name) => name === focusKey);
    const next = low[(after + 1) % low.length];
    if (next) focusField(next);
  };

  useShortcuts({
    j: () => goToNeighbour(1),
    k: () => goToNeighbour(-1),
    e: () => editable && focusField("vendor_name"),
    s: () => editable && save(),
    a: doApprove,
    r: () => editable && setRejectOpen(true),
    "?": () => setHelpOpen((open) => !open),
  });

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 space-y-1">
          <h1 className="truncate text-2xl font-semibold tracking-tight">{invoice.filename}</h1>
          <p className="text-sm text-muted">
            Uploaded {formatDateTime(invoice.uploaded_at)} · version {invoice.version}
          </p>
        </div>
        <Button variant="ghost" size="sm" onClick={() => setHelpOpen((open) => !open)} aria-expanded={helpOpen}>
          <Keyboard /> Shortcuts
        </Button>
      </header>

      {helpOpen && (
        <section aria-label="Keyboard shortcuts" className="rounded-2xl border border-border bg-surface px-5 py-4">
          <dl className="grid gap-x-6 gap-y-1.5 text-sm sm:grid-cols-2">
            {SHORTCUTS.map(([keys, action]) => (
              <div key={keys} className="flex gap-3">
                <dt className="w-14 shrink-0">
                  <kbd className="rounded border border-border-strong bg-surface-muted px-1.5 py-0.5 font-mono text-xs">{keys}</kbd>
                </dt>
                <dd className="text-muted">{action}</dd>
              </div>
            ))}
          </dl>
        </section>
      )}

      {conflict && (
        <div
          role="alert"
          className="flex flex-wrap items-center gap-3 rounded-xl border border-[var(--status-review)]/40 bg-[var(--status-review-soft)] px-4 py-3 text-sm"
        >
          <TriangleAlert className="size-4 shrink-0 text-[var(--status-review)]" aria-hidden="true" />
          <span className="flex-1">
            This invoice changed since you opened it, so nothing was saved. Reload to see the latest
            version{dirty ? "; your unsaved edits will be replaced" : ""}.
          </span>
          <Button size="sm" onClick={() => void reload()}>
            <RefreshCw /> Reload
          </Button>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.05fr)_minmax(0,1fr)]">
        <div className="h-[70vh] lg:sticky lg:top-20 lg:h-[calc(100dvh-7rem)]">
          <Suspense fallback={<Skeleton className="h-full rounded-2xl" />}>
            <DocumentViewer invoiceId={invoice.id} highlight={highlight} />
          </Suspense>
        </div>

        <div className="space-y-5">
          <DecisionBar
            invoice={invoice}
            dirty={dirty}
            busy={busy}
            rejectOpen={rejectOpen}
            onRejectOpenChange={setRejectOpen}
            onApprove={doApprove}
            onReject={doReject}
            onRetry={() =>
              retry.mutate(undefined, {
                onSuccess: () => toast.success("Queued for another extraction attempt"),
                onError: (error) => failed(error, "retry"),
              })
            }
            exportConfigured={health.data?.export_configured ?? null}
            canReview={canReview}
            onRetryExport={() =>
              retryExport.mutate(undefined, {
                onSuccess: () => toast.success("Queued for another delivery attempt"),
                onError: (error) => failed(error, "retry the export"),
              })
            }
          />
          <FieldsEditor
            draft={draft}
            onChange={setDraft}
            confidence={invoice.confidence}
            editable={editable}
            dirty={dirty}
            saving={edit.isPending}
            errors={errors}
            onSave={save}
            onReset={() => {
              adopt(invoice);
              setErrors({});
            }}
            onFocusField={setFocusKey}
            onNextLowConfidence={nextLowConfidence}
          />
          <TotalsCheck
            values={{
              subtotal: draft.subtotal || null,
              tax: draft.tax || null,
              total: draft.total || null,
              line_items: draft.line_items,
            }}
          />
          <AuditTimeline events={invoice.events} />
        </div>
      </div>
    </div>
  );
}

/**
 * The form's values. New server data replaces the draft only when the draft has no unsaved
 * edits; otherwise ``changedElsewhere`` is set and the reviewer decides (reload).
 */
function useDraft(invoice: Invoice) {
  const [draft, setDraft] = useState<Draft>(() => draftFrom(invoice.fields));
  const base = useRef({ version: invoice.version, fields: invoice.fields });
  const [changedElsewhere, setChangedElsewhere] = useState(false);

  const adopt = useCallback((latest: Invoice) => {
    base.current = { version: latest.version, fields: latest.fields };
    setDraft(draftFrom(latest.fields));
    setChangedElsewhere(false);
  }, []);

  useEffect(() => {
    if (invoice.version === base.current.version) return;
    if (isDirty(base.current.fields, draft)) setChangedElsewhere(true);
    else adopt(invoice);
  }, [invoice]); // eslint-disable-line react-hooks/exhaustive-deps

  return { draft, setDraft, dirty: isDirty(base.current.fields, draft), changedElsewhere, adopt };
}

/** Single-key shortcuts, ignored while typing or with modifier keys held. */
function useShortcuts(handlers: Record<string, () => unknown>) {
  const latest = useRef(handlers);
  latest.current = handlers;
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.defaultPrevented || event.metaKey || event.ctrlKey || event.altKey) return;
      const target = event.target as HTMLElement | null;
      if (target?.closest("input, textarea, select, [contenteditable='true'], [role='dialog']")) return;
      const handler = latest.current[event.key.toLowerCase()] ?? latest.current[event.key];
      if (!handler) return;
      event.preventDefault();
      handler();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
}
