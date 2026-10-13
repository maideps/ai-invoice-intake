import { ArrowLeft, Download } from "lucide-react";
import { Link, useParams } from "react-router";

import { API_BASE } from "@/api/client";
import { useInvoice } from "@/api/queries";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDateTime, formatMoney } from "@/lib/format";

/** A short summary of one invoice. The full review screen (document, fields, decisions) is feat-009. */
export function InvoicePage() {
  const { invoiceId = "" } = useParams();
  const invoice = useInvoice(invoiceId);

  return (
    <div className="space-y-6">
      <Button variant="ghost" size="sm" asChild className="-ml-3">
        <Link to="/">
          <ArrowLeft /> Review queue
        </Link>
      </Button>

      {invoice.isPending ? (
        <div className="space-y-3" aria-busy="true">
          <Skeleton className="h-8 w-72" />
          <Skeleton className="h-4 w-48" />
        </div>
      ) : invoice.isError ? (
        <div role="alert" className="rounded-2xl border border-border bg-surface p-6">
          <h1 className="font-medium">Couldn't load this invoice</h1>
          <p className="text-sm text-muted">{invoice.error.message}</p>
        </div>
      ) : (
        <div className="space-y-6">
          <header className="flex flex-wrap items-start justify-between gap-4">
            <div className="space-y-2">
              <h1 className="text-2xl font-semibold tracking-tight">{invoice.data.filename}</h1>
              <p className="text-sm text-muted">Uploaded {formatDateTime(invoice.data.uploaded_at)}</p>
            </div>
            <StatusBadge status={invoice.data.status} />
          </header>
          <dl className="grid gap-4 rounded-2xl border border-border bg-surface p-6 sm:grid-cols-3">
            <Detail label="Vendor" value={invoice.data.fields.vendor_name ?? "—"} />
            <Detail label="Invoice number" value={invoice.data.fields.invoice_number ?? "—"} />
            <Detail
              label="Total"
              value={formatMoney(invoice.data.fields.total, invoice.data.fields.currency)}
            />
          </dl>
          <div className="flex flex-wrap items-center gap-3 rounded-2xl border border-dashed border-border-strong p-6 text-sm text-muted">
            <span className="flex-1">
              The full review screen, with the document beside editable fields, confidence and decisions, comes next.
            </span>
            <Button asChild size="sm">
              <a href={`${API_BASE}/invoices/${invoice.data.id}/document`} target="_blank" rel="noreferrer">
                <Download /> Original document
              </a>
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div className="space-y-1">
      <dt className="text-xs text-muted">{label}</dt>
      <dd className="tabular font-medium">{value}</dd>
    </div>
  );
}
