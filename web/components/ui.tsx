"use client";

import clsx from "clsx";
import { Info, Loader2 } from "lucide-react";
import React from "react";

export function Card({ title, subtitle, actions, children, className }: {
  title?: React.ReactNode; subtitle?: React.ReactNode; actions?: React.ReactNode;
  children?: React.ReactNode; className?: string;
}) {
  return (
    <section className={clsx("rounded-xl border border-border bg-white shadow-card", className)}>
      {(title || actions) && (
        <header className="flex items-start justify-between gap-4 border-b border-border px-5 py-3.5">
          <div>
            {title && <h2 className="text-[15px] font-bold text-ink">{title}</h2>}
            {subtitle && <p className="mt-0.5 text-[13px] text-muted">{subtitle}</p>}
          </div>
          {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className="px-5 py-4">{children}</div>
    </section>
  );
}

type BtnProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "accent" | "ghost" | "danger" | "outline"; loading?: boolean; size?: "sm" | "md";
};

export function Button({ variant = "primary", loading, size = "md", className, children, disabled, ...rest }: BtnProps) {
  return (
    <button
      {...rest}
      disabled={disabled || loading}
      className={clsx(
        "inline-flex items-center justify-center gap-2 rounded-lg font-semibold transition disabled:cursor-not-allowed disabled:opacity-50",
        size === "sm" ? "px-3 py-1.5 text-[13px]" : "px-4 py-2 text-sm",
        variant === "primary" && "bg-brand-900 text-white hover:bg-brand-950",
        variant === "accent" && "bg-accent-600 text-white hover:bg-accent-700",
        variant === "outline" && "border border-border bg-white text-ink hover:bg-bg-soft",
        variant === "ghost" && "text-brand-800 hover:bg-bg-soft",
        variant === "danger" && "bg-danger text-white hover:opacity-90",
        className,
      )}
    >
      {loading && <Loader2 className="h-4 w-4 animate-spin" />}
      {children}
    </button>
  );
}

export function Field({ label, hint, children, className }: {
  label: React.ReactNode; hint?: React.ReactNode; children: React.ReactNode; className?: string;
}) {
  return (
    <label className={clsx("block", className)}>
      <span className="mb-1 block text-[13px] font-semibold text-ink">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-[12px] leading-snug text-muted">{hint}</span>}
    </label>
  );
}

export const inputCls =
  "w-full rounded-lg border border-border bg-white px-3 py-2 text-sm text-ink placeholder:text-muted/70 focus:border-accent-500 focus:outline-none focus:ring-2 focus:ring-accent-100";

export function Badge({ tone = "neutral", children }: {
  tone?: "neutral" | "success" | "warning" | "danger" | "info" | "sun"; children: React.ReactNode;
}) {
  return (
    <span className={clsx(
      "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11.5px] font-semibold",
      tone === "neutral" && "bg-bg-soft text-ink-soft",
      tone === "success" && "bg-success-soft text-success",
      tone === "warning" && "bg-warning-soft text-warning",
      tone === "danger" && "bg-danger-soft text-danger",
      tone === "info" && "bg-accent-100 text-accent-800",
      tone === "sun" && "bg-sun-soft text-sun-ink",
    )}>{children}</span>
  );
}

const STATUS_TONE: Record<string, "neutral" | "success" | "warning" | "danger" | "info" | "sun"> = {
  ok: "success", extracted: "sun", empty: "warning", truncated: "warning", refused: "warning",
  out_of_range: "warning", ambiguous: "warning", unparsable: "warning", error: "danger", skipped: "neutral",
  completed: "success", running: "info", created: "neutral", cancelled: "warning", stopped: "warning", failed: "danger",
};

export function StatusBadge({ status }: { status?: string | null }) {
  if (!status) return null;
  return <Badge tone={STATUS_TONE[status] ?? "neutral"}>{status.replace("_", " ")}</Badge>;
}

export function Note({ children, tone = "info" }: { children: React.ReactNode; tone?: "info" | "warning" | "danger" }) {
  return (
    <div className={clsx(
      "flex gap-2.5 rounded-lg border px-3.5 py-2.5 text-[13px] leading-relaxed",
      tone === "info" && "border-accent-200 bg-accent-50 text-accent-900",
      tone === "warning" && "border-warning-soft bg-[#fbf7ea] text-warning",
      tone === "danger" && "border-danger-soft bg-[#fdf3f3] text-danger",
    )}>
      <Info className="mt-0.5 h-4 w-4 shrink-0" />
      <div>{children}</div>
    </div>
  );
}

export function Stat({ label, value, sub }: { label: string; value: React.ReactNode; sub?: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-border bg-bg px-3.5 py-2.5">
      <div className="text-[11.5px] font-semibold uppercase tracking-wide text-muted">{label}</div>
      <div className="mt-0.5 text-lg font-bold text-ink">{value}</div>
      {sub && <div className="text-[12px] text-muted">{sub}</div>}
    </div>
  );
}

export function fmt(v: unknown, digits = 3): string {
  if (v === null || v === undefined || (typeof v === "number" && Number.isNaN(v))) return "—";
  if (typeof v === "number") return Number.isInteger(v) ? String(v) : v.toFixed(digits);
  return String(v);
}

export function ErrorBox({ error }: { error: unknown }) {
  if (!error) return null;
  return <Note tone="danger">{error instanceof Error ? error.message : String(error)}</Note>;
}
