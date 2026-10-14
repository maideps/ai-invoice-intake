import type { Role } from "@/api/client";

/** What each role means, in the words the UI uses (the API enforces it, D-019). */
export const ROLE_META: Record<Role, { label: string; description: string }> = {
  viewer: { label: "Viewer", description: "Reads invoices, documents and audit trails" },
  reviewer: { label: "Reviewer", description: "Uploads, corrects, approves and rejects invoices" },
  admin: { label: "Admin", description: "Everything a reviewer does, and manages accounts" },
};

export const ROLES: Role[] = ["viewer", "reviewer", "admin"];
