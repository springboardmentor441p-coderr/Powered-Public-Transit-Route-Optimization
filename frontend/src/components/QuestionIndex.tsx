import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

/** The Start page's spine: planner questions as full-width rows, each with a live one-line answer preview. */
export function QuestionIndex({ rows }: {
  rows: { question: string; preview: ReactNode; to: string; quiet?: boolean }[]
}) {
  return (
    <ol className="border-t border-rule-strong">
      {rows.map((r, i) => (
        <li key={r.to} className="grid grid-cols-[32px_minmax(0,1fr)_auto] items-baseline gap-4 border-b border-rule py-4">
          <span className="num text-sm text-ink-2">{r.quiet ? '' : String(i + 1).padStart(2, '0')}</span>
          <div>
            <h3 className={r.quiet ? 'text-md font-semibold text-ink-2' : 'text-lg font-semibold tracking-tight'}>{r.question}</h3>
            <div className="mt-1 flex flex-wrap items-center gap-1.5 text-sm text-ink-2">{r.preview}</div>
          </div>
          <Link to={r.to} className="text-sm font-semibold">Open<span className="sr-only">: {r.question}</span></Link>
        </li>
      ))}
    </ol>
  )
}
