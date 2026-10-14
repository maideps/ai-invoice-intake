import "react-pdf/dist/Page/TextLayer.css";

import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, ExternalLink, ZoomIn, ZoomOut } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";

import { API_BASE } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

import { markMatches } from "./highlight";

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  "pdfjs-dist/build/pdf.worker.min.mjs",
  import.meta.url,
).toString();

const ZOOMS = [0.75, 1, 1.25, 1.5, 2];

interface Props {
  invoiceId: string;
  /** Text to highlight in the document (the focused field's value, in its likely printed forms). */
  highlight: string[];
}

/** The original document: a PDF with a searchable text layer, or an image. */
export default function DocumentViewer({ invoiceId, highlight }: Props) {
  const url = `${API_BASE}/invoices/${invoiceId}/document`;
  const file = useQuery({
    queryKey: ["invoices", "document", invoiceId],
    queryFn: async () => {
      const response = await fetch(url);
      if (!response.ok) throw new Error(`The document could not be loaded (${response.status})`);
      return response.blob();
    },
    staleTime: Infinity, // the original never changes
  });
  const [pages, setPages] = useState(0);
  const [page, setPage] = useState(1);
  const [zoom, setZoom] = useState(1);
  const [found, setFound] = useState<boolean | null>(null);
  const frame = useRef<HTMLDivElement>(null);
  const width = useElementWidth(frame);

  const renderText = useCallback(
    ({ str }: { str: string }) => markMatches(str, highlight),
    [highlight],
  );

  // After the text layer redraws with new marks, bring the first one into view.
  const revealMatch = useCallback(() => {
    if (highlight.length === 0) {
      setFound(null);
      return;
    }
    const mark = frame.current?.querySelector(".textLayer mark");
    setFound(Boolean(mark));
    mark?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [highlight]);

  const isPdf = file.data?.type === "application/pdf";
  const imageUrl = useObjectUrl(isPdf ? undefined : file.data);
  return (
    <div className="flex h-full flex-col overflow-hidden rounded-2xl border border-border bg-surface">
      <div className="flex items-center gap-1 border-b border-border px-3 py-2 text-sm">
        {isPdf && pages > 1 && (
          <>
            <Button variant="ghost" size="icon" aria-label="Previous page" onClick={() => setPage((p) => Math.max(1, p - 1))}>
              <ChevronLeft />
            </Button>
            <span className="tabular text-muted">
              {page} / {pages}
            </span>
            <Button variant="ghost" size="icon" aria-label="Next page" onClick={() => setPage((p) => Math.min(pages, p + 1))}>
              <ChevronRight />
            </Button>
          </>
        )}
        <span className="flex-1 truncate px-2 text-xs text-muted" aria-live="polite">
          {found === false
            ? "That value isn't printed this way in the document"
            : found
              ? "Highlighted in the document"
              : isPdf
                ? "Select a field to find it in the document"
                : file.data
                  ? "Images can't be searched; compare by eye"
                  : ""}
        </span>
        <Button variant="ghost" size="icon" aria-label="Zoom out" onClick={() => setZoom((z) => ZOOMS[Math.max(0, ZOOMS.indexOf(z) - 1)]!)}>
          <ZoomOut />
        </Button>
        <span className="tabular w-11 text-center text-xs text-muted">{Math.round(zoom * 100)}%</span>
        <Button variant="ghost" size="icon" aria-label="Zoom in" onClick={() => setZoom((z) => ZOOMS[Math.min(ZOOMS.length - 1, ZOOMS.indexOf(z) + 1)]!)}>
          <ZoomIn />
        </Button>
        <Button variant="ghost" size="icon" asChild aria-label="Open the original document">
          <a href={url} target="_blank" rel="noreferrer">
            <ExternalLink />
          </a>
        </Button>
      </div>

      <div ref={frame} className="min-h-0 flex-1 overflow-auto bg-surface-muted p-4">
        {file.isPending ? (
          <Skeleton className="aspect-[1/1.414] w-full rounded-md" />
        ) : file.isError ? (
          <p role="alert" className="p-6 text-center text-sm text-muted">
            {file.error.message}
          </p>
        ) : isPdf ? (
          <Document
            file={file.data}
            onLoadSuccess={({ numPages }) => setPages(numPages)}
            loading={<Skeleton className="aspect-[1/1.414] w-full rounded-md" />}
            error={<p className="p-6 text-center text-sm text-muted">This PDF couldn't be displayed.</p>}
          >
            <Page
              pageNumber={page}
              width={width ? Math.max(200, (width - 32) * zoom) : undefined}
              renderAnnotationLayer={false}
              customTextRenderer={renderText}
              onRenderTextLayerSuccess={revealMatch}
              className="mx-auto w-fit overflow-hidden rounded-md shadow-md"
            />
          </Document>
        ) : (
          <img
            src={imageUrl}
            alt="The uploaded invoice"
            className="mx-auto rounded-md shadow-md"
            style={{ width: `${zoom * 100}%`, maxWidth: "none" }}
          />
        )}
      </div>
    </div>
  );
}

/** A blob: URL for the image, released when it changes or the viewer closes. */
function useObjectUrl(blob: Blob | undefined): string | undefined {
  const [url, setUrl] = useState<string>();
  useEffect(() => {
    if (!blob) return;
    const next = URL.createObjectURL(blob);
    setUrl(next);
    return () => URL.revokeObjectURL(next);
  }, [blob]);
  return url;
}

function useElementWidth(ref: React.RefObject<HTMLElement | null>): number {
  const [width, setWidth] = useState(0);
  useEffect(() => {
    const element = ref.current;
    if (!element || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(([entry]) => setWidth(entry?.contentRect.width ?? 0));
    observer.observe(element);
    return () => observer.disconnect();
  }, [ref]);
  return width;
}
