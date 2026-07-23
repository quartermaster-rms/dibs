import {
  type AnchorHTMLAttributes,
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
  useEffect,
  useState,
} from "react";

import type { Color } from "../api/types";
import { ApiError } from "../api/client";

export function cx(...parts: (string | false | null | undefined)[]) {
  return parts.filter(Boolean).join(" ");
}

type Variant = "primary" | "secondary" | "danger" | "ghost" | "ghost-danger";

const VARIANTS: Record<Variant, string> = {
  primary: "bg-brand text-on-brand hover:bg-brand-hover",
  secondary: "bg-surface border border-border text-text hover:bg-surface-muted",
  danger: "bg-danger text-on-brand hover:opacity-90",
  ghost: "text-text-muted hover:bg-surface-muted hover:text-text",
  "ghost-danger": "text-danger hover:bg-danger/10",
};

const BTN_BASE = cx(
  "inline-flex items-center justify-center gap-1.5 rounded-control px-3 py-1.5 text-sm font-medium",
  "transition-colors disabled:cursor-not-allowed disabled:opacity-50",
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-2 focus-visible:ring-offset-surface",
);

export function buttonClasses(variant: Variant = "secondary", className?: string) {
  return cx(BTN_BASE, VARIANTS[variant], className);
}

export function Button({
  variant = "secondary",
  className,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return <button className={buttonClasses(variant, className)} {...props} />;
}

/** An <a> styled as a button (avoids nesting a <button> inside an <a>). */
export function ButtonLink({
  variant = "secondary",
  className,
  ...props
}: AnchorHTMLAttributes<HTMLAnchorElement> & { variant?: Variant }) {
  return <a className={buttonClasses(variant, className)} {...props} />;
}

/** Compact icon-only button (requires an aria-label). */
export function IconButton({ className, ...props }: ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      type="button"
      className={cx(
        "inline-flex h-7 w-7 items-center justify-center rounded-control text-text-muted transition-colors",
        "hover:bg-surface-muted hover:text-text",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-1 focus-visible:ring-offset-surface",
        "disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      {...props}
    />
  );
}

export function Card({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={cx("rounded-card border border-border bg-surface p-4 shadow-sm", className)}>
      {children}
    </div>
  );
}

export function PageHeading({
  title,
  subtitle,
  actions,
}: {
  title: string;
  subtitle?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-2">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-text">{title}</h1>
        {subtitle && <p className="mt-0.5 text-sm text-text-muted">{subtitle}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}

export function SectionHeading({ children, className }: { children: ReactNode; className?: string }) {
  return <h2 className={cx("text-base font-semibold text-text", className)}>{children}</h2>;
}

export function Badge({
  children,
  tone = "muted",
}: {
  children: ReactNode;
  tone?: "muted" | "brand" | "success" | "warning" | "danger";
}) {
  const tones = {
    muted: "bg-surface-muted text-text-muted",
    brand: "bg-brand-soft text-brand",
    success: "bg-success/15 text-success",
    warning: "bg-warning/15 text-warning",
    danger: "bg-danger/15 text-danger",
  };
  return (
    <span className={cx("rounded-full px-2 py-0.5 text-xs font-medium", tones[tone])}>{children}</span>
  );
}

export function StatusDot({
  color,
  counts,
}: {
  color: Color;
  counts?: { open_fatal: number; open_warning: number };
}) {
  const bg = { green: "bg-success", yellow: "bg-warning", red: "bg-danger" }[color];
  const ring = { green: "ring-success/30", yellow: "ring-warning/30", red: "ring-danger/30" }[color];
  const label =
    color === "red"
      ? `Out of service${counts ? ` (${counts.open_fatal} fatal)` : ""}`
      : color === "yellow"
        ? `Has a warning${counts ? ` (${counts.open_warning})` : ""}`
        : "Good";
  return (
    <span className="inline-flex items-center gap-1.5" title={label} aria-label={label}>
      <span className={cx("inline-block h-2.5 w-2.5 rounded-full ring-4", bg, ring)} />
    </span>
  );
}

export function Field({
  label,
  children,
  hint,
  help,
}: {
  label: string;
  children: ReactNode;
  hint?: string;
  help?: ReactNode;
}) {
  return (
    <label className="block text-sm">
      <span className="mb-1 flex items-center gap-1 font-medium text-text">
        {label}
        {help && <Help>{help}</Help>}
      </span>
      {children}
      {hint && <span className="mt-1 block text-xs text-text-muted">{hint}</span>}
    </label>
  );
}

const inputCls = cx(
  "w-full rounded-control border border-border bg-surface px-2.5 py-1.5 text-sm text-text",
  "placeholder:text-text-muted transition-colors outline-none",
  "hover:border-text-muted focus:border-brand focus:ring-2 focus:ring-brand/40",
  "disabled:cursor-not-allowed disabled:opacity-60 disabled:bg-surface-muted",
  "aria-[invalid=true]:border-danger aria-[invalid=true]:ring-2 aria-[invalid=true]:ring-danger/30",
);

export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={cx(inputCls, props.className)} {...props} />;
}

export function Textarea(props: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={cx(inputCls, props.className)} {...props} />;
}

export function Select({ className, children, ...props }: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <span className="relative block">
      <select className={cx(inputCls, "cursor-pointer appearance-none pr-8", className)} {...props}>
        {children}
      </select>
      <svg
        className="pointer-events-none absolute right-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted"
        viewBox="0 0 20 20"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
        aria-hidden="true"
      >
        <path d="M6 8l4 4 4-4" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </span>
  );
}

/** A pill-shaped search field with a leading icon and a clear button. */
export function SearchInput({
  className,
  value,
  onClear,
  ...props
}: InputHTMLAttributes<HTMLInputElement> & { onClear?: () => void }) {
  const hasValue = value != null && value !== "";
  return (
    <div className={cx("relative", className)}>
      <svg
        aria-hidden="true"
        className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted"
        viewBox="0 0 20 20"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
      >
        <circle cx="9" cy="9" r="6" />
        <path d="M14 14l3.5 3.5" strokeLinecap="round" />
      </svg>
      <input
        type="text"
        value={value}
        className={cx(
          "w-full rounded-full border border-border bg-surface-muted py-1.5 pl-9 pr-9 text-sm text-text",
          "placeholder:text-text-muted transition-colors outline-none",
          "hover:border-text-muted focus:border-brand focus:bg-surface focus:ring-2 focus:ring-brand/40",
        )}
        {...props}
      />
      {hasValue && onClear && (
        <button
          type="button"
          aria-label="Clear search"
          onClick={onClear}
          className="absolute right-2 top-1/2 inline-flex h-5 w-5 -translate-y-1/2 items-center justify-center rounded-full text-text-muted transition-colors hover:bg-surface hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand"
        >
          ✕
        </button>
      )}
    </div>
  );
}

export function Checkbox({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      type="checkbox"
      className={cx(
        "h-4 w-4 shrink-0 rounded border-border bg-surface accent-brand transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/40",
        "disabled:cursor-not-allowed disabled:opacity-60",
        className,
      )}
      {...props}
    />
  );
}

/** A checkbox with an inline label (and optional help tooltip). */
export function CheckboxField({
  label,
  help,
  className,
  ...props
}: InputHTMLAttributes<HTMLInputElement> & { label: ReactNode; help?: ReactNode }) {
  return (
    <label className="flex items-center gap-2 text-sm text-text">
      <Checkbox className={className} {...props} />
      <span>{label}</span>
      {help && <Help>{help}</Help>}
    </label>
  );
}

export function Spinner() {
  return (
    <div role="status" aria-label="Loading" className="flex justify-center py-8">
      <span className="h-5 w-5 animate-spin rounded-full border-2 border-border border-t-brand" />
    </div>
  );
}

export function ErrorNote({ error }: { error: ApiError | Error | null }) {
  if (!error) return null;
  const help = error instanceof ApiError ? helpFor(error.code) : null;
  return (
    <div
      role="alert"
      className="rounded-control border border-danger/40 bg-danger/10 p-3 text-sm text-danger"
    >
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
    equipment_in_use:
      "Someone else has this equipment enabled; it is never force-ended automatically.",
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
    <span className="relative inline-flex">
      <button
        type="button"
        aria-label="Help"
        aria-expanded={open}
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          setOpen((o) => !o);
        }}
        onBlur={() => setOpen(false)}
        onKeyDown={(e) => {
          if (e.key === "Escape") setOpen(false);
        }}
        className="inline-flex h-5 w-5 items-center justify-center rounded-full border border-border text-[11px] text-text-muted transition-colors hover:bg-surface-muted hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand"
      >
        ?
      </button>
      {open && (
        <span className="absolute left-6 top-0 z-20 w-56 rounded-control border border-border bg-surface p-2 text-xs leading-relaxed text-text-muted shadow-md">
          {children}
        </span>
      )}
    </span>
  );
}

export function Modal({
  title,
  children,
  onClose,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="w-full max-w-lg rounded-card border border-border bg-surface p-4 shadow-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-text">{title}</h2>
          <IconButton aria-label="Close" onClick={onClose}>
            ✕
          </IconButton>
        </div>
        {children}
      </div>
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-card border border-dashed border-border px-6 py-8 text-center text-sm text-text-muted">
      {children}
    </div>
  );
}
