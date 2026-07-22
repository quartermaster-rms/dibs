import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Badge, StatusDot, helpFor } from "../components/ui";

describe("ui primitives", () => {
  it("maps friction codes to help text", () => {
    expect(helpFor("equipment_in_use")).toMatch(/enabled/i);
    expect(helpFor("fatal_fault_open")).toMatch(/fatal/i);
    expect(helpFor("unknown_code")).toBeNull();
  });

  it("labels the red status dot as out of service", () => {
    render(<StatusDot color="red" counts={{ open_fatal: 2, open_warning: 0 }} />);
    expect(screen.getByLabelText(/Out of service/)).toBeInTheDocument();
  });

  it("labels the green status dot as good", () => {
    render(<StatusDot color="green" />);
    expect(screen.getByLabelText("Good")).toBeInTheDocument();
  });

  it("renders a badge", () => {
    render(<Badge tone="brand">admin</Badge>);
    expect(screen.getByText("admin")).toBeInTheDocument();
  });
});
