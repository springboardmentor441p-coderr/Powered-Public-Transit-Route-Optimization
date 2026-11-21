import { fmt } from '../lib/format'
import { stopShare } from '../lib/stopShare'
import { RouteSign } from './RouteSign'

const STOP_SETS_NOTE = 'stop sets, not stop order: how many stops are shared, not where'

/** A route's own-stops segment. A narrow one shows just the count (the words move to the tooltip), so the text is
 *  never cut off; it keeps a minimum width so the count always fits. */
function OnlySeg({ n, route, frac, className, pct }: { n: number; route: string; frac: number; className: string; pct: (f: number) => string }) {
  const words = `${fmt(n)} ${n === 1 ? 'stop' : 'stops'} only on ${route}`
  return <div className={`${className} justify-center`} style={{ width: pct(frac), minWidth: '1.75rem' }} title={words} aria-label={words}>
    {frac < 0.2 ? fmt(n) : `${fmt(n)} only`}</div>
}

/** Two bars aligned on their shared stops: [A only | shared] over [shared | B only]. Widths are stop counts. */
export function StopShareStrip({ a, b, shared, jaccard, smallerOverlap, interpretation }: {
  a: { route: string; groupId: number | null; stops: number }
  b: { route: string; groupId: number | null; stops: number }
  shared: number; jaccard: number; smallerOverlap: number
  interpretation?: string              // left out when the page already shows the label once
}) {
  const s = stopShare(a.stops, b.stops, shared)
  const pct = (f: number) => `${(f * 100).toFixed(4)}%`
  const seg = 'flex h-6 items-center overflow-hidden whitespace-nowrap px-1.5 text-xs'
  const sharedSeg = `${seg} justify-center bg-brand font-semibold text-white`
  const onlySeg = `${seg} border border-rule-strong bg-panel text-ink-2`
  return (
    <figure>
      <div className="grid grid-cols-[56px_minmax(0,1fr)] items-center gap-x-3 gap-y-1.5">
        <RouteSign route={a.route} groupId={a.groupId} />
        <div className="flex" style={{ width: pct(s.a.only + s.a.shared) }}>
          {s.aOnly > 0 && <OnlySeg n={s.aOnly} route={a.route} frac={s.a.only / (s.a.only + s.a.shared)} className={onlySeg} pct={pct} />}
          <div className={sharedSeg} style={{ flex: 1 }}>{fmt(s.shared)} shared</div>
        </div>
        <RouteSign route={b.route} groupId={b.groupId} />
        <div className="flex" style={{ marginLeft: pct(s.a.only), width: pct(s.b.shared + s.b.only) }}>
          <div className={sharedSeg} style={{ flex: 1 }}>{fmt(s.shared)} shared</div>
          {s.bOnly > 0 && <OnlySeg n={s.bOnly} route={b.route} frac={s.b.only / (s.b.shared + s.b.only)} className={onlySeg} pct={pct} />}
        </div>
      </div>
      <figcaption className="mt-2 space-y-1 text-xs text-ink-2">
        <div>
          <span className="num">{fmt(a.stops)}</span> stops on {a.route}, <span className="num">{fmt(b.stops)}</span> on {b.route},{' '}
          <span className="num">{fmt(shared)}</span> in both · Jaccard <span className="num">{fmt(jaccard, 3)}</span>
          {' '}· smaller-route overlap <span className="num">{fmt(smallerOverlap, 3)}</span> · {STOP_SETS_NOTE}
        </div>
        {interpretation && <div className="border-l-[3px] border-warn-ink bg-warn-bg px-2 py-1 text-warn-ink">{interpretation}</div>}
      </figcaption>
    </figure>
  )
}
