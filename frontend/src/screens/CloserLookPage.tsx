// Closer look (spec 9.16.2 "Review priorities"): the three named rankings side by side, with rank stability
// between the development period and the full matched window, the unranked routes and why, and the route overlap
// review as a fourth view. Every number and sentence is computed from API responses at render time (CLAUDE.md).
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, buildUrl } from '../api/client'
import { useRequestScope, type RequestScope } from '../api/cutoff'
import type { DayType, OverlapResponse, PeriodName, RankingMetric, RankingResponse, RankingRow, RouteRow } from '../api/types'
import { useApi, type ApiState } from '../api/useApi'
import { AsyncBlock } from '../components/AsyncBlock'
import { ApiLabel, Panel } from '../components/Panel'
import { Num, type ProvenanceInfo } from '../components/Provenance'
import { RouteSign } from '../components/RouteSign'
import { Choice, NumberChoice, Sentence } from '../components/Sentence'
import { Value } from '../components/Value'
import { METRIC_ORDER, displayedGate, higherMeans, orderRanked, parseMinDays, rankMovement, topOverlap, unrankedSummary } from '../lib/closerLook'
import { fmtRange } from '../lib/dates'
import { rankingProvenance } from '../lib/provenance'
import { fmt, fmtPct } from '../lib/format'
import { stability } from '../lib/stability'
import { compareRoutes } from '../lib/routeSort'

const OVERLAP = 'route_overlap_review'
type View = RankingMetric | typeof OVERLAP
const PAGE_ROWS = 25
const TOP_N = 10

const VIEW_TEXT: Record<View, string> = {
  observed_daily_demand: 'observed daily demand', rides_per_scheduled_trip: 'rides per scheduled trip',
  rides_per_scheduled_hour: 'rides per scheduled hour', route_overlap_review: 'route overlap review',
}
const DAYTYPE_TEXT: Record<DayType, string> = { W: 'weekdays', A: 'Saturdays', U: 'Sundays and holidays' }
const PERIOD_TEXT: Record<PeriodName, string> = { full_matched_window: 'the full matched window', development: 'the development period' }

type Query = { daytype: DayType; min_days?: number; group_id?: number }

/** One ranking request (metric x period) for the current day type, gate and peer group. */
function useRanking(metric: RankingMetric, period: PeriodName, q: Query) {
  const key = `rank:${metric}:${period}:${q.daytype}:${q.min_days ?? 'ref'}:${q.group_id ?? 'all'}`
  return useApi(o => api.rankings({ metric, period, ...q }, o), key)
}

const allOk = <T,>(states: ApiState<T>[]): states is { status: 'ok'; data: T }[] => states.every(s => s.status === 'ok')

// ---- the page --------------------------------------------------------------------------------------------------------
export function CloserLookPage() {
  const scope = useRequestScope()
  const [view, setView] = useState<View>('rides_per_scheduled_hour')
  const [daytype, setDaytype] = useState<DayType>('W')
  const [period, setPeriod] = useState<PeriodName>('full_matched_window')
  const [minDays, setMinDays] = useState<number | null>(null)          // null = the API's reference gate
  const [peerChoice, setPeer] = useState<string>('all')
  const [lowestFirst, setLowestFirst] = useState(false)

  const groups = useApi(o => api.groups(o), 'groups')
  const routes = useApi(o => api.routes({}, o), 'routes')
  const groupsOk = groups.status === 'ok' && groups.data.available ? groups.data : null
  // Under a cutoff before the groups were fitted, the API refuses group_id: rank among all routes, with the reason.
  const peer = groupsOk ? peerChoice : 'all'

  const q: Query = { daytype, min_days: minDays ?? undefined, group_id: peer === 'all' ? undefined : Number(peer) }
  const full = { observed_daily_demand: useRanking('observed_daily_demand', 'full_matched_window', q),
                 rides_per_scheduled_trip: useRanking('rides_per_scheduled_trip', 'full_matched_window', q),
                 rides_per_scheduled_hour: useRanking('rides_per_scheduled_hour', 'full_matched_window', q) }
  const dev = { observed_daily_demand: useRanking('observed_daily_demand', 'development', q),
                rides_per_scheduled_trip: useRanking('rides_per_scheduled_trip', 'development', q),
                rides_per_scheduled_hour: useRanking('rides_per_scheduled_hour', 'development', q) }
  const shown = period === 'full_matched_window' ? full : dev
  const [overlapVersion, setOverlapVersion] = useState<string | undefined>(undefined)
  const overlap = useApi(o => api.overlap({ geometry_version: overlapVersion }, o), `overlap:${overlapVersion ?? 'default'}`)

  const main = view === OVERLAP ? null : shown[view]
  const cfg = main?.status === 'ok' ? main.data.configuration : null
  const reference = cfg?.reference_min_observed_days
  const gate = displayedGate(cfg?.min_observed_days, minDays, reference)

  const routeInfo = useMemo(() => routes.status === 'ok' ? new Map(routes.data.routes.map(r => [r.route, r])) : new Map<string, RouteRow>(),
                            [routes])
  const peerOptions = [{ value: 'all', text: 'all routes' },
    ...(groupsOk?.groups.map(g => ({ value: String(g.group_id), text: `${g.name} (${g.size} routes)` })) ?? [])]
  const peerName = peer === 'all' ? null : groupsOk?.groups.find(g => String(g.group_id) === peer)?.name ?? `group ${peer}`

  return (
    <div>
      <div className="eyebrow">Closer look</div>
      <h1 className="text-xl font-semibold tracking-tight">Which routes deserve a closer look?</h1>

      <div className="mt-4">
        <Sentence>
          Showing <Choice label="Measure" value={view} onChange={setView}
                          options={(Object.keys(VIEW_TEXT) as View[]).map(v => ({ value: v, text: VIEW_TEXT[v] }))} />
          {view === OVERLAP ? (
            <> for timetable <Choice label="Timetable" value={overlapVersion ?? (overlap.status === 'ok' ? overlap.data.geometry_version : '')}
                                     onChange={setOverlapVersion}
                                     options={overlap.status === 'ok' ? overlap.data.available_geometry_versions.map(v => ({
                                       value: v, text: v === overlap.data.default_geometry_version ? `${v} (default)` : v })) : []} />,
              {' '}route pairs <OrderChoice lowestFirst={lowestFirst} onChange={setLowestFirst} /> by shared stops.</>
          ) : (
            <> on <Choice label="Day type" value={daytype} onChange={setDaytype}
                          options={(Object.keys(DAYTYPE_TEXT) as DayType[]).map(d => ({ value: d, text: DAYTYPE_TEXT[d] }))} /> in{' '}
              <Choice label="Period" value={period} onChange={setPeriod}
                      options={(Object.keys(PERIOD_TEXT) as PeriodName[]).map(p => ({ value: p, text: PERIOD_TEXT[p] }))} />
              {main?.status === 'ok' && <span className="text-ink-2"> ({fmtRange(main.data.period.start, main.data.period.end)})</span>},
              {' '}ranked among{' '}
              {groupsOk
                ? <Choice label="Peer group" value={peer} onChange={setPeer} options={peerOptions} />
                : <><span className="font-semibold">all routes</span>{groups.status === 'ok' && !groups.data.available &&
                    <span className="text-xs text-ink-2"> (peer groups unavailable – {groups.data.reason})</span>}</>}
              , <OrderChoice lowestFirst={lowestFirst} onChange={setLowestFirst} />, counting routes with at least{' '}
              {gate != null
                ? <NumberChoice label="Minimum observed days" value={gate} warn={!!cfg?.non_reference_gate}
                                parse={parseMinDays} invalidText="enter a whole number of 1 or more" onChange={setMinDays}
                                suggestions={gateSuggestions(reference).map(n => ({ value: n, text: n === reference ? `${n} (reference)` : String(n) }))} />
                : <span aria-busy>…</span>}{' '}
              observed days.</>
          )}
        </Sentence>
        {view !== OVERLAP && main?.status === 'ok' && (
          <div className="-mt-3 mb-5 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
            <span><span className="num font-semibold">{fmt(main.data.counts.ranked)}</span> of {fmt(main.data.counts.routes)} routes ranked at {fmt(main.data.configuration.min_observed_days)} days</span>
            <ApiLabel warn={main.data.configuration.non_reference_gate} text={main.data.configuration.gate_label} />
            {cfg?.non_reference_gate && (
              <button type="button" className="btn-secondary" onClick={() => setMinDays(null)}>Back to the reference gate</button>
            )}
            {peerName && <span>Ranks restart from 1 within {peerName}: rank 1 is the highest of its {fmt(main.data.counts.routes)} routes on {DAYTYPE_TEXT[daytype]}.</span>}
          </div>
        )}
      </div>

      {view === OVERLAP
        ? <OverlapView s={overlap} lowestFirst={lowestFirst} routeInfo={routeInfo} />
        : <RankingView view={view} shown={shown} full={full} dev={dev} lowestFirst={lowestFirst}
                       routeInfo={routeInfo} scope={scope} q={q} period={period} />}
    </div>
  )
}

/** Common gate values to pick from; any other whole number can be typed. Built around the API's reference gate. */
function gateSuggestions(reference: number | undefined): number[] {
  const base = [1, 5, 10]
  if (reference != null) base.push(reference, reference * 2, reference * 3)
  return [...new Set(base)].sort((a, b) => a - b)
}

function OrderChoice({ lowestFirst, onChange }: { lowestFirst: boolean; onChange: (v: boolean) => void }) {
  return <Choice label="Order" value={lowestFirst ? 'low' : 'high'} onChange={v => onChange(v === 'low')}
                 options={[{ value: 'high', text: 'highest first' }, { value: 'low', text: 'lowest first' }]} />
}

// ---- rankings ------------------------------------------------------------------------------------------------------
type ByMetric = Record<RankingMetric, ApiState<RankingResponse> & { retry: () => void }>

function RankingView({ view, shown, full, dev, lowestFirst, routeInfo, scope, q, period }: {
  view: RankingMetric; shown: ByMetric; full: ByMetric; dev: ByMetric; lowestFirst: boolean
  routeInfo: Map<string, RouteRow>; scope: RequestScope; q: Query; period: PeriodName
}) {
  const [all, setAll] = useState(false)
  const states = [...METRIC_ORDER.map(m => shown[m]), ...METRIC_ORDER.map(m => full[m]), ...METRIC_ORDER.map(m => dev[m])]
  if (!allOk(states)) {
    const bad = states.find(s => s.status !== 'ok')!
    return <AsyncBlock state={bad} retry={() => states.forEach(s => s.retry())} label="Loading the rankings">{() => null}</AsyncBlock>
  }
  const data = (by: ByMetric, m: RankingMetric) => (by[m] as { data: RankingResponse }).data
  const main = data(shown, view)
  const index = (by: ByMetric) => Object.fromEntries(METRIC_ORDER.map(m => [m, new Map(data(by, m).rows.map(r => [r.route, r]))])) as
    Record<RankingMetric, Map<string, RankingRow>>
  const shownIdx = index(shown), fullIdx = index(full), devIdx = index(dev)

  const ranked = orderRanked(main.rows, lowestFirst)
  const unranked = main.rows.filter(r => r.rank == null)
  const visible = all ? ranked : ranked.slice(0, PAGE_ROWS)
  const request = (m: RankingMetric) => buildUrl('/api/rankings', { metric: m, period, ...q }, scope)

  const prov = (m: RankingMetric, r: RankingRow | undefined, route: string): ProvenanceInfo =>
    rankingProvenance(data(shown, m), r, route, request(m))

  return (
    <div className="space-y-6">
      <Insight view={view} shown={Object.fromEntries(METRIC_ORDER.map(m => [m, data(shown, m)])) as Record<RankingMetric, RankingResponse>}
               full={data(full, view)} dev={data(dev, view)} />

      <Panel title={`Ranked routes: ${fmt(ranked.length)}`}
             purpose={`${higherMeans(main.metric.numerator_label, main.metric.denominator_label)} Sorted by ${main.metric.label.toLowerCase()}, ${lowestFirst ? 'lowest' : 'highest'} first.`}
             howToRead={`Each route shows its value and rank (#n, ties share a rank) on all three measures, in the unit under each heading; the sorted measure is marked ▾. Stability compares the route's rank in the development period with the full matched window, on the same day type and gate. Click a value for how it was made. ${main.metric.caveat}`}>
        <div className="-mx-4 overflow-x-auto">
          <table className="data-table">
            <thead>
              <tr>
                <th rowSpan={2}>Route</th><th rowSpan={2}>Name</th>
                {METRIC_ORDER.map(m => <th key={m} colSpan={2} className={m === view ? 'font-semibold text-ink' : ''}>
                  {data(shown, m).metric.label}{m === view && ' ▾'}</th>)}
                <th rowSpan={2} className="n">Observed days</th>
              </tr>
              <tr>{METRIC_ORDER.map(m => [<th key={`${m}v`} className="n">{data(shown, m).metric.unit} · rank</th>, <th key={`${m}s`}>Stability</th>])}</tr>
            </thead>
            <tbody>
              {visible.map(r => (
                <tr key={r.route}>
                  <td><RouteLink route={r.route} info={routeInfo.get(r.route)} /></td>
                  <td className="text-sm">{routeInfo.get(r.route)?.route_long_name ?? <span className="text-xs text-ink-2">no name in the timetables</span>}</td>
                  {METRIC_ORDER.map(m => [
                    <td key={`${m}v`} className="n"><RankCell p={prov(m, shownIdx[m].get(r.route), r.route)} row={shownIdx[m].get(r.route)} /></td>,
                    <td key={`${m}s`}><StabilityCell dev={devIdx[m].get(r.route)} full={fullIdx[m].get(r.route)} /></td>,
                  ])}
                  <td className="n num">{fmt(r.observed_days)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {ranked.length > PAGE_ROWS && (
          <button type="button" className="btn-secondary mt-3" onClick={() => setAll(a => !a)}>
            {all ? `Show the first ${PAGE_ROWS}` : `Show all ${ranked.length} ranked routes`}
          </button>
        )}
      </Panel>

      <UnrankedPanel rows={unranked} routeInfo={routeInfo} metricLabel={main.metric.label} />
    </div>
  )
}

function RouteLink({ route, info }: { route: string; info: RouteRow | undefined }) {
  return (
    <Link to={`/route/${encodeURIComponent(route)}`} className="no-underline" aria-label={`Open route ${route}`}>
      <RouteSign route={route} groupId={info?.group_id} groupName={info?.group_name} size="sm" />
    </Link>
  )
}

function RankCell({ p, row }: { p: ProvenanceInfo; row: RankingRow | undefined }) {
  return (
    <span className="whitespace-nowrap">
      <Num p={p} showUnit={false} />
      {row?.rank != null
        ? <span className="ml-1.5 text-xs text-ink-2">#{row.rank}</span>
        : <span className="ml-1.5 text-xs text-ink-2">unranked</span>}
    </span>
  )
}

function StabilityCell({ dev, full }: { dev: RankingRow | undefined; full: RankingRow | undefined }) {
  const s = stability({ rank: dev?.rank ?? null, reason: dev?.reason ?? 'not in this ranking' },
                      { rank: full?.rank ?? null, reason: full?.reason ?? 'not in this ranking' })
  if (s.kind === 'not_comparable') return <span className="whitespace-nowrap text-xs text-ink-2" title={s.text}>not comparable</span>
  return (
    <span className="whitespace-nowrap text-xs" title={s.text}>
      <span className="num">#{dev!.rank} → #{full!.rank}</span>
      <span className="ml-1.5 text-ink-2">{s.kind === 'same' ? 'same' : `${s.places} ${s.direction}`}</span>
    </span>
  )
}

/** The two insight sentences. Every number is counted from the responses; the wording only follows the counts. */
function Insight({ view, shown, full, dev }: {
  view: RankingMetric; shown: Record<RankingMetric, RankingResponse>; full: RankingResponse; dev: RankingResponse
}) {
  const other: RankingMetric = view === 'observed_daily_demand' ? 'rides_per_scheduled_hour' : 'observed_daily_demand'
  const t = topOverlap(shown[view].rows, shown[other].rows, TOP_N)
  const mv = rankMovement(dev.rows, full.rows)
  const a = shown[view].metric.label.toLowerCase(), b = shown[other].metric.label.toLowerCase()
  return (
    <div className="space-y-2 border-l-[3px] border-brand pl-4 text-md leading-8">
      <p>
        {t == null
          ? <>No route is ranked on both {a} and {b} here, so their top routes cannot be compared.</>
          : <>Of the top {fmt(t.n)} routes by {a}, <span className="font-semibold num">{fmt(t.both)}</span> {t.both === 1 ? 'is' : 'are'} also
              in the top {fmt(t.n)} by {b}
              {t.both === t.n ? ': on these settings the two measures agree on who leads.'
                : ': the measure you rank by changes which routes lead, so each ranking is a prompt to look, not a verdict.'}</>}
      </p>
      <p>
        {mv.compared === 0
          ? <>No route is ranked in both the development period and the full matched window, so rank stability cannot be shown.</>
          : <>Between the development period and the full matched window, <span className="font-semibold num">{fmt(mv.same)}</span> of{' '}
              {fmt(mv.compared)} routes ranked in both keep the same place on {a}, and{' '}
              <span className="font-semibold num">{fmt(mv.within3)}</span> move 3 places or fewer.</>}
      </p>
    </div>
  )
}

function UnrankedPanel({ rows, routeInfo, metricLabel }: { rows: RankingRow[]; routeInfo: Map<string, RouteRow>; metricLabel: string }) {
  const s = unrankedSummary(rows)
  return (
    <Panel title={`Not ranked: ${fmt(s.total)}`} purpose={`Routes left out of the ${metricLabel.toLowerCase()} ranking, each with the API's reason. They are listed, never given a rank of 0.`}>
      {s.total === 0
        ? <p className="text-sm text-ink-2">Every route on these settings is ranked.</p>
        : <>
            <p className="mb-3 text-sm">
              <span className="font-semibold">Why unranked: </span>{fmt(s.total)} unranked:{' '}
              {s.parts.map((p, i) => <span key={p.reason}>{i > 0 && ', '}{p.reason} (<span className="num">{fmt(p.count)}</span>)</span>)}.
            </p>
            <div className="-mx-4 overflow-x-auto">
              <table className="data-table">
                <thead><tr><th>Route</th><th>Name</th><th>Reason</th><th className="n">Observed days</th><th className="n">Scheduled service days</th></tr></thead>
                <tbody>
                  {rows.map(r => (
                    <tr key={r.route}>
                      <td><RouteLink route={r.route} info={routeInfo.get(r.route)} /></td>
                      <td className="text-sm">{routeInfo.get(r.route)?.route_long_name ?? <span className="text-xs text-ink-2">no name in the timetables</span>}</td>
                      <td className="text-sm">{r.reason ?? 'no reason given'}</td>
                      <td className="n num">{fmt(r.observed_days)}</td>
                      <td className="n"><Value value={r.scheduled_service_days} reason="not scheduled" /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>}
    </Panel>
  )
}

// ---- route overlap review ------------------------------------------------------------------------------------------
function OverlapView({ s, lowestFirst, routeInfo }: {
  s: ApiState<OverlapResponse> & { retry: () => void }; lowestFirst: boolean; routeInfo: Map<string, RouteRow>
}) {
  const [all, setAll] = useState(false)
  return (
    <AsyncBlock state={s} retry={s.retry} label="Loading the route overlap review" isEmpty={o => o.rows.length === 0}
                emptyMessage={o => `No route pairs share stops in timetable ${o.geometry_version}.`}>
      {o => {
        const rows = [...o.rows].sort((a, b) => (lowestFirst ? b.rank - a.rank : a.rank - b.rank)
          || compareRoutes(a.route_a, b.route_a) || compareRoutes(a.route_b, b.route_b))
        const visible = all ? rows : rows.slice(0, PAGE_ROWS)
        const sharing = o.rows.filter(r => r.shared_stop_count > 0).length
        const mostly = o.rows.filter(r => r.smaller_route_stop_overlap > 0.5).length
        return (
          <div className="space-y-6">
            <div className="space-y-3">
              {o.metric.caveat && <ApiLabel warn text={o.metric.caveat} />}
              <p className="border-l-[3px] border-brand pl-4 text-md leading-8">
                In timetable {o.geometry_version}, <span className="font-semibold num">{fmt(sharing)}</span> route pairs share at least one
                stop, and in <span className="font-semibold num">{fmt(mostly)}</span> of them more than half of the smaller route's stops are shared.
              </p>
            </div>
            <Panel title={`Route pairs: ${fmt(o.counts.pairs)}`}
                   purpose={`${o.metric.meaning}. Ordered by Jaccard stop overlap, ${lowestFirst ? 'lowest' : 'highest'} first.`}
                   howToRead="Jaccard is the shared stops divided by all stops on either route (1 = the same stops). The smaller-route share is how much of the shorter route is shared; the last two columns are the share of each route's stops that no other route serves.">
              <div className="-mx-4 overflow-x-auto">
                <table className="data-table">
                  <thead><tr>
                    <th className="n">Rank</th><th>Route pair</th><th className="n">Shared stops</th><th className="n">Jaccard</th>
                    <th className="n">Share of smaller route</th><th className="n">First route only</th><th className="n">Second route only</th>
                  </tr></thead>
                  <tbody>
                    {visible.map(r => (
                      <tr key={`${r.route_a}-${r.route_b}`}>
                        <td className="n num">#{r.rank}</td>
                        <td className="whitespace-nowrap"><RouteLink route={r.route_a} info={routeInfo.get(r.route_a)} />{' and '}
                          <RouteLink route={r.route_b} info={routeInfo.get(r.route_b)} /></td>
                        <td className="n num">{fmt(r.shared_stop_count)} <span className="text-xs text-ink-2">of {fmt(r.route_a_stop_count)} / {fmt(r.route_b_stop_count)}</span></td>
                        <td className="n num">{fmt(r.jaccard_stop_overlap, 3)}</td>
                        <td className="n num">{fmtPct(r.smaller_route_stop_overlap)} %</td>
                        <td className="n num">{fmtPct(r.route_a_exclusive_fraction)} %</td>
                        <td className="n num">{fmtPct(r.route_b_exclusive_fraction)} %</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {rows.length > PAGE_ROWS && (
                <button type="button" className="btn-secondary mt-3" onClick={() => setAll(a => !a)}>
                  {all ? `Show the first ${PAGE_ROWS}` : `Show all ${rows.length} pairs`}
                </button>
              )}
            </Panel>
          </div>
        )
      }}
    </AsyncBlock>
  )
}
