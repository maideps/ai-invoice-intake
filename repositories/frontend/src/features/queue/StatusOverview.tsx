import { motion } from "motion/react";

import type { Stats } from "@/api/client";
import { Skeleton } from "@/components/ui/skeleton";
import { STATUS_META, STATUSES, TONE_CLASSES, type InvoiceStatus } from "@/lib/status";
import { cn } from "@/lib/utils";

interface Props {
  stats: Stats | undefined;
  active: InvoiceStatus | null;
  onSelect: (status: InvoiceStatus | null) => void;
}

/** A proportion bar of the pipeline, and filter chips that double as the status counts. */
export function StatusOverview({ stats, active, onSelect }: Props) {
  if (!stats) {
    return (
      <div className="space-y-3" aria-busy="true">
        <Skeleton className="h-2 w-full rounded-full" />
        <div className="flex flex-wrap gap-2">
          {Array.from({ length: 5 }, (_, i) => (
            <Skeleton key={i} className="h-8 w-28 rounded-full" />
          ))}
        </div>
      </div>
    );
  }

  const count = (status: InvoiceStatus) => stats.by_status[status] ?? 0;
  return (
    <div className="space-y-3">
      <div
        className="flex h-2 w-full overflow-hidden rounded-full bg-surface-muted"
        role="img"
        aria-label={`${stats.total} invoices: ${STATUSES.filter((s) => count(s) > 0)
          .map((s) => `${count(s)} ${STATUS_META[s].label.toLowerCase()}`)
          .join(", ")}`}
      >
        {STATUSES.map((status) =>
          count(status) > 0 ? (
            <motion.div
              key={status}
              className={cn("h-full", TONE_CLASSES[STATUS_META[status].tone].dot)}
              initial={false}
              animate={{ width: `${(count(status) / stats.total) * 100}%` }}
              transition={{ type: "spring", stiffness: 140, damping: 22 }}
            />
          ) : null,
        )}
      </div>

      <div className="flex flex-wrap gap-2" role="group" aria-label="Filter by status">
        <FilterChip label="All" count={stats.total} pressed={active === null} onClick={() => onSelect(null)} />
        {STATUSES.map((status) => {
          const meta = STATUS_META[status];
          return (
            <FilterChip
              key={status}
              label={meta.label}
              count={count(status)}
              dotClass={TONE_CLASSES[meta.tone].dot}
              pressed={active === status}
              onClick={() => onSelect(active === status ? null : status)}
            />
          );
        })}
      </div>
    </div>
  );
}

function FilterChip(props: {
  label: string;
  count: number;
  pressed: boolean;
  dotClass?: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      aria-pressed={props.pressed}
      onClick={props.onClick}
      className={cn(
        "inline-flex h-8 items-center gap-2 rounded-full border px-3 text-sm transition-colors",
        props.pressed
          ? "border-foreground bg-foreground text-background"
          : "border-border bg-surface text-foreground hover:border-border-strong",
        props.count === 0 && !props.pressed && "text-muted",
      )}
    >
      {props.dotClass && <span className={cn("size-2 rounded-full", props.dotClass)} aria-hidden="true" />}
      {props.label}
      <span className={cn("tabular text-xs", props.pressed ? "text-background/70" : "text-muted")}>
        {props.count}
      </span>
    </button>
  );
}
