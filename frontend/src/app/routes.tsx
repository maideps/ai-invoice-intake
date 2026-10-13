import type { RouteObject } from "react-router";

import { InvoicePage } from "@/features/invoice/InvoicePage";
import { QueuePage } from "@/features/queue/QueuePage";

import { AppShell } from "./AppShell";
import { NotFoundPage } from "./NotFoundPage";

export const routes: RouteObject[] = [
  {
    element: <AppShell />,
    children: [
      { index: true, element: <QueuePage /> },
      { path: "invoices/:invoiceId", element: <InvoicePage /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
];
