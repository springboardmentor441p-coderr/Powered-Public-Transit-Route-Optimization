import type { ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'
import { AlertCircle, LoaderCircle, RefreshCw, SearchX } from 'lucide-react'

export function PageTitle({ eyebrow, title, description, action }: {
  eyebrow?: string
  title: string
  description?: string
  action?: ReactNode
}) {
  return (
    <div className="mb-7 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div>
        {eyebrow && <p className="mb-2 text-xs font-bold uppercase tracking-[0.18em] text-teal-700">{eyebrow}</p>}
        <h1 className="text-2xl font-bold tracking-tight text-slate-950 sm:text-3xl">{title}</h1>
        {description && <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-500">{description}</p>}
      </div>
      {action}
    </div>
  )
}

export function Panel({ title, subtitle, action, children, className = '' }: {
  title?: string
  subtitle?: string
  action?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <section className={`rounded-2xl border border-slate-200/80 bg-white p-5 shadow-panel sm:p-6 ${className}`}>
      {(title || subtitle || action) && (
        <div className="mb-5 flex items-start justify-between gap-3">
          <div>
            {title && <h2 className="font-semibold text-slate-900">{title}</h2>}
            {subtitle && <p className="mt-1 text-xs leading-5 text-slate-500">{subtitle}</p>}
          </div>
          {action}
        </div>
      )}
      {children}
    </section>
  )
}

export function LoadingState({ label = 'Loading data…' }: { label?: string }) {
  return <div className="flex min-h-40 items-center justify-center gap-3 text-sm text-slate-500"><LoaderCircle className="h-5 w-5 animate-spin text-teal-600" />{label}</div>
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex items-start gap-3 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
      <AlertCircle className="mt-0.5 h-5 w-5 shrink-0" />
      <div className="min-w-0 flex-1"><p className="font-semibold">Data could not be loaded</p><p className="mt-1 break-words text-rose-700">{message}</p></div>
      {onRetry && <button onClick={onRetry} className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1 font-medium hover:bg-rose-100"><RefreshCw className="h-3.5 w-3.5" />Retry</button>}
    </div>
  )
}

export function EmptyState({ title = 'No matching records', detail = 'Try changing your search or filters.' }: { title?: string; detail?: string }) {
  return <div className="flex min-h-40 flex-col items-center justify-center text-center"><SearchX className="mb-3 h-8 w-8 text-slate-300" /><p className="font-medium text-slate-700">{title}</p><p className="mt-1 text-sm text-slate-500">{detail}</p></div>
}

export function DataNotice({ children, tone = 'slate' }: { children: ReactNode; tone?: 'slate' | 'amber' | 'teal' }) {
  const colors = {
    slate: 'border-slate-200 bg-slate-50 text-slate-600',
    amber: 'border-amber-200 bg-amber-50 text-amber-900',
    teal: 'border-teal-100 bg-teal-50 text-teal-900',
  }
  return <div className={`rounded-xl border px-4 py-3 text-xs leading-5 ${colors[tone]}`}>{children}</div>
}

export function MetricCard({ label, value, detail, icon: Icon, accent = 'teal' }: {
  label: string
  value: string
  detail: string
  icon: LucideIcon
  accent?: 'teal' | 'blue' | 'amber' | 'violet'
}) {
  const styles = { teal: 'bg-teal-50 text-teal-700', blue: 'bg-blue-50 text-blue-700', amber: 'bg-amber-50 text-amber-700', violet: 'bg-violet-50 text-violet-700' }
  return (
    <div className="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-panel">
      <div className="flex items-center justify-between"><span className="text-sm font-medium text-slate-500">{label}</span><span className={`grid h-10 w-10 place-items-center rounded-xl ${styles[accent]}`}><Icon className="h-5 w-5" /></span></div>
      <p className="mt-5 text-3xl font-bold tracking-tight text-slate-950">{value}</p>
      <p className="mt-1 text-xs leading-5 text-slate-500">{detail}</p>
    </div>
  )
}

export function formatNumber(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return '—'
  return new Intl.NumberFormat('en-IN', { maximumFractionDigits: digits }).format(value)
}

export function formatDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined || !Number.isFinite(seconds)) return '—'
  const totalMinutes = Math.round(seconds / 60)
  const hours = Math.floor(totalMinutes / 60)
  const minutes = totalMinutes % 60
  return hours ? `${hours}h ${minutes}m` : `${minutes}m`
}
