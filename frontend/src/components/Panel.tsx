import type { ReactNode } from 'react'

/** A working surface: white, one 1 px rule, square corners, no shadow. Title + one-line purpose on top;
 *  `howToRead` is the single plain-language line under a chart. */
export function Panel({ title, purpose, howToRead, aside, children, className = '' }: {
  title: string; purpose?: string; howToRead?: string; aside?: ReactNode; children: ReactNode; className?: string
}) {
  return (
    <section className={`border border-rule bg-panel ${className}`}>
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2 border-b border-rule px-4 py-2.5">
        <div>
          <h2 className="text-base font-semibold">{title}</h2>
          {purpose && <p className="text-sm text-ink-2">{purpose}</p>}
        </div>
        {aside}
      </div>
      <div className="px-4 py-3">{children}</div>
      {howToRead && (
        <p className="border-t border-rule px-4 py-2 text-xs text-ink-2">
          <span className="font-semibold text-ink">How to read this: </span>{howToRead}
        </p>
      )}
    </section>
  )
}

/** A label shown exactly as the API sends it. `warn` styles non-reference / caution labels (with words, not colour alone). */
export function ApiLabel({ text, warn = false }: { text: string; warn?: boolean }) {
  return warn
    ? <span className="inline-block border-l-[3px] border-warn-ink bg-warn-bg px-2 py-0.5 text-sm text-warn-ink">{text}</span>
    : <span className="inline-block border border-rule px-2 py-0.5 text-sm text-ink-2">{text}</span>
}

/** A section heading in the page flow: small eyebrow, then a plain question or title. */
export function SectionHead({ eyebrow, title, note }: { eyebrow?: string; title: string; note?: string }) {
  return (
    <div className="mb-3 mt-10 flex flex-wrap items-end justify-between gap-x-6 gap-y-1 border-b border-rule-strong pb-2">
      <div>
        {eyebrow && <div className="eyebrow">{eyebrow}</div>}
        <h2 className="text-lg font-semibold tracking-tight">{title}</h2>
      </div>
      {note && <p className="min-w-0 max-w-[60ch] text-xs text-ink-2">{note}</p>}
    </div>
  )
}
