/** The three non-data states every block can be in. */
export function Loading({ label = 'Loading' }: { label?: string }) {
  return (
    <div role="status" aria-live="polite" className="space-y-2 py-2">
      <span className="sr-only">{label}…</span>
      {[90, 70, 80].map(w => <div key={w} className="h-3 animate-pulse bg-hover" style={{ width: `${w}%` }} />)}
    </div>
  )
}

export function Empty({ message }: { message: string }) {
  return <p className="py-4 text-base text-ink-2">{message}</p>
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="flex items-start justify-between gap-4 border-l-[3px] border-ink bg-hover px-3 py-2">
      <div>
        <div className="text-base font-semibold">Could not load this</div>
        <div className="text-sm text-ink-2">{message}</div>
      </div>
      {onRetry && <button type="button" onClick={onRetry} className="btn-secondary">Retry</button>}
    </div>
  )
}
