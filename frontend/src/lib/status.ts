import {
  CheckCircle2,
  Clock3,
  Eye,
  Send,
  Sparkles,
  TriangleAlert,
  XCircle,
  type LucideIcon,
} from "lucide-react";

import type { components } from "@/api/schema";

export type InvoiceStatus = components["schemas"]["InvoiceStatus"];

type Tone = "neutral" | "progress" | "review" | "good" | "info" | "bad";

export interface StatusMeta {
  label: string;
  description: string;
  icon: LucideIcon;
  tone: Tone;
  /** The worker is still busy with it: keep refreshing. */
  inProgress: boolean;
}

/** Pipeline order: how an invoice moves through the system. */
export const STATUSES: InvoiceStatus[] = [
  "uploaded",
  "extracting",
  "needs_review",
  "approved",
  "exported",
  "rejected",
  "failed",
];

export const STATUS_META: Record<InvoiceStatus, StatusMeta> = {
  uploaded: {
    label: "Queued",
    description: "Waiting for the extraction worker",
    icon: Clock3,
    tone: "neutral",
    inProgress: true,
  },
  extracting: {
    label: "Extracting",
    description: "The AI is reading the document",
    icon: Sparkles,
    tone: "progress",
    inProgress: true,
  },
  needs_review: {
    label: "Needs review",
    description: "Ready for a person to check",
    icon: Eye,
    tone: "review",
    inProgress: false,
  },
  approved: {
    label: "Approved",
    description: "Approved for export",
    icon: CheckCircle2,
    tone: "good",
    inProgress: false,
  },
  exported: {
    label: "Exported",
    description: "Sent to the accounting system",
    icon: Send,
    tone: "info",
    inProgress: false,
  },
  rejected: {
    label: "Rejected",
    description: "Rejected by a reviewer",
    icon: XCircle,
    tone: "neutral",
    inProgress: false,
  },
  failed: {
    label: "Failed",
    description: "Extraction gave up after its retries",
    icon: TriangleAlert,
    tone: "bad",
    inProgress: false,
  },
};

/** Tailwind classes per tone, built on the status tokens in index.css. */
export const TONE_CLASSES: Record<Tone, { text: string; soft: string; dot: string }> = {
  neutral: {
    text: "text-[var(--status-neutral)]",
    soft: "bg-[var(--status-neutral-soft)]",
    dot: "bg-[var(--status-neutral)]",
  },
  progress: {
    text: "text-[var(--status-progress)]",
    soft: "bg-[var(--status-progress-soft)]",
    dot: "bg-[var(--status-progress)]",
  },
  review: {
    text: "text-[var(--status-review)]",
    soft: "bg-[var(--status-review-soft)]",
    dot: "bg-[var(--status-review)]",
  },
  good: {
    text: "text-[var(--status-good)]",
    soft: "bg-[var(--status-good-soft)]",
    dot: "bg-[var(--status-good)]",
  },
  info: {
    text: "text-[var(--status-info)]",
    soft: "bg-[var(--status-info-soft)]",
    dot: "bg-[var(--status-info)]",
  },
  bad: {
    text: "text-[var(--status-bad)]",
    soft: "bg-[var(--status-bad-soft)]",
    dot: "bg-[var(--status-bad)]",
  },
};

export function isStatus(value: string | null): value is InvoiceStatus {
  return value !== null && (STATUSES as string[]).includes(value);
}
