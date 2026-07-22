import { type ButtonHTMLAttributes, type ReactNode, useState } from "react";

import type { Color } from "../api/types";
import { ApiError } from "../api/client";

export function cx(...parts: (string | false | null | undefined)[]) {
  return parts.filter(Boolean).join(" ");
}

type Variant = "primary" | "secondary" | "danger" | "ghost";

export function Button({
  variant = "secondary",
  className,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  const styles: Record<Variant, string> = {
    primary: "bg-brand text-white hover:bg-brand-hover",
    secondary: "bg-surface border border-border text-text hover:bg-surface-muted",
    danger: "bg-danger text-white hover:opacity-90",
    ghost: "text-text-muted hover:bg-surface-muted",
  };
  return (
    <button
      className={cx(
        "inline-flex items-center gap-1.5 rounded-control px-3 py-1.5 text-sm font-medium",
        "disabled:cursor-not-allowed disabled:opacity-50 transition-colors",
        styles[variant],
        className,
      )}
      {...props}
    />
  );
}

export function Card({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cx("rounded-card border border-border bg-surface p-4 shadow-sm", className)}>
      {children}
    </div>
  );
}

export function Badge({ children, tone = "muted" }: { children: ReactNode; tone?: "muted" | "brand" | "success" | "warning" | "danger" }) {
  const tones = {
    muted: "bg-surface-muted text-text-muted",
    brand: "bg-brand-soft text-brand",
    success: "bg-success/15 text-success",
    warning: "bg-warning/15 text-warning",
    danger: "bg-danger/15 text-danger",
  };
  return <span className={cx("rounded-full px-2 py-0.5 text-xs font-medium", tones[tone])}>{children}</span>;
}

export function StatusDot({ color, counts }: { color: Color; counts?: { open_fatal: number; open_warning: number } }) {
  const bg = { green: "bg-success", yellow: "bg-warning", red: "bg-danger" }[color];
  const label =
    color === "red"
      ? `Out of service${counts ? ` (${counts.open_fatal} fatal)` : ""}`
      : color === "yellow"
        ? `Has a warning${counts ? ` (${counts.open_warning})` : ""}`
        : "Good";
  return (
    <span className="inline-flex items-center gap-1.5" title={label} aria-label={label}>
      <span className={cx("inline-block h-2.5 w-2.5 rounded-full", bg)} />
    </span>
  );
}

export function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return (
    <label className="block text-sm">
      <span className="mb-1 block font-medium text-text">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-text-muted">{hint}</span>}
    </label>
  );
}

const inputCls =
  "w-full rounded-control border border-border bg-surface px-2.5 py-1.5 text-sm text-text outline-none focus:border-brand";

export function Input(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return <input className={cx(inputCls, props.className)} {...props} />;
}

export function Textarea(props: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={cx(inputCls, props.className)} {...props} />;
}

export function Select(props: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return <select className={cx(inputCls, props.className)} {...props} />;
}

export function Spinner() {
  return <div role="status" aria-label="Loading" className="animate-pulse text-text-muted">Loading…</div>;
}

export function ErrorNote({ error }: { error: ApiError | Error | null }) {
  if (!error) return null;
  const help = error instanceof ApiError ? helpFor(error.code) : null;
  return (
    <div role="alert" className="rounded-control border border-danger/40 bg-danger/10 p-3 text-sm text-danger">
      {error.message}
      {help && <span className="mt-1 block text-xs opacity-80">{help}</span>}
    </div>
  );
}

/** In-app plain-language help for friction points (guide §9). */
export function helpFor(code: string): string | null {
  const map: Record<string, string> = {
    forbidden: "You do not have the access level this action requires.",
    grant_forbidden: "Your delegation abilities do not permit this change.",
    equipment_in_use: "Someone else has this equipment enabled; it is never force-ended automatically.",
    fatal_fault_open: "This equipment has an open fatal issue (red). Close it to restore service.",
    quota_exceeded: "You have reached your quota for this window.",
    reservation_conflict: "That time overlaps an existing booking.",
    reservation_immutable: "A reservation can only be changed before it starts.",
    slot_misaligned: "Pick start/end times on the reservation slot boundary.",
    advance_limit_exceeded: "That is further ahead than bookings are allowed.",
    department_gate: "This is limited to certain department groups.",
    csrf_failed: "Your session expired; please sign in again.",
  };
  return map[code] ?? null;
}

export function Help({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <span className="relative inline-block">
      <button
        type="button"
        aria-label="Help"
        onClick={() => setOpen((o) => !o)}
        className="ml-1 inline-flex h-4 w-4 items-center justify-center rounded-full border border-border text-[10px] text-text-muted"
      >
        ?
      </button>
      {open && (
        <span className="absolute left-5 top-0 z-10 w-56 rounded-control border border-border bg-surface p-2 text-xs text-text-muted shadow-lg">
          {children}
        </span>
      )}
    </span>
  );
}

export function Modal({ title, children, onClose }: { title: string; children: ReactNode; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div
        role="dialog"
        aria-label={title}
        className="w-full max-w-lg rounded-card border border-border bg-surface p-4 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-text">{title}</h2>
          <Button variant="ghost" onClick={onClose} aria-label="Close">
            ✕
          </Button>
        </div>
        {children}
      </div>
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="py-8 text-center text-sm text-text-muted">{children}</div>;
}
