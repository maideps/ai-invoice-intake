import { describe, expect, it } from "vitest";

import { IDLE_REFRESH_MS, liveRefresh, LIVE_REFRESH_MS } from "./queries";
import { toApiError } from "./client";

describe("toApiError", () => {
  it("keeps a plain detail message", () => {
    const error = toApiError(415, { detail: "only PDF, PNG and JPEG files are accepted" });
    expect([error.status, error.message]).toEqual([415, "only PDF, PNG and JPEG files are accepted"]);
  });

  it("keeps the review endpoints' message and error list", () => {
    const error = toApiError(422, {
      detail: { message: "cannot approve until these fields are filled", errors: ["total"] },
    });
    expect(error.message).toBe("cannot approve until these fields are filled");
    expect(error.errors).toEqual(["total"]);
  });

  it("summarises FastAPI validation errors", () => {
    const error = toApiError(422, { detail: [{ msg: "Field required" }, { msg: "Too short" }] });
    expect(error.message).toBe("Field required");
    expect(error.errors).toEqual(["Field required", "Too short"]);
  });

  it("treats a gateway error as an unreachable API", () => {
    for (const status of [502, 503, 504]) {
      const error = toApiError(status, { detail: "The API is not running" });
      expect(error.unreachable).toBe(true);
      expect(error.message).toBe("Can't reach the API. Check that the backend is running.");
    }
    expect(toApiError(500, null).unreachable).toBe(false);
  });

  it("has a readable fallback for unknown bodies", () => {
    expect(toApiError(500, "oops").message).toBe("The server had a problem");
    expect(toApiError(404, null).message).toBe("Request failed (404)");
  });
});

describe("liveRefresh", () => {
  it("refreshes quickly while the worker is busy with something listed, slowly otherwise", () => {
    expect(liveRefresh([{ status: "needs_review" }, { status: "uploaded" }])).toBe(LIVE_REFRESH_MS);
    expect(liveRefresh([{ status: "extracting" }])).toBe(LIVE_REFRESH_MS);
    expect(liveRefresh([{ status: "needs_review" }, { status: "failed" }])).toBe(IDLE_REFRESH_MS);
    expect(liveRefresh(undefined)).toBe(IDLE_REFRESH_MS);
  });
});
