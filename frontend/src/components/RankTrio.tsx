import { stability } from '../lib/stability'
import { Num, type ProvenanceInfo } from './Provenance'

export type RankCell = {
  metricLabel: string
  value: ProvenanceInfo                // the number, with its provenance
  rank: number | null
  of: number
  reason?: string | null               // why unranked
  dev: { rank: number | null; reason?: string | null }   // same ranking over the development period
}

/** Three ranks side by side: one per named ranking (spec 9.12), each with its value, rank and stability. */
export function RankTrio({ cells }: { cells: RankCell[] }) {
  return (
    <div className="grid border border-rule bg-panel md:grid-cols-3">
      {cells.map((c, i) => {
        const s = stability(c.dev, { rank: c.rank, reason: c.reason })
        return (
          <div key={c.metricLabel} className={`min-w-0 px-4 py-3 ${i ? 'border-t border-rule md:border-l md:border-t-0' : ''}`}>
            <div className="text-sm text-ink-2">{c.metricLabel}</div>
            <div className="mt-1 text-xl font-semibold tracking-tight"><Num p={c.value} /></div>
            <div className="mt-1 text-sm">
              {c.rank == null
                ? <span className="text-xs text-ink-2">unranked – {c.reason ?? 'no reason given'}</span>
                : <><span className="font-semibold">rank {c.rank}</span> <span className="text-ink-2">of {c.of}</span></>}
            </div>
            <div className={`mt-2 border-t border-rule pt-2 text-xs ${s.kind === 'not_comparable' ? 'text-ink-2' : 'text-ink'}`}>
              <span className="font-semibold">Stability: </span>{s.text}
            </div>
          </div>
        )
      })}
    </div>
  )
}
