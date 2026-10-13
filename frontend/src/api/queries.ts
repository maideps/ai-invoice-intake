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
      return data ? liveRefresh([data]) : IDLE_REFRESH_MS;
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

export type { InvoiceSummary };
