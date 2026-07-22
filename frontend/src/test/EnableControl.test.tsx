import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { EnableControl } from "../components/EnableControl";
import { mkRow, renderWith } from "./utils";

const noop = () => {};
const holder = (subject: string, name: string) => ({
  subject,
  display_name: name,
  started_at: "2026-07-22T22:00:00Z",
  session_id: "s1",
});

describe("EnableControl (capability-aware)", () => {
  it("shows no control on a no-enable item", async () => {
    renderWith(<EnableControl row={mkRow({ enable_gated: false })} onChange={noop} />, { subject: "u1" });
    expect(await screen.findByText(/No interlock/)).toBeInTheDocument();
  });

  it("enables when authorized and green", async () => {
    renderWith(<EnableControl row={mkRow()} onChange={noop} />, { subject: "u1" });
    expect(await screen.findByRole("button", { name: "Enable" })).toBeEnabled();
  });

  it("blocks (disabled) with explanation when not authorized", async () => {
    renderWith(<EnableControl row={mkRow({ can_operate: false })} onChange={noop} />, { subject: "u1" });
    expect(await screen.findByRole("button", { name: "Enable" })).toBeDisabled();
    expect(screen.getByText("Not authorized")).toBeInTheDocument();
  });

  it("blocks non-admin on red equipment", async () => {
    renderWith(
      <EnableControl row={mkRow({ status: { color: "red", open_fatal: 1, open_warning: 0 } })} onChange={noop} />,
      { subject: "u1" },
    );
    expect(await screen.findByRole("button", { name: "Enable" })).toBeDisabled();
    expect(screen.getByText("Red")).toBeInTheDocument();
  });

  it("shows in-use for a non-admin when held by another", async () => {
    renderWith(
      <EnableControl row={mkRow({ current_holder: holder("u2", "Bob") })} onChange={noop} />,
      { subject: "u1" },
    );
    expect(await screen.findByText(/In use by Bob/)).toBeInTheDocument();
  });

  it("offers force-close to an admin when held by another", async () => {
    renderWith(
      <EnableControl row={mkRow({ current_holder: holder("u2", "Bob") })} onChange={noop} />,
      { subject: "admin", is_admin: true },
    );
    expect(await screen.findByRole("button", { name: /Force close/ })).toBeInTheDocument();
  });

  it("offers disable to the holder", async () => {
    renderWith(
      <EnableControl row={mkRow({ current_holder: holder("u1", "Me") })} onChange={noop} />,
      { subject: "u1" },
    );
    expect(await screen.findByRole("button", { name: "Disable" })).toBeInTheDocument();
  });
});
