import { FileUp, LoaderCircle } from "lucide-react";
import { useRef, useState, type DragEvent } from "react";
import { toast } from "sonner";

import { ApiError } from "@/api/client";
import { useUploadInvoice } from "@/api/queries";
import { cn } from "@/lib/utils";

const ACCEPT = "application/pdf,image/png,image/jpeg";

/** Drop or pick invoices; each file is uploaded on its own and reported in a toast. */
export function UploadDropzone({ onUploaded }: { onUploaded: (invoiceId: string) => void }) {
  const upload = useUploadInvoice();
  const input = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [pending, setPending] = useState(0);

  async function send(files: File[]) {
    setPending((n) => n + files.length);
    await Promise.all(
      files.map(async (file) => {
        try {
          const invoice = await upload.mutateAsync(file);
          onUploaded(invoice.id);
          toast.success(`${file.name} uploaded`, { description: "Queued for extraction" });
        } catch (error) {
          const message = error instanceof ApiError ? error.message : "Upload failed";
          toast.error(`Couldn't upload ${file.name}`, { description: message });
        } finally {
          setPending((n) => n - 1);
        }
      }),
    );
  }

  function onDrop(event: DragEvent) {
    event.preventDefault();
    setDragging(false);
    const files = Array.from(event.dataTransfer.files);
    if (files.length) void send(files);
  }

  const busy = pending > 0;
  return (
    <div
      onDragOver={(event) => {
        event.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
      className={cn(
        "group relative flex flex-col items-center justify-center gap-3 rounded-2xl border border-dashed px-6 py-8 text-center transition-colors",
        dragging ? "border-accent bg-accent-soft" : "border-border-strong bg-surface hover:border-accent/60",
      )}
    >
      <span
        className={cn(
          "flex size-11 items-center justify-center rounded-xl transition-colors",
          dragging ? "bg-accent text-accent-foreground" : "bg-surface-muted text-muted group-hover:text-accent",
        )}
        aria-hidden="true"
      >
        {busy ? <LoaderCircle className="size-5 motion-safe:animate-spin" /> : <FileUp className="size-5" />}
      </span>
      <div className="space-y-1">
        <p className="text-sm font-medium">
          {busy ? `Uploading ${pending} file${pending === 1 ? "" : "s"}…` : "Drop invoices here"}
        </p>
        <p className="text-xs text-muted">PDF, PNG or JPEG, up to 10 MB each. Extraction starts right away.</p>
      </div>
      <button
        type="button"
        onClick={() => input.current?.click()}
        className="text-sm font-medium text-accent underline-offset-4 hover:underline"
      >
        Choose files
      </button>
      <input
        ref={input}
        type="file"
        accept={ACCEPT}
        multiple
        className="sr-only"
        aria-label="Upload invoices"
        onChange={(event) => {
          const files = Array.from(event.target.files ?? []);
          event.target.value = "";
          if (files.length) void send(files);
        }}
      />
    </div>
  );
}
