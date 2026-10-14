import { ChevronRight, FileText } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { Link } from "react-router";

import type { InvoiceSummary } from "@/api/client";
import { StatusBadge } from "@/components/StatusBadge";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDateTime, formatMoney, formatRelative } from "@/lib/format";
import { cn } from "@/lib/utils";

const GRID = "grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 gap-y-1 sm:grid-cols-[minmax(0,1fr)_9rem_8rem_7rem_1rem]";

export function InvoiceList({ items, highlight }: { items: InvoiceSummary[]; highlight: Set<string> }) {
  return (
    <div className="overflow-hidden rounded-2xl border border-border bg-surface">
      <div className={cn(GRID, "hidden border-b border-border px-5 py-2.5 text-xs font-medium text-muted sm:grid")}>
        <span>Document</span>
        <span>Status</span>
        <span className="text-right">Total</span>
        <span className="text-right">Uploaded</span>
        <span />
      </div>
      <ul>
        <AnimatePresence initial={false}>
          {items.map((invoice) => (
            <motion.li
              key={invoice.id}
              layout
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.25, ease: "easeOut" }}
              className="border-b border-border last:border-b-0"
            >
              <Link
                to={`/invoices/${invoice.id}`}
                className={cn(
                  GRID,
                  "group px-5 py-3.5 transition-colors hover:bg-surface-muted focus-visible:bg-surface-muted",
                  highlight.has(invoice.id) && "bg-accent-soft/60",
                )}
              >
                <span className="flex min-w-0 items-center gap-3">
                  <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-surface-muted text-muted" aria-hidden="true">
                    <FileText className="size-4" />
                  </span>
                  <span className="min-w-0">
                    <span className="block truncate text-sm font-medium">{invoice.filename}</span>
                    <span className="block truncate text-xs text-muted">
                      {invoice.vendor_name ?? (invoice.status === "uploaded" || invoice.status === "extracting"
                        ? "Reading the document…"
                        : "Vendor not found")}
                    </span>
                  </span>
                </span>
                <StatusBadge status={invoice.status} className="justify-self-end sm:justify-self-start" />
                <span className="tabular col-start-1 text-sm sm:col-start-auto sm:text-right">
                  {formatMoney(invoice.total, invoice.currency)}
                </span>
                <time
                  dateTime={invoice.uploaded_at}
                  title={formatDateTime(invoice.uploaded_at)}
                  className="justify-self-end text-xs text-muted sm:text-right"
                >
                  {formatRelative(invoice.uploaded_at)}
                </time>
                <ChevronRight
                  className="hidden size-4 text-muted transition-transform group-hover:translate-x-0.5 sm:block"
                  aria-hidden="true"
                />
              </Link>
            </motion.li>
          ))}
        </AnimatePresence>
      </ul>
    </div>
  );
}

export function InvoiceListSkeleton() {
  return (
    <div className="overflow-hidden rounded-2xl border border-border bg-surface" aria-busy="true" aria-label="Loading invoices">
      {Array.from({ length: 6 }, (_, i) => (
        <div key={i} className="flex items-center gap-4 border-b border-border px-5 py-4 last:border-b-0">
          <Skeleton className="size-9 rounded-lg" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-3.5 w-48" />
            <Skeleton className="h-3 w-32" />
          </div>
          <Skeleton className="h-6 w-24 rounded-full" />
          <Skeleton className="hidden h-3.5 w-20 sm:block" />
        </div>
      ))}
    </div>
  );
}
