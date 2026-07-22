import { beforeAll, describe, expect, it } from "vitest";

import { fmtDateTime, fromLocalInput, setTz, toLocalInput } from "../lib/time";

describe("PLATFORM_TZ time helpers", () => {
  beforeAll(() => setTz("America/Los_Angeles"));

  it("converts a local wall-time (PDT) to a UTC instant", () => {
    // July -> PDT (UTC-7): 15:00 local == 22:00 UTC
    expect(fromLocalInput("2026-07-22T15:00")).toBe("2026-07-22T22:00:00Z");
  });

  it("round-trips local <-> UTC", () => {
    const iso = fromLocalInput("2026-07-22T15:00");
    expect(toLocalInput(iso)).toBe("2026-07-22T15:00");
  });

  it("handles PST (winter, UTC-8)", () => {
    expect(fromLocalInput("2026-01-15T09:00")).toBe("2026-01-15T17:00:00Z");
  });

  it("formats and guards null", () => {
    expect(fmtDateTime(null)).toBe("—");
    expect(fmtDateTime("2026-07-22T22:00:00Z")).toMatch(/2026/);
  });
});
