let TZ = "UTC";

export function setTz(tz: string) {
  TZ = tz;
}

export function tzLabel(): string {
  return TZ;
}

export function fmtDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: TZ,
  }).format(new Date(iso));
}

export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Intl.DateTimeFormat("en-US", { dateStyle: "medium", timeZone: TZ }).format(
    new Date(iso),
  );
}

/** A local `YYYY-MM-DDTHH:mm` string (in PLATFORM_TZ) for datetime-local inputs. */
export function toLocalInput(iso: string): string {
  const parts = new Intl.DateTimeFormat("en-CA", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: TZ,
  }).formatToParts(new Date(iso));
  const get = (t: string) => parts.find((p) => p.type === t)?.value ?? "00";
  return `${get("year")}-${get("month")}-${get("day")}T${get("hour")}:${get("minute")}`;
}

function wallAsUtcMs(utcMs: number): number {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: TZ,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).formatToParts(new Date(utcMs));
  const g = (t: string) => Number(parts.find((p) => p.type === t)!.value);
  const hour = g("hour") === 24 ? 0 : g("hour");
  return Date.UTC(g("year"), g("month") - 1, g("day"), hour, g("minute"), g("second"));
}

/** Interpret a `YYYY-MM-DDTHH:mm` wall-time (PLATFORM_TZ) as a UTC ISO instant. */
export function fromLocalInput(local: string): string {
  const [date, time] = local.split("T");
  const [y, m, d] = date.split("-").map(Number);
  const [hh, mm] = time.split(":").map(Number);
  const guess = Date.UTC(y, m - 1, d, hh, mm, 0);
  const offset = guess - wallAsUtcMs(guess); // TZ offset from UTC at this instant
  return new Date(guess + offset).toISOString().replace(/\.\d{3}Z$/, "Z");
}
