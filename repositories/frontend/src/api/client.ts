import createClient, { type Middleware } from "openapi-fetch";

import type { components, paths } from "./schema";

export type Invoice = components["schemas"]["InvoiceOut"];
export type InvoiceSummary = components["schemas"]["InvoiceSummaryOut"];
export type InvoicePage = components["schemas"]["InvoicePageOut"];
export type Stats = components["schemas"]["StatsOut"];
export type Account = components["schemas"]["AccountOut"];
export type DemoAccount = components["schemas"]["DemoAccountOut"];
export type Role = Account["role"];
export type Permission = Account["permissions"][number];

/** Same origin: Vite (dev) or the web server (later) forwards /api to FastAPI. */
export const API_BASE = "/api";

/** A failed API call, with the most useful message the server gave. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
    readonly errors: string[] = [],
  ) {
    super(message);
    this.name = "ApiError";
  }

  /** No answer from the API itself: network down, or a proxy in front of it gave up. */
  get unreachable(): boolean {
    return this.status === 0 || UNREACHABLE_STATUSES.includes(this.status);
  }
}

const UNREACHABLE_STATUSES = [502, 503, 504];
const UNREACHABLE_MESSAGE = "Can't reach the API. Check that the backend is running.";

/** Turn FastAPI's error bodies (string, {message, errors} or validation list) into an ApiError. */
export function toApiError(status: number, body: unknown): ApiError {
  if (UNREACHABLE_STATUSES.includes(status)) return new ApiError(status, UNREACHABLE_MESSAGE);
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return new ApiError(status, detail);
  if (detail && typeof detail === "object" && "message" in detail) {
    const problem = detail as { message: string; errors?: string[] };
    return new ApiError(status, problem.message, problem.errors ?? []);
  }
  if (Array.isArray(detail)) {
    const messages = detail.map((item: { msg?: string }) => item.msg ?? "Invalid request");
    return new ApiError(status, messages[0] ?? "Invalid request", messages);
  }
  return new ApiError(status, status >= 500 ? "The server had a problem" : `Request failed (${status})`);
}

/** Told when the API answers 401 (the session ended or expired), except to sign-in itself. */
const signedOutListeners = new Set<() => void>();

export function onSignedOut(listener: () => void): () => void {
  signedOutListeners.add(listener);
  return () => signedOutListeners.delete(listener);
}

// The session is an HttpOnly cookie (D-019): the browser sends it, scripts never see it.
const sessionWatch: Middleware = {
  onResponse({ request, response }) {
    if (response.status === 401 && !new URL(request.url).pathname.endsWith("/auth/sign-in")) {
      signedOutListeners.forEach((listener) => listener());
    }
    return response;
  },
};

export const api = createClient<paths>({
  // Absolute: fetch outside the browser (tests) cannot resolve a relative URL.
  baseUrl: `${globalThis.location?.origin ?? ""}${API_BASE}`,
  // Look fetch up on each call rather than once at import, so test mocks installed later apply.
  fetch: (request) => globalThis.fetch(request),
});
api.use(sessionWatch);

/** Unwrap an openapi-fetch result: the data, or an ApiError. A network failure throws too. */
export async function unwrap<T>(
  call: Promise<{ data?: T; error?: unknown; response: Response }>,
): Promise<T> {
  let result: { data?: T; error?: unknown; response: Response };
  try {
    result = await call;
  } catch {
    throw new ApiError(0, UNREACHABLE_MESSAGE);
  }
  if (result.error !== undefined || !result.response.ok) {
    throw toApiError(result.response.status, result.error);
  }
  return result.data as T;
}
