import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { pdfFile, testFile } from "@/test/files";
import { db, makeInvoice, server } from "@/test/server";
import { renderApp } from "@/test/render";

function rows() {
  return within(screen.getByRole("list")).getAllByRole("link");
}

describe("review queue", () => {
  it("lists invoices with vendor, formatted total and status", async () => {
    db.invoices = [makeInvoice({ filename: "maple.pdf" }), makeInvoice({ status: "approved" })];

    renderApp();

    const first = await screen.findByRole("link", { name: /maple\.pdf/ });
    expect(first).toHaveTextContent("Maple Ridge Software Inc.");
    expect(first).toHaveTextContent("CA$6,370.86");
    expect(first).toHaveTextContent("Needs review");
    expect(rows()).toHaveLength(2);
    expect(first).toHaveAttribute("href", `/invoices/${db.invoices[0]!.id}`);
  });

  it("filters by status from the chips and keeps the filter in the URL", async () => {
    db.invoices = [makeInvoice({ status: "needs_review" }), makeInvoice({ status: "failed" })];
    const { user, location } = renderApp();
    await screen.findAllByRole("link", { name: /invoice-/ });

    await user.click(screen.getByRole("button", { name: /^Failed/ }));

    await waitFor(() => expect(rows()).toHaveLength(1));
    expect(location().search).toBe("?status=failed");
    expect(screen.getByRole("button", { name: /^Failed/ })).toHaveAttribute("aria-pressed", "true");
    const listed = db.requests.filter((r) => r.method === "GET").map((r) => new URL(r.url).search);
    expect(listed.at(-1)).toContain("status=failed");
  });

  it("shows counts per status in the chips", async () => {
    db.invoices = [makeInvoice(), makeInvoice(), makeInvoice({ status: "extracting" })];

    renderApp();

    expect(await screen.findByRole("button", { name: /^All\s*3$/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^Needs review\s*2$/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^Extracting\s*1$/ })).toBeInTheDocument();
  });

  it("invites a first upload when there are no invoices", async () => {
    renderApp();

    expect(await screen.findByRole("heading", { name: "Upload your first invoice" })).toBeInTheDocument();
  });

  it("offers to clear a filter that matches nothing", async () => {
    db.invoices = [makeInvoice()];
    const { user } = renderApp("/?status=rejected");

    await screen.findByRole("heading", { name: "Nothing in Rejected" });
    await user.click(screen.getByRole("button", { name: "Show all invoices" }));

    await waitFor(() => expect(rows()).toHaveLength(1));
  });

  it("explains a failure and recovers on retry", async () => {
    db.invoices = [makeInvoice({ filename: "after-retry.pdf" })];
    server.use(http.get("*/api/invoices", () => HttpResponse.error(), { once: true }));
    const { user } = renderApp();

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Can't reach the API");
    await user.click(within(alert).getByRole("button", { name: /Try again/ }));

    expect(await screen.findByRole("link", { name: /after-retry\.pdf/ })).toBeInTheDocument();
  });

  it("keeps the last list on screen and says so when a refresh fails", async () => {
    db.invoices = [makeInvoice({ filename: "kept.pdf" })];
    const { client } = renderApp();
    await screen.findByRole("link", { name: /kept\.pdf/ });
    server.use(http.get("*/api/invoices", () => HttpResponse.json({}, { status: 502 })));

    await client.refetchQueries({ queryKey: ["invoices", "list"] });

    expect(await screen.findByRole("status")).toHaveTextContent(
      "Showing the last loaded list. Can't reach the API",
    );
    expect(screen.getByRole("link", { name: /kept\.pdf/ })).toBeInTheDocument();
  });

  it("uploads a dropped file and shows it in the list", async () => {
    const { user } = renderApp();
    await screen.findByRole("heading", { name: "Upload your first invoice" });

    await user.upload(screen.getByLabelText("Upload invoices"), pdfFile("new-one.pdf"));

    expect(await screen.findByText("new-one.pdf uploaded")).toBeInTheDocument();
    const row = await screen.findByRole("link", { name: /new-one\.pdf/ });
    expect(row).toHaveTextContent("Queued");
    expect(row).toHaveTextContent("Reading the document…");
  });

  it("shows the server's reason when an upload is refused", async () => {
    const { user } = renderApp();
    await screen.findByRole("heading", { name: "Upload your first invoice" });
    const text = testFile("just text", "notes.pdf");

    await user.upload(screen.getByLabelText("Upload invoices"), text);

    expect(await screen.findByText("Couldn't upload notes.pdf")).toBeInTheDocument();
    expect(screen.getByText("only PDF, PNG and JPEG files are accepted")).toBeInTheDocument();
    expect(db.invoices).toHaveLength(0);
  });
});

describe("app shell", () => {
  it("sends the chosen name as X-User with uploads", async () => {
    const { user } = renderApp();
    await user.click(await screen.findByRole("button", { name: "Acting as anonymous" }));
    await user.type(screen.getByLabelText("Acting as"), "alice@example.com");
    await user.click(screen.getByRole("button", { name: "Save" }));

    await user.upload(screen.getByLabelText("Upload invoices"), pdfFile("signed.pdf"));
    await screen.findByText("signed.pdf uploaded");

    const upload = db.requests.find((r) => r.method === "POST");
    expect(upload?.headers.get("X-User")).toBe("alice@example.com");
    expect(screen.getByRole("button", { name: "Acting as alice@example.com" })).toBeInTheDocument();
  });

  it("cycles the theme between system, light and dark", async () => {
    const { user } = renderApp();
    const toggle = await screen.findByRole("button", { name: "Theme: follows your system" });

    await user.click(toggle);
    expect(document.documentElement).not.toHaveClass("dark");
    await user.click(screen.getByRole("button", { name: "Theme: light" }));
    expect(document.documentElement).toHaveClass("dark");
    expect(screen.getByRole("button", { name: "Theme: dark" })).toBeInTheDocument();
  });

  it("shows a friendly page for unknown addresses", async () => {
    renderApp("/no/such/page");

    expect(await screen.findByRole("heading", { name: "Page not found" })).toBeInTheDocument();
  });
});
