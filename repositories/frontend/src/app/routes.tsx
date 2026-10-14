import type { RouteObject } from "react-router";

import { UsersPage } from "@/features/accounts/UsersPage";
import { QueuePage } from "@/features/queue/QueuePage";
import { ReviewPage } from "@/features/review/ReviewPage";

import { AppShell } from "./AppShell";
import { NotFoundPage } from "./NotFoundPage";
import { SignedInOnly } from "./SignedInOnly";

export const routes: RouteObject[] = [
  {
    // Everything needs a signed-in account (D-019); <SignedInOnly> shows sign-in otherwise.
    element: (
      <SignedInOnly>
        <AppShell />
      </SignedInOnly>
    ),
    children: [
      { index: true, element: <QueuePage /> },
      { path: "invoices/:invoiceId", element: <ReviewPage /> },
      { path: "users", element: <UsersPage /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
];
