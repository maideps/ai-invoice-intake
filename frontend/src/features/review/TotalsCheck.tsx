import { CircleCheck, CircleDashed, TriangleAlert } from "lucide-react";

import { cn } from "@/lib/utils";

import { checkTotals, type TotalsInput } from "./totals";

/** Do the numbers add up? Live, from the values being edited. A warning, never a block. */
export function TotalsCheck({ values }: { values: TotalsInput }) {
  const results = checkTotals(values);
  const mismatches = results.filter((result) => result.status === "mismatch").length;
  return (
    <section aria-labelledby="totals-heading" className="rounded-2xl border border-border bg-surface px-5 py-4">
      <div className="mb-2 flex items-center justify-between">
        <h2 id="totals-heading" className="font-medium">
          Totals check
        </h2>
        <span
          className={cn(
            "text-xs",
            mismatches ? "text-[var(--status-review)]" : "text-[var(--status-good)]",
          )}
        >
          {mismatches ? `${mismatches} to look at` : "Everything adds up"}
        </span>
      </div>
      <ul className="space-y-1.5 text-sm">
        {results.map((result) => (
          <li key={result.label} className="flex items-start gap-2">
            {result.status === "ok" ? (
              <CircleCheck className="mt-0.5 size-4 shrink-0 text-[var(--status-good)]" aria-label="Adds up" />
            ) : result.status === "mismatch" ? (
              <TriangleAlert className="mt-0.5 size-4 shrink-0 text-[var(--status-review)]" aria-label="Doesn't add up" />
            ) : (
              <CircleDashed className="mt-0.5 size-4 shrink-0 text-muted" aria-label="Not checked" />
            )}
            <span className={cn(result.status === "skipped" && "text-muted")}>
              {result.label}
              {result.status === "mismatch" && (
                <span className="tabular block text-xs text-muted">
                  Expected {result.expected}, the invoice says {result.actual}
                </span>
              )}
              {result.status === "skipped" && <span className="block text-xs">Not checked: {result.reason}</span>}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
