import { ChevronLeft, ChevronRight, FileStack, RefreshCw, SearchX, WifiOff } from "lucide-react";
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { useSearchParams } from "react-router";

import { ApiError } from "@/api/client";
import { PAGE_SIZE, useInvoices, useStats } from "@/api/queries";
import { Button } from "@/components/ui/button";
import { isStatus, STATUS_META, type InvoiceStatus } from "@/lib/status";

import { InvoiceList, InvoiceListSkeleton } from "./InvoiceList";
import { StatusOverview } from "./StatusOverview";
import { UploadDropzone } from "./UploadDropzone";

/** How long a fresh upload stays highlighted in the list. */
const HIGHLIGHT_MS = 6000;

export function QueuePage() {
  const [params, setParams] = useSearchParams();
  const status = isStatus(params.get("status")) ? (params.get("status") as InvoiceStatus) : null;
  const page = Math.max(1, Number(params.get("page")) || 1);

  const stats = useStats();
  const invoices = useInvoices(status, page);
  const highlight = useRecentUploads();

  const select = (next: InvoiceStatus | null) =>
    setParams(next ? { status: next } : {}, { replace: false });
  const goTo = (nextPage: number) =>
    setParams({ ...(status ? { status } : {}), ...(nextPage > 1 ? { page: String(nextPage) } : {}) });

  const data = invoices.data;
  const pages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;

  return (
    <div className="space-y-8">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold tracking-tight">Review queue</h1>
          <p className="text-sm text-muted">
            Upload invoices, let the AI read them, then check every result before it's exported.
          </p>
        </div>
      </header>

      <UploadDropzone onUploaded={highlight.add} />

      <section aria-labelledby="queue-heading" className="space-y-4">
        <h2 id="queue-heading" className="sr-only">
          Invoices
        </h2>
        {!(stats.isError && !stats.data) && (
          <StatusOverview stats={stats.data} active={status} onSelect={select} />
        )}
        {invoices.isError && data && (
          <StaleNotice error={invoices.error} onRetry={() => void invoices.refetch()} />
        )}

        {invoices.isPending ? (
          <InvoiceListSkeleton />
        ) : invoices.isError && !data ? (
          <ErrorState error={invoices.error} onRetry={() => void invoices.refetch()} />
        ) : data && data.items.length === 0 ? (
          status ? (
            <EmptyState
              icon={<SearchX className="size-5" />}
              title={`Nothing in ${STATUS_META[status].label}`}
              body="Try another status, or show everything."
              action={<Button onClick={() => select(null)}>Show all invoices</Button>}
            />
          ) : (
            <EmptyState
              icon={<FileStack className="size-5" />}
              title="Upload your first invoice"
              body="Drop a PDF above. The synthetic samples in samples/invoices are a good start."
            />
          )
        ) : data ? (
          <>
            <InvoiceList items={data.items} highlight={highlight.ids} />
            {pages > 1 && (
              <nav className="flex items-center justify-between text-sm" aria-label="Pages">
                <span className="text-muted">
                  Page {page} of {pages} · {data.total} invoices
                </span>
                <div className="flex gap-2">
                  <Button size="sm" onClick={() => goTo(page - 1)} disabled={page <= 1} aria-label="Previous page">
                    <ChevronLeft /> Previous
                  </Button>
                  <Button size="sm" onClick={() => goTo(page + 1)} disabled={page >= pages} aria-label="Next page">
                    Next <ChevronRight />
                  </Button>
                </div>
              </nav>
            )}
          </>
        ) : null}
      </section>
    </div>
  );
}

/** Ids uploaded in this visit, highlighted for a few seconds so new rows are easy to spot. */
function useRecentUploads() {
  const [ids, setIds] = useState<Set<string>>(() => new Set());
  const timers = useRef<number[]>([]);

  const add = useCallback((id: string) => {
    setIds((current) => new Set(current).add(id));
    timers.current.push(
      window.setTimeout(() => {
        setIds((current) => {
          const next = new Set(current);
          next.delete(id);
          return next;
        });
      }, HIGHLIGHT_MS),
    );
  }, []);

  useEffect(() => {
    const pending = timers.current;
    return () => pending.forEach((timer) => window.clearTimeout(timer));
  }, []);

  return { ids, add };
}

function EmptyState(props: { icon: ReactNode; title: string; body: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-2xl border border-border bg-surface px-6 py-14 text-center">
      <span className="flex size-11 items-center justify-center rounded-xl bg-surface-muted text-muted" aria-hidden="true">
        {props.icon}
      </span>
      <div className="space-y-1">
        <h3 className="font-medium">{props.title}</h3>
        <p className="text-sm text-muted">{props.body}</p>
      </div>
      {props.action}
    </div>
  );
}

/** The list on screen is from the last successful load; a refresh just failed. */
function StaleNotice({ error, onRetry }: { error: Error; onRetry: () => void }) {
  return (
    <div
      role="status"
      className="flex flex-wrap items-center gap-3 rounded-xl border border-[var(--status-review-soft)] bg-[var(--status-review-soft)]/50 px-4 py-2.5 text-sm"
    >
      <WifiOff className="size-4 text-[var(--status-review)]" aria-hidden="true" />
      <span className="flex-1">Showing the last loaded list. {error.message}</span>
      <Button size="sm" variant="ghost" onClick={onRetry}>
        <RefreshCw /> Retry
      </Button>
    </div>
  );
}

function ErrorState({ error, onRetry }: { error: Error; onRetry: () => void }) {
  const unreachable = error instanceof ApiError && error.unreachable;
  return (
    <div
      role="alert"
      className="flex flex-col items-center gap-3 rounded-2xl border border-[var(--status-bad-soft)] bg-surface px-6 py-14 text-center"
    >
      <span
        className="flex size-11 items-center justify-center rounded-xl bg-[var(--status-bad-soft)] text-[var(--status-bad)]"
        aria-hidden="true"
      >
        <WifiOff className="size-5" />
      </span>
      <div className="space-y-1">
        <h3 className="font-medium">{unreachable ? "Can't reach the API" : "Couldn't load invoices"}</h3>
        <p className="text-sm text-muted">
          {unreachable ? "Check that the backend is running, then try again." : error.message}
        </p>
      </div>
      <Button onClick={onRetry}>
        <RefreshCw /> Try again
      </Button>
    </div>
  );
}
