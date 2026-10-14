import { AnimatePresence, motion } from "motion/react";

import { STATUS_META, TONE_CLASSES, type InvoiceStatus } from "@/lib/status";
import { cn } from "@/lib/utils";

/** A status pill. When the status changes, the old one slides out and the new one in. */
export function StatusBadge({ status, className }: { status: InvoiceStatus; className?: string }) {
  const meta = STATUS_META[status];
  const tone = TONE_CLASSES[meta.tone];
  const Icon = meta.icon;
  return (
    <span className={cn("relative inline-flex", className)} title={meta.description}>
      <AnimatePresence mode="popLayout" initial={false}>
        <motion.span
          key={status}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -6 }}
          transition={{ duration: 0.2, ease: "easeOut" }}
          className={cn(
            "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium",
            tone.soft,
            tone.text,
          )}
        >
          {meta.inProgress ? (
            <span className="relative flex size-2" aria-hidden="true">
              <span
                className={cn(
                  "absolute inline-flex size-full rounded-full opacity-60 motion-safe:animate-ping",
                  tone.dot,
                )}
              />
              <span className={cn("relative inline-flex size-2 rounded-full", tone.dot)} />
            </span>
          ) : (
            <Icon className="size-3.5" aria-hidden="true" />
          )}
          {meta.label}
        </motion.span>
      </AnimatePresence>
    </span>
  );
}
