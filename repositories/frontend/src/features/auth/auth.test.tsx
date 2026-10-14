import { screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { renderApp } from "@/test/render";
import { addAccount, db, makeInvoice, PASSWORD, signInAs } from "@/test/server";

// pdf.js needs a real canvas; these tests are about who may do what.
vi.mock("@/features/review/DocumentViewer", () => ({ default: () => <div data-testid="document" /> }));

const signOut = () => {
  db.account = null;
};

describe("signing in", () => {
  it("asks who you are, explains a wrong password, then shows the queue", async () => {
    signOut();
    const { user } = renderApp();

    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    await user.type(screen.getByLabelText("Username"), "maide");
    await user.type(screen.getByLabelText("Password"), "not the password");
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Wrong username or password.");

    await user.clear(screen.getByLabelText("Password"));
    await user.type(screen.getByLabelText("Password"), PASSWORD);
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByRole("heading", { name: "Review queue" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Signed in as Maide P (Reviewer)" })).toBeInTheDocument();
  });

  it("offers the demo accounts when the server lists them", async () => {
    signOut();
    const viewer = addAccount("viewer", "alex.chen", "Alex Chen");
    db.demoAccounts = [
      { username: viewer.username, display_name: viewer.display_name, role: "viewer", password: PASSWORD },
    ];
    const { user } = renderApp();

    const demo = await screen.findByRole("region", { name: "Demo accounts" });
    expect(within(demo).getByText(`alex.chen / ${PASSWORD}`)).toBeInTheDocument();
    await user.click(within(demo).getByRole("button", { name: "Sign in as Alex Chen (Viewer)" }));

    expect(await screen.findByRole("button", { name: "Signed in as Alex Chen (Viewer)" })).toBeInTheDocument();
  });

  it("lists no demo accounts unless the server does", async () => {
    signOut();
    renderApp();

    await screen.findByRole("heading", { name: "Sign in" });
    expect(screen.queryByRole("region", { name: "Demo accounts" })).not.toBeInTheDocument();
  });

  it("signs out from the user menu", async () => {
    const { user } = renderApp();
    await user.click(await screen.findByRole("button", { name: /^Signed in as Maide P/ }));
    await user.click(screen.getByRole("button", { name: "Sign out" }));

    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    expect(db.account).toBeNull();
  });

  it("returns to sign-in when the session ends while working", async () => {
    const invoice = makeInvoice();
    db.invoices.push(invoice);
    const { user } = renderApp(`/invoices/${invoice.id}`);
    await screen.findByRole("heading", { name: invoice.filename });

    signOut(); // e.g. expired, or deactivated by an admin
    await user.click(screen.getByRole("button", { name: /Approve/ }));

    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    expect(db.invoices[0]!.status).toBe("needs_review");
  });
});

describe("viewers", () => {
  it("see the queue without the upload area", async () => {
    signInAs("viewer");
    db.invoices.push(makeInvoice());
    renderApp();

    expect(await screen.findByText(/signed in as a viewer/)).toBeInTheDocument();
    expect(screen.queryByLabelText("Upload invoices")).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Users" })).not.toBeInTheDocument();
  });

  it("can read an invoice but not change or decide it", async () => {
    signInAs("viewer");
    const invoice = makeInvoice();
    db.invoices.push(invoice);
    const { user } = renderApp(`/invoices/${invoice.id}`);
    await screen.findByRole("heading", { name: invoice.filename });

    expect(screen.getByText(/Read-only: a viewer can follow this invoice/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Approve/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Reject/ })).not.toBeInTheDocument();
    expect(screen.getByLabelText("Total", { selector: "input" })).toHaveAttribute("readonly");

    await user.keyboard("a"); // the shortcut does nothing either
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(db.invoices[0]!.status).toBe("needs_review");
  });
});

describe("the Users screen", () => {
  it("is for admins only", async () => {
    renderApp("/users"); // signed in as a reviewer

    expect(await screen.findByText("Only admins manage accounts")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Users" })).not.toBeInTheDocument();
  });

  it("lets an admin add an account and change it", async () => {
    signInAs("admin", "boss", "Bo Boss");
    const { user } = renderApp();
    await user.click(await screen.findByRole("link", { name: "Users" }));
    const accounts = await screen.findByRole("region", { name: "Accounts" });
    expect(await within(accounts).findByText("maide")).toBeInTheDocument();

    await user.type(screen.getByLabelText("Username"), "Kim.Lee");
    await user.type(screen.getByLabelText("Display name"), "Kim Lee");
    await user.selectOptions(screen.getByLabelText("Role"), "viewer");
    await user.type(screen.getByLabelText("Starting password"), "a starting password");
    await user.click(screen.getByRole("button", { name: /Add/ }));

    expect(await screen.findByText("Added Kim Lee")).toBeInTheDocument();
    expect(await within(accounts).findByText("kim.lee")).toBeInTheDocument();
    expect(db.accounts.find((a) => a.username === "kim.lee")?.role).toBe("viewer");

    await user.selectOptions(screen.getByLabelText("Role for Kim Lee"), "reviewer");
    expect(await screen.findByText("Kim Lee is now reviewer")).toBeInTheDocument();
    expect(db.accounts.find((a) => a.username === "kim.lee")?.role).toBe("reviewer");

    const kim = within(accounts).getByText("kim.lee").closest("li")!;
    await user.click(within(kim as HTMLElement).getByRole("button", { name: "Deactivate" }));
    expect(await screen.findByText("Kim Lee can no longer sign in")).toBeInTheDocument();
    await waitFor(() => expect(within(kim as HTMLElement).getByText("Inactive")).toBeInTheDocument());
  });

  it("explains a refused change: the last admin keeps the role", async () => {
    signInAs("admin", "boss", "Bo Boss");
    const { user } = renderApp("/users");

    await user.selectOptions(await screen.findByLabelText("Role for Bo Boss"), "viewer");

    expect(await screen.findByText("Couldn't change Bo Boss")).toBeInTheDocument();
    expect(screen.getByText(/keep at least one active admin/)).toBeInTheDocument();
    expect(db.accounts.find((a) => a.username === "boss")?.role).toBe("admin");
  });

  it("shows why an account could not be added", async () => {
    signInAs("admin", "boss", "Bo Boss");
    const { user } = renderApp("/users");
    await screen.findByRole("region", { name: "Accounts" });

    await user.type(screen.getByLabelText("Username"), "maide");
    await user.type(screen.getByLabelText("Display name"), "Twin");
    await user.type(screen.getByLabelText("Starting password"), "a starting password");
    await user.click(screen.getByRole("button", { name: /Add/ }));

    expect(await screen.findByRole("alert")).toHaveTextContent("the username 'maide' is taken");
  });
});
