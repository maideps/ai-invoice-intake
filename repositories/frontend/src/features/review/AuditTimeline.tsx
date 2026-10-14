import { Cog, Pencil, Sparkles, User } from "lucide-react";

import type { Invoice } from "@/api/client";
import { formatDateTime, formatRelative } from "@/lib/format";
import { STATUS_META } from "@/lib/status";

import { HEADER_FIELDS } from "./draft";

type AuditEvent = Invoice["events"][number];

const ACTOR_ICONS = { user: User, ai: Sparkles, system: Cog } as const;
const LABELS: Record<string, string> = { line_items: "the line items" };
for (const def of HEADER_FIELDS) LABELS[def.name] = def.label.toLowerCase();

/** The invoice's history as a story: who did what, when, and what changed. */
export function AuditTimeline({ events }: { events: Invoice["events"] }) {
  return (
    <section aria-labelledby="timeline-heading" className="rounded-2xl border border-border bg-surface px-5 py-4">
      <h2 id="timeline-heading" className="mb-3 font-medium">
        Audit trail
      </h2>
      <ol className="relative space-y-4 border-l border-border pl-5">
        {events.map((event) => {
          const Icon = event.action === "fields_edited" ? Pencil : (ACTOR_ICONS[event.actor_kind as keyof typeof ACTOR_ICONS] ?? Cog);
          return (
            <li key={event.sequence} className="relative text-sm">
              <span
                className="absolute -left-[31px] flex size-5 items-center justify-center rounded-full border border-border bg-surface text-muted"
                aria-hidden="true"
              >
                <Icon className="size-3" />
              </span>
              <p>
                <span className="font-medium">{event.actor_name}</span> {describe(event)}
              </p>
              <EventDetail event={event} />
              <time dateTime={event.occurred_at} title={formatDateTime(event.occurred_at)} className="text-xs text-muted">
                {formatRelative(event.occurred_at)}
              </time>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

function describe(event: AuditEvent): string {
  switch (event.action) {
    case "status_changed":
      if (event.from_status === null) return "uploaded the invoice";
      if (event.to_status === "approved") return "approved it";
      if (event.to_status === "rejected") return "rejected it";
      if (event.to_status === "exported") return "delivered it to the accounting system";
      return event.to_status
        ? `moved it to ${STATUS_META[event.to_status].label.toLowerCase()}`
        : "changed its status";
    case "extraction_recorded": {
      const fields = (event.details?.fields ?? {}) as Record<string, unknown>;
      const filled = Object.entries(fields).filter(([, value]) => value !== null && !(Array.isArray(value) && value.length === 0)).length;
      return `read ${filled} field${filled === 1 ? "" : "s"} from the document`;
    }
    case "extraction_rejected":
      return "returned output that failed the checks";
    case "export_failed": {
      const details = (event.details ?? {}) as { attempt?: number; final?: boolean };
      const last = details.final ? " (no more automatic retries)" : "";
      return `couldn't deliver it, attempt ${details.attempt ?? "?"}${last}`;
    }
    case "fields_edited": {
      const changed = Object.keys(event.details?.changes ?? {});
      return `changed ${changed.map((name) => LABELS[name] ?? name).join(", ")}`;
    }
    default:
      return event.action.replaceAll("_", " ");
  }
}

function EventDetail({ event }: { event: AuditEvent }) {
  if (event.reason) {
    return <p className="mt-0.5 text-xs text-muted">“{event.reason}”</p>;
  }
  if (event.action === "fields_edited") {
    const changes = (event.details?.changes ?? {}) as Record<string, { from: unknown; to: unknown }>;
    return (
      <ul className="mt-1 space-y-0.5 text-xs">
        {Object.entries(changes).map(([name, change]) => (
          <li key={name} className="tabular text-muted">
            {LABELS[name] ?? name}: <del className="opacity-70">{show(change.from)}</del> → <ins className="text-foreground no-underline">{show(change.to)}</ins>
          </li>
        ))}
      </ul>
    );
  }
  if (event.action === "export_failed") {
    const error = event.details?.error;
    return <p className="mt-0.5 text-xs text-muted">{typeof error === "string" ? error : ""}</p>;
  }
  if (event.action === "extraction_rejected") {
    const errors = (event.details?.errors ?? []) as string[];
    return (
      <p className="mt-0.5 text-xs text-muted">
        {errors[0]}
        {errors.length > 1 && ` (and ${errors.length - 1} more)`}
      </p>
    );
  }
  return null;
}

function show(value: unknown): string {
  if (value === null || value === undefined) return "empty";
  if (Array.isArray(value)) return `${value.length} line${value.length === 1 ? "" : "s"}`;
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return `${value}`;
  }
  return JSON.stringify(value);
}
