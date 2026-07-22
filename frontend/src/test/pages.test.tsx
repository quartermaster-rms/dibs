import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import App from "../App";
import { Login } from "../pages/Login";
import { EquipmentList } from "../pages/EquipmentList";
import { type Route, mkRow, renderWith } from "./utils";

describe("Login", () => {
  it("submits the stub identity", async () => {
    let posted: { subject?: string } = {};
    const routes: Route[] = [
      {
        match: "/auth/stub-login",
        method: "POST",
        respond: (init) => {
          posted = JSON.parse(String(init.body));
          return { body: { subject: "alice", csrf_token: "c" } };
        },
      },
    ];
    renderWith(<Login />, null, routes);
    await userEvent.type(await screen.findByLabelText("Username"), "alice");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    await waitFor(() => expect(posted.subject).toBe("alice"));
  });
});

describe("EquipmentList", () => {
  const listRoute: Route = {
    match: /^\/equipment/,
    respond: (_init, path) => ({ body: path.includes("q=zzz") ? [] : [mkRow({ name: "Big Lathe" })] }),
  };

  it("renders rows and filters via search", async () => {
    renderWith(<EquipmentList />, { subject: "u1" }, [listRoute]);
    expect(await screen.findByText("Big Lathe")).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Search equipment"), "zzz");
    await waitFor(() => expect(screen.getByText(/No equipment matches/)).toBeInTheDocument());
  });
});

describe("App navigation (capability-aware)", () => {
  const empty: Route[] = [{ match: /^\/equipment/, respond: () => ({ body: [] }) }];

  it("shows Settings + Audit to an admin", async () => {
    renderWith(<App />, { subject: "admin", is_admin: true }, empty);
    expect(await screen.findByText("Settings")).toBeInTheDocument();
    expect(screen.getByText("Audit")).toBeInTheDocument();
  });

  it("hides Settings + Audit from a plain user", async () => {
    renderWith(<App />, { subject: "u1" }, empty);
    expect(await screen.findByText("Equipment")).toBeInTheDocument();
    expect(screen.queryByText("Settings")).not.toBeInTheDocument();
    expect(screen.queryByText("Audit")).not.toBeInTheDocument();
  });
});
