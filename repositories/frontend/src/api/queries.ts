import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { STATUS_META, type InvoiceStatus } from "@/lib/status";

import { api, unwrap, type Invoice, type InvoicePage, type InvoiceSummary, type Stats } from "./client";

export const PAGE_SIZE = 20;
/** How often to refresh while the worker is busy with something on screen. */
export const LIVE_REFRESH_MS = 2000;
/** Otherwise a slow refresh, so uploads by other people and integrations still show up. */
export const IDLE_REFRESH_MS = 15_000;

export const keys = {
  all: ["invoices"] as const,
  list: (status: InvoiceStatus | null, page: number) => ["invoices", "list", status, page] as const,
  stats: ["invoices", "stats"] as const,
  detail: (id: string) => ["invoices", "detail", id] as const,
};

/** Refresh every couple of seconds while any listed invoice is still being processed. */
export function liveRefresh(items: { status: InvoiceStatus }[] | undefined): number {
  return items?.some((item) => STATUS_META[item.status].inProgress) ? LIVE_REFRESH_MS : IDLE_REFRESH_MS;
}

export function useInvoices(status: InvoiceStatus | null, page: number) {
  return useQuery({
    queryKey: keys.list(status, page),
    queryFn: () =>
      unwrap<InvoicePage>(
        api.GET("/invoices", {
          params: {
            query: { limit: PAGE_SIZE, offset: (page - 1) * PAGE_SIZE, ...(status ? { status } : {}) },
          },
        }),
      ),
    placeholderData: keepPreviousData,
    refetchInterval: (query) => liveRefresh(query.state.data?.items),
  });
}

export function useStats() {
  return useQuery({
    queryKey: keys.stats,
    queryFn: () => unwrap<Stats>(api.GET("/invoices/stats")),
    refetchInterval: (query) => {
      const byStatus = query.state.data?.by_status ?? {};
      const busy = (byStatus.uploaded ?? 0) + (byStatus.extracting ?? 0) > 0;
      return busy ? LIVE_REFRESH_MS : IDLE_REFRESH_MS;
    },
  });
}

export function useInvoice(id: string) {
  return useQuery({
    queryKey: keys.detail(id),
    queryFn: () =>
      unwrap<Invoice>(api.GET("/invoices/{invoice_id}", { params: { path: { invoice_id: id } } })),
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data) return IDLE_REFRESH_MS;
      // An approved invoice on its way to the accounting system: follow it closely too.
      const exporting = data.export?.state === "pending" || data.export?.state === "retrying";
      return exporting ? LIVE_REFRESH_MS : liveRefresh([data]);
    },
  });
}

export function useUploadInvoice() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (file: File) =>
      unwrap<Invoice>(
        api.POST("/invoices", {
          body: { file: file as unknown as string },
          bodySerializer: () => {
            const form = new FormData();
            form.append("file", file);
            return form;
          },
        }),
      ),
    onSuccess: (invoice) => {
      queryClient.setQueryData(keys.detail(invoice.id), invoice);
      void queryClient.invalidateQueries({ queryKey: keys.all });
    },
  });
}

/** After a change: show the new invoice at once, and refresh lists and counts. */
function useInvoiceUpdated() {
  const queryClient = useQueryClient();
  return (invoice: Invoice) => {
    queryClient.setQueryData(keys.detail(invoice.id), invoice);
    void queryClient.invalidateQueries({ queryKey: ["invoices", "list"] });
    void queryClient.invalidateQueries({ queryKey: keys.stats });
  };
}

const path = (id: string) => ({ params: { path: { invoice_id: id } } });

export function useEditFields(id: string) {
  const onSuccess = useInvoiceUpdated();
  return useMutation({
    mutationFn: (body: { version: number; fields: Record<string, unknown> }) =>
      unwrap<Invoice>(api.PATCH("/invoices/{invoice_id}/fields", { ...path(id), body })),
    onSuccess,
  });
}

export function useApprove(id: string) {
  const onSuccess = useInvoiceUpdated();
  return useMutation({
    mutationFn: (version: number) =>
      unwrap<Invoice>(api.POST("/invoices/{invoice_id}/approve", { ...path(id), body: { version } })),
    onSuccess,
  });
}

export function useReject(id: string) {
  const onSuccess = useInvoiceUpdated();
  return useMutation({
    mutationFn: ({ version, reason }: { version: number; reason: string }) =>
      unwrap<Invoice>(
        api.POST("/invoices/{invoice_id}/reject", { ...path(id), body: { version, reason } }),
      ),
    onSuccess,
  });
}

export function useRequestExtraction(id: string) {
  const onSuccess = useInvoiceUpdated();
  return useMutation({
    mutationFn: () => unwrap<Invoice>(api.POST("/invoices/{invoice_id}/extract", path(id))),
    onSuccess,
  });
}

export function useRequestExport(id: string) {
  const onSuccess = useInvoiceUpdated();
  return useMutation({
    mutationFn: () => unwrap<Invoice>(api.POST("/invoices/{invoice_id}/export", path(id))),
    onSuccess,
  });
}

/** Service facts the UI adapts to, such as whether an export webhook is configured. */
export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: () => unwrap(api.GET("/health")),
    staleTime: 60_000,
  });
}

/** Invoices waiting for review, oldest first, for "next" and "previous" (J and K). */
export function useReviewQueue() {
  return useQuery({
    queryKey: ["invoices", "list", "review-order"],
    queryFn: async () => {
      const page = await unwrap<InvoicePage>(
        api.GET("/invoices", { params: { query: { status: "needs_review", limit: 100, offset: 0 } } }),
      );
      return page.items.map((item) => item.id).reverse();
    },
    refetchInterval: IDLE_REFRESH_MS,
  });
}

export type { InvoiceSummary };
