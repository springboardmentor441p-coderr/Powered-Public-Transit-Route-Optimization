import type { ReactNode } from "react";
import { AlertTriangle, ChevronLeft, ChevronRight, Info, Inbox, Loader2 } from "lucide-react";
import type { PaginationMeta } from "../types/api";

export function formatNum(v: number | null | undefined, digits = 2): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "N/A";
  return v.toLocaleString("en-US", {
    minimumFractionDigits: Number.isInteger(v) && digits === 0 ? 0 : Math.min(digits, 2),
    maximumFractionDigits: digits,
  });
}

export function formatInt(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "N/A";
  return Math.round(v).toLocaleString("en-US");
}

export function LoadingState({ label = "Loading analytical data..." }: { label?: string }) {
  return (
    <div
      role="status"
      aria-live="polite"
      className="flex flex-col items-center justify-center gap-3 rounded-xl border border-slate-800 bg-slate-900/60 p-10 text-slate-300"
    >
      <Loader2 className="h-6 w-6 animate-spin text-sky-400" />
      <p className="text-sm font-medium">{label}</p>
    </div>
  );
}

export function ErrorState({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div
      role="alert"
      className="flex flex-col gap-3 rounded-xl border border-rose-500/40 bg-rose-950/30 p-5 text-rose-200 sm:flex-row sm:items-center sm:justify-between"
    >
      <div className="flex items-start gap-3">
        <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-rose-400" />
        <div>
          <p className="text-sm font-semibold text-rose-100">Request Failed</p>
          <p className="mt-0.5 text-sm text-rose-200/90">{message}</p>
        </div>
      </div>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="shrink-0 rounded-lg border border-rose-400/50 bg-rose-900/40 px-3.5 py-1.5 text-xs font-semibold text-rose-100 hover:bg-rose-900/70"
        >
          Retry
        </button>
      )}
    </div>
  );
}

export function EmptyState({
  title = "No matching records",
  description = "Try adjusting your filters or date range.",
}: {
  title?: string;
  description?: string;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-xl border border-slate-800 bg-slate-900/40 p-10 text-center text-slate-400">
      <Inbox className="h-7 w-7 text-slate-500" />
      <p className="text-sm font-semibold text-slate-200">{title}</p>
      <p className="max-w-md text-xs text-slate-400">{description}</p>
    </div>
  );
}

export function MethodNote({
  title,
  children,
  tone = "info",
}: {
  title: string;
  children: ReactNode;
  tone?: "info" | "warning";
}) {
  const styles =
    tone === "warning"
      ? "border-amber-500/40 bg-amber-950/25 text-amber-100"
      : "border-sky-500/30 bg-sky-950/20 text-slate-200";
  const iconColor = tone === "warning" ? "text-amber-400" : "text-sky-400";

  return (
    <div className={`flex items-start gap-3 rounded-xl border p-4 text-xs leading-relaxed ${styles}`}>
      <Info className={`mt-0.5 h-4 w-4 shrink-0 ${iconColor}`} />
      <div>
        <span className="font-semibold">{title}: </span>
        <span className="text-slate-300">{children}</span>
      </div>
    </div>
  );
}

export function KpiCard({
  label,
  value,
  subtext,
  accent = "sky",
}: {
  label: string;
  value: string;
  subtext?: string;
  accent?: "sky" | "emerald" | "amber" | "violet";
}) {
  const accentMap = {
    sky: "border-t-sky-400",
    emerald: "border-t-emerald-400",
    amber: "border-t-amber-400",
    violet: "border-t-violet-400",
  } as const;

  return (
    <div
      className={`rounded-xl border border-slate-800 border-t-2 ${accentMap[accent]} bg-slate-900/75 p-4 shadow-sm`}
    >
      <p className="text-xs font-medium uppercase tracking-wider text-slate-400">{label}</p>
      <p className="mt-1.5 text-2xl font-bold tracking-tight text-slate-50">{value}</p>
      {subtext && <p className="mt-1 text-xs text-slate-400">{subtext}</p>}
    </div>
  );
}

export function SectionCard({
  title,
  subtitle,
  actions,
  children,
}: {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="rounded-xl border border-slate-800 bg-slate-900/65 p-5 shadow-sm">
      <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-base font-semibold text-slate-100">{title}</h2>
          {subtitle && <p className="mt-0.5 text-xs text-slate-400">{subtitle}</p>}
        </div>
        {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
      </div>
      {children}
    </section>
  );
}

export function Badge({
  children,
  variant = "slate",
}: {
  children: ReactNode;
  variant?: "slate" | "sky" | "emerald" | "amber" | "rose" | "violet";
}) {
  const map = {
    slate: "bg-slate-800 text-slate-200 border-slate-700",
    sky: "bg-sky-950/70 text-sky-300 border-sky-700/60",
    emerald: "bg-emerald-950/70 text-emerald-300 border-emerald-700/60",
    amber: "bg-amber-950/70 text-amber-300 border-amber-700/60",
    rose: "bg-rose-950/70 text-rose-300 border-rose-700/60",
    violet: "bg-violet-950/70 text-violet-300 border-violet-700/60",
  } as const;
  return (
    <span className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium ${map[variant]}`}>
      {children}
    </span>
  );
}

export function PaginationBar({
  pagination,
  onPageChange,
}: {
  pagination: PaginationMeta;
  onPageChange: (nextOffset: number) => void;
}) {
  const start = pagination.total === 0 ? 0 : pagination.offset + 1;
  const end = pagination.offset + pagination.returned;
  const canPrev = pagination.offset > 0;
  const canNext = pagination.has_more;

  return (
    <div className="mt-4 flex flex-col gap-2 border-t border-slate-800 pt-3 text-xs text-slate-400 sm:flex-row sm:items-center sm:justify-between">
      <p>
        Showing <span className="font-semibold text-slate-200">{start}</span>–
        <span className="font-semibold text-slate-200">{end}</span> of{" "}
        <span className="font-semibold text-slate-200">{pagination.total.toLocaleString("en-US")}</span> records
      </p>
      <div className="flex items-center gap-2">
        <button
          type="button"
          disabled={!canPrev}
          onClick={() => onPageChange(Math.max(0, pagination.offset - pagination.limit))}
          aria-label="Previous page"
          className="inline-flex items-center gap-1 rounded-lg border border-slate-700 bg-slate-800/80 px-3 py-1.5 font-medium text-slate-200 hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-40"
        >
          <ChevronLeft className="h-3.5 w-3.5" />
          Previous
        </button>
        <button
          type="button"
          disabled={!canNext}
          onClick={() => onPageChange(pagination.offset + pagination.limit)}
          aria-label="Next page"
          className="inline-flex items-center gap-1 rounded-lg border border-slate-700 bg-slate-800/80 px-3 py-1.5 font-medium text-slate-200 hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-40"
        >
          Next
          <ChevronRight className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}
