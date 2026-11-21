import { createContext, useContext, useState, type ReactNode } from 'react'
import { fmt } from '../lib/format'
import { Drawer } from './Drawer'
import { Value } from './Value'

/** Everything needed to answer "How was this number made?". Filled from API fields only. */
export type ProvenanceInfo = {
  title: string                        // e.g. "Route 49 · rides per scheduled hour"
  value: number | null
  digits?: number
  unit?: string
  formula: string                      // in words: "recorded rides ÷ scheduled trip-hours"
  numerator?: { label: string; value: number | null; digits?: number }
  denominator?: { label: string; value: number | null; digits?: number }
  days?: { observed: number; gateLabel?: string }
  period?: { name: string; start: string; end: string }
  daytype?: string
  timetables?: { id: string; start: string; end: string }[]
  missing?: { reason: string; side?: string }
  dataVersion: string
  request: string                      // the exact API request, e.g. /api/rankings?metric=...
}

const Ctx = createContext<(p: ProvenanceInfo) => void>(() => undefined)

export function ProvenanceProvider({ children }: { children: ReactNode }) {
  const [current, setCurrent] = useState<ProvenanceInfo | null>(null)
  return (
    <Ctx.Provider value={setCurrent}>
      {children}
      {current && <Drawer eyebrow="How was this number made?" title={current.title} onClose={() => setCurrent(null)}>
        <ProvenanceBody p={current} />
      </Drawer>}
    </Ctx.Provider>
  )
}

/** A number that opens its own provenance. Dotted underline = "you can ask where this came from". */
export function Num({ p, className = '' }: { p: ProvenanceInfo; className?: string }) {
  const open = useContext(Ctx)
  return (
    <button type="button" onClick={() => open(p)} title="How was this number made?"
            className={`cursor-help border-b border-dotted border-ink-2 text-left hover:border-ink hover:bg-hover ${className}`}>
      <Value value={p.value} digits={p.digits} unit={p.unit} reason={p.missing?.reason} />
    </button>
  )
}

function Row({ k, children }: { k: string; children: ReactNode }) {
  return (
    <div className="grid grid-cols-[110px_minmax(0,1fr)] gap-3 break-words border-b border-rule py-2 text-sm last:border-b-0">
      <dt className="text-ink-2">{k}</dt><dd>{children}</dd>
    </div>
  )
}

export function ProvenanceBody({ p }: { p: ProvenanceInfo }) {
  const n = p.numerator, d = p.denominator
  return (
    <div>
      <div className="mb-3 text-xl font-semibold"><Value value={p.value} digits={p.digits} unit={p.unit} reason={p.missing?.reason} /></div>
      <dl>
        <Row k="Formula">{p.formula}</Row>
        {n && d && (
          <Row k="Calculation">
            <span className="num">{fmt(n.value, n.digits ?? 0)}</span> <span className="text-ink-2">{n.label}</span>
            <span className="px-1.5">÷</span>
            <span className="num">{fmt(d.value, d.digits ?? 0)}</span> <span className="text-ink-2">{d.label}</span>
            <span className="px-1.5">=</span>
            <Value value={p.value} digits={p.digits} reason={p.missing?.reason} />
          </Row>
        )}
        {p.missing && <Row k="Why missing">{p.missing.reason}{p.missing.side && <span className="text-ink-2"> ({p.missing.side})</span>}</Row>}
        {p.days && <Row k="Days counted"><span className="num">{fmt(p.days.observed)}</span> observed days{p.days.gateLabel && <span className="text-ink-2"> · {p.days.gateLabel}</span>}</Row>}
        {p.period && <Row k="Period">{p.period.name}: <span className="num">{p.period.start} to {p.period.end}</span></Row>}
        {p.daytype && <Row k="Day type">{p.daytype}</Row>}
        {p.timetables && (
          <Row k="Timetables">
            <ul className="space-y-0.5">{p.timetables.map(t => <li key={t.id} className="num">{t.id} <span className="text-ink-2">applied {t.start} to {t.end}</span></li>)}</ul>
          </Row>
        )}
        <Row k="Data version"><span className="num break-all">{p.dataVersion}</span></Row>
        <Row k="Request"><code className="break-all font-mono text-xs">{p.request}</code></Row>
      </dl>
    </div>
  )
}
