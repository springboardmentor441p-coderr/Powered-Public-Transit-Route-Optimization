// Shared stops (route overlap review, from spec 9.16.2 "Review priorities"): every pair of routes that share stops
// in a chosen timetable, both overlap measures side by side, the stop-share strip and a map for the selected pair,
// and the "corridor review only" label. Every number and sentence is computed from the API (CLAUDE.md).
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import type { OverlapResponse, OverlapRow } from '../api/types'
import { useApi } from '../api/useApi'
import { AsyncBlock } from '../components/AsyncBlock'
import { MapCaption } from '../components/MapCaption'
import { ApiLabel, Panel } from '../components/Panel'
import { RouteMap } from '../components/RouteMap'
import { RouteSign } from '../components/RouteSign'
import { Choice, Sentence } from '../components/Sentence'
import { StopShareStrip } from '../components/StopShareStrip'
import { fmt, fmtPct } from '../lib/format'
import { fullyInside, involving, pairKey, sortPairs, topAgreement, type OverlapMeasure } from '../lib/sharedStops'

const PAGE_ROWS = 25
const TOP_N = 10
const MEASURE_TEXT: Record<OverlapMeasure, string> = { jaccard: 'Jaccard stop overlap', smaller: 'share of the smaller route' }

export function SharedStopsPage() {
  const [version, setVersion] = useState<string | undefined>(undefined)
  const overlap = useApi(o => api.overlap({ geometry_version: version }, o), `overlap:${version ?? 'default'}`)
  return (
    <div>
      <div className="eyebrow">Shared stops</div>
      <h1 className="text-xl font-semibold tracking-tight">Which routes share stops?</h1>
      <div className="mt-4">
        <AsyncBlock state={overlap} retry={overlap.retry} label="Loading the route overlap review" isEmpty={o => o.rows.length === 0}
                    emptyMessage={o => `No route pairs share stops in timetable ${o.geometry_version}.`}>
          {o => <SharedBody o={o} onVersion={setVersion} />}
        </AsyncBlock>
      </div>
    </div>
  )
}

function SharedBody({ o, onVersion }: { o: OverlapResponse; onVersion: (v: string) => void }) {
  const [by, setBy] = useState<OverlapMeasure>('jaccard')
  const [lowestFirst, setLowestFirst] = useState(false)
  const [route, setRoute] = useState('')
  const [all, setAll] = useState(false)
  const [picked, setPicked] = useState<string | null>(null)
  const routes = useApi(op => api.routes({}, op), 'routes')
  const groupOf = routes.status === 'ok' ? new Map(routes.data.routes.map(r => [r.route, r.group_id])) : new Map<string, number | null>()

  const rows = sortPairs(involving(o.rows, route), by, lowestFirst)
  const visible = all ? rows : rows.slice(0, PAGE_ROWS)
  const selected = rows.find(r => pairKey(r) === picked) ?? rows[0]
  const agree = topAgreement(o.rows, TOP_N)
  const inside = fullyInside(o.rows)
  const routeList = [...new Set(o.rows.flatMap(r => [r.route_a, r.route_b]))].sort((a, b) => a.localeCompare(b, undefined, { numeric: true }))

  return (
    <div>
      <Sentence>
        Showing pairs of routes that share stops in timetable{' '}
        <Choice label="Timetable" value={o.geometry_version} onChange={onVersion}
                options={o.available_geometry_versions.map(v => ({ value: v, text: v === o.default_geometry_version ? `${v} (default)` : v }))} />,
        {' '}involving <Choice label="Route filter" value={route} onChange={v => { setRoute(v); setPicked(null) }}
                               options={[{ value: '', text: 'any route' }, ...routeList.map(r => ({ value: r, text: `route ${r}` }))]} />,
        {' '}sorted by <Choice label="Sort by" value={by} onChange={setBy}
                               options={(Object.keys(MEASURE_TEXT) as OverlapMeasure[]).map(m => ({ value: m, text: MEASURE_TEXT[m] }))} />,
        {' '}<Choice label="Order" value={lowestFirst ? 'low' : 'high'} onChange={v => setLowestFirst(v === 'low')}
                     options={[{ value: 'high', text: 'highest first' }, { value: 'low', text: 'lowest first' }]} />.
      </Sentence>

      {o.metric.caveat && <div className="mb-4"><ApiLabel warn text={o.metric.caveat} /></div>}

      <div className="space-y-2 border-l-[3px] border-brand pl-4 text-md leading-8">
        <p>
          <span className="font-semibold num">{fmt(o.counts.pairs)}</span> route pairs share at least one stop in this timetable.{' '}
          {agree && <>Of the top {fmt(agree.n)} pairs by Jaccard, <span className="font-semibold num">{fmt(agree.both)}</span> are also in the
            top {fmt(agree.n)} by share of the smaller route{agree.both < agree.n
              ? ': "these two routes are alike" and "one route sits inside another" are different questions.'
              : ': here both measures pick the same pairs.'}</>}
        </p>
        <p>
          In <span className="font-semibold num">{fmt(inside)}</span> {inside === 1 ? 'pair' : 'pairs'}, every stop of the smaller route is
          also served by the other route.
        </p>
      </div>

      <div className="mt-6 grid items-start gap-4 xl:grid-cols-[minmax(0,7fr)_minmax(0,5fr)]">
        <Panel title={`${fmt(rows.length)} pairs${route ? ` involving route ${route}` : ''}`}
               purpose={`Sorted by ${MEASURE_TEXT[by]}, ${lowestFirst ? 'lowest' : 'highest'} first. Choose "show" on a row to see that pair.`}
               howToRead="Jaccard is shared stops ÷ all stops on either route (1 = the same stops). Share of the smaller route is shared stops ÷ the shorter route's stops (100 % = the shorter route lies inside the longer). The last two columns are each route's stops that the other does not serve.">
          <div className="-mx-4 overflow-x-auto">
            <table className="data-table">
              <thead><tr>
                <th>Route pair</th><th className="n">Shared stops</th>
                <th className={`n ${by === 'jaccard' ? 'text-ink' : ''}`}>Jaccard{by === 'jaccard' && ' ▾'}</th>
                <th className={`n ${by === 'smaller' ? 'text-ink' : ''}`}>Share of smaller route{by === 'smaller' && ' ▾'}</th>
                <th className="n">First route alone</th><th className="n">Second route alone</th>
              </tr></thead>
              <tbody>
                {visible.map(r => {
                  const isSel = selected != null && pairKey(r) === pairKey(selected)
                  return (
                    <tr key={pairKey(r)} className={isSel ? 'bg-hover' : ''}>
                      <td className="whitespace-nowrap">
                        <button type="button" className="mr-2 text-xs text-ink-2 underline" onClick={() => setPicked(pairKey(r))}
                                aria-pressed={isSel} aria-label={`Show routes ${r.route_a} and ${r.route_b}`}>show</button>
                        <PairSigns r={r} groupOf={groupOf} />
                      </td>
                      <td className="n num">{fmt(r.shared_stop_count)} <span className="text-xs text-ink-2">of {fmt(r.route_a_stop_count)} / {fmt(r.route_b_stop_count)}</span></td>
                      <td className="n num">{fmt(r.jaccard_stop_overlap, 3)}</td>
                      <td className="n num">{fmtPct(r.smaller_route_stop_overlap)} %</td>
                      <td className="n num">{fmtPct(r.route_a_exclusive_fraction)} %</td>
                      <td className="n num">{fmtPct(r.route_b_exclusive_fraction)} %</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          {rows.length > PAGE_ROWS && (
            <button type="button" className="btn-secondary mt-3" onClick={() => setAll(a => !a)}>
              {all ? `Show the first ${PAGE_ROWS}` : `Show all ${rows.length} pairs`}
            </button>
          )}
        </Panel>
        {selected && <PairPanel r={selected} o={o} groupOf={groupOf} />}
      </div>
    </div>
  )
}

function PairSigns({ r, groupOf }: { r: OverlapRow; groupOf: Map<string, number | null> }) {
  return <>
    <Link to={`/route/${encodeURIComponent(r.route_a)}`} className="no-underline" aria-label={`Open route ${r.route_a}`}>
      <RouteSign route={r.route_a} groupId={groupOf.get(r.route_a)} size="sm" /></Link>
    {' and '}
    <Link to={`/route/${encodeURIComponent(r.route_b)}`} className="no-underline" aria-label={`Open route ${r.route_b}`}>
      <RouteSign route={r.route_b} groupId={groupOf.get(r.route_b)} size="sm" /></Link>
  </>
}

function PairPanel({ r, o, groupOf }: { r: OverlapRow; o: OverlapResponse; groupOf: Map<string, number | null> }) {
  const lines = useApi(op => api.mapLines({ routes: [r.route_a, r.route_b], geometry_version: o.geometry_version }, op),
                       `lines:${r.route_a},${r.route_b}:${o.geometry_version}`)
  return (
    <Panel title={`Routes ${r.route_a} and ${r.route_b}`} purpose={`Review rank #${r.rank} by Jaccard in timetable ${o.geometry_version}.`}
           howToRead="Top bar: the first route's stops; bottom bar: the second's. The dark middle is the stops both serve. Bar widths are stop counts, not distances.">
      <StopShareStrip a={{ route: r.route_a, groupId: groupOf.get(r.route_a) ?? null, stops: r.route_a_stop_count }}
                      b={{ route: r.route_b, groupId: groupOf.get(r.route_b) ?? null, stops: r.route_b_stop_count }}
                      shared={r.shared_stop_count} jaccard={r.jaccard_stop_overlap} smallerOverlap={r.smaller_route_stop_overlap} />
      <div className="-mx-4 -mb-3 mt-4">
        <AsyncBlock state={lines} retry={lines.retry} label="Loading the map" isEmpty={m => m.lines.length === 0}
                    emptyMessage={m => m.routes_without_lines.map(x => `Route ${x.route}: ${x.reason}`).join('; ') || 'No lines for these routes.'}>
          {m => <>
            <RouteMap lines={m.lines} height={300} weight={3} />
            <MapCaption geometryVersion={m.geometry_version} appliedStart={m.applied.start} appliedEnd={m.applied.end}
                        pathLabel={m.label} displayNote={m.display.note} />
          </>}
        </AsyncBlock>
      </div>
    </Panel>
  )
}
