// One route (spec 9.16.2 "Route detail"): the route's three ranks with stability, its recorded rides per day (the
// analysis window, or the full history), its weekly rhythm, exact map lines, its group and its shared-stop routes.
// Every number and sentence is computed from API responses at render time (CLAUDE.md, UI design principles).
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api, buildUrl } from '../api/client'
import { useRequestScope } from '../api/cutoff'
import type { DayType, HistoryDay, HistoryResponse, PeriodName, RankingMetric, RankingResponse, RouteRow } from '../api/types'
import { useApi, type ApiState } from '../api/useApi'
import { AsyncBlock } from '../components/AsyncBlock'
import { ForecastPanel } from '../components/ForecastPanel'
import { MapCaption } from '../components/MapCaption'
import { Panel, SectionHead } from '../components/Panel'
import { Num, type ProvenanceInfo } from '../components/Provenance'
import { RankTrio } from '../components/RankTrio'
import { RhythmGrid } from '../components/RhythmGrid'
import { RidesChart } from '../components/RidesChart'
import { RouteMap } from '../components/RouteMap'
import { RouteSign } from '../components/RouteSign'
import { Choice, Sentence } from '../components/Sentence'
import { StopShareStrip } from '../components/StopShareStrip'
import { Empty } from '../components/States'
import { Value } from '../components/Value'
import { METRIC_ORDER } from '../lib/closerLook'
import { fmtDate, fmtRange } from '../lib/dates'
import { fmt, fmtPct } from '../lib/format'
import { rankingProvenance } from '../lib/provenance'
import { daytypeMeans, recordCoverage, shareOfWeekday } from '../lib/routeProfile'
import { compareRoutes, sortByRoute } from '../lib/routeSort'

const DAYTYPE_TEXT: Record<DayType, string> = { W: 'weekdays', A: 'Saturdays', U: 'Sundays and holidays' }
const PARTNERS = 8

function useRanking(metric: RankingMetric, period: PeriodName, daytype: DayType) {
  return useApi(o => api.rankings({ metric, period, daytype }, o), `rank:${metric}:${period}:${daytype}:ref:all`)
}

export function OneRoutePage() {
  const { route } = useParams()
  const navigate = useNavigate()
  const routes = useApi(o => api.routes({}, o), 'routes')
  const list = routes.status === 'ok' ? sortByRoute(routes.data.routes, r => r.route) : []
  const info = list.find(r => r.route === route)

  return (
    <div>
      <div className="eyebrow">One route</div>
      <h1 className="text-xl font-semibold tracking-tight">How is one route doing?</h1>
      <div className="mt-4">
        <Sentence>
          Showing route{' '}
          {routes.status === 'ok'
            ? <Choice label="Route" value={route ?? ''} onChange={r => navigate(`/route/${encodeURIComponent(r)}`)}
                      options={[...(route ? [] : [{ value: '', text: 'choose a route' }]),
                                ...list.map(r => ({ value: r.route, text: r.route_long_name ? `${r.route} ${r.route_long_name}` : r.route }))]} />
            : <span aria-busy>…</span>}.
        </Sentence>
      </div>
      {!route
        ? <RoutePicker s={routes} />
        : routes.status === 'ok' && !info
          ? <Empty message={`Route ${route} is not in this data version.`} />
          : <RouteBody route={route} info={info} />}
    </div>
  )
}

function RoutePicker({ s }: { s: ApiState<{ routes: RouteRow[] }> & { retry: () => void } }) {
  return (
    <AsyncBlock state={s} retry={s.retry} label="Loading routes" isEmpty={d => d.routes.length === 0}>
      {d => (
        <Panel title={`Choose one of ${fmt(d.routes.length)} routes`} purpose="Each sign opens that route.">
          <ul className="flex flex-wrap gap-2">
            {sortByRoute(d.routes, r => r.route).map(r => (
              <li key={r.route}><Link to={`/route/${encodeURIComponent(r.route)}`} className="no-underline" aria-label={`Open route ${r.route}`}>
                <RouteSign route={r.route} groupId={r.group_id} groupName={r.group_name} /></Link></li>
            ))}
          </ul>
        </Panel>
      )}
    </AsyncBlock>
  )
}

function RouteBody({ route, info }: { route: string; info: RouteRow | undefined }) {
  const scope = useRequestScope()
  const [daytype, setDaytype] = useState<DayType>('W')
  const [full, setFull] = useState(false)
  const coverage = useApi(o => api.coverage(o), 'coverage')
  const first = coverage.status === 'ok' ? coverage.data.observations.first_date : null
  const histStart = full && first ? first : undefined
  const history = useApi(o => api.history(route, { start: histStart }, o), `history:${route}:${histStart ?? 'window'}`)
  const windowHistory = useApi(o => api.history(route, {}, o), `history:${route}:window`)
  const fullRank = { observed_daily_demand: useRanking('observed_daily_demand', 'full_matched_window', daytype),
                     rides_per_scheduled_trip: useRanking('rides_per_scheduled_trip', 'full_matched_window', daytype),
                     rides_per_scheduled_hour: useRanking('rides_per_scheduled_hour', 'full_matched_window', daytype) }
  const devRank = { observed_daily_demand: useRanking('observed_daily_demand', 'development', daytype),
                    rides_per_scheduled_trip: useRanking('rides_per_scheduled_trip', 'development', daytype),
                    rides_per_scheduled_hour: useRanking('rides_per_scheduled_hour', 'development', daytype) }
  const lines = useApi(o => api.mapLines({ routes: [route], simplify_m: 0 }, o), `lines:${route}:exact`)
  const overlap = useApi(o => api.overlap({}, o), 'overlap')
  const groups = useApi(o => api.groups(o), 'groups')
  const routes = useApi(o => api.routes({}, o), 'routes')
  const groupOf = routes.status === 'ok' ? new Map(routes.data.routes.map(r => [r.route, r.group_id])) : new Map<string, number | null>()
  const ranksOk = [...METRIC_ORDER.map(m => fullRank[m]), ...METRIC_ORDER.map(m => devRank[m])]
  const allRanks = ranksOk.every(s => s.status === 'ok')
  const rankData = (by: typeof fullRank, m: RankingMetric) => (by[m] as { data: RankingResponse }).data
  const request = (m: RankingMetric) => buildUrl('/api/rankings', { metric: m, period: 'full_matched_window', daytype }, scope)

  return (
    <div>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <RouteSign route={route} groupId={info?.group_id} groupName={info?.group_name} size="lg" />
        <div>
          <div className="text-lg font-semibold">{info?.route_long_name ?? <span className="text-sm font-normal text-ink-2">no name in the timetables</span>}</div>
          <div className="text-sm text-ink-2">
            {info?.group_id != null
              ? <>Group {info.group_id} · {info.group_name} · <Link to="/alike">see similar routes</Link></>
              : <>Ungrouped{info?.ungrouped_reason ? ` – ${info.ungrouped_reason}` : groups.status === 'ok' && !groups.data.available ? ` – ${groups.data.reason}` : ''}</>}
          </div>
        </div>
        <Link to={`/scenarios?routes=${encodeURIComponent(route)}`} className="btn-secondary ml-auto no-underline"
              aria-label={`Create a scenario for route ${route}`}>Create scenario</Link>
      </div>

      {windowHistory.status === 'ok' && allRanks && (
        <RouteInsight route={route} h={windowHistory.data} daytype={daytype}
                      ranks={Object.fromEntries(METRIC_ORDER.map(m => [m, rankData(fullRank, m)])) as Record<RankingMetric, RankingResponse>} />
      )}

      <div className="mt-6"><ForecastPanel route={route} /></div>

      <SectionHead title="Ranks on three measures" note="Rank 1 is the highest value among all routes on the chosen day type, in the full matched window." />
      <p className="mb-3 text-sm">
        Day type: <Choice label="Day type for ranks" value={daytype} onChange={setDaytype}
                          options={(Object.keys(DAYTYPE_TEXT) as DayType[]).map(d => ({ value: d, text: DAYTYPE_TEXT[d] }))} />
      </p>
      {allRanks
        ? <>
            <RankTrio cells={METRIC_ORDER.map(m => {
              const d = rankData(fullRank, m), row = d.rows.find(r => r.route === route)
              const dev = rankData(devRank, m).rows.find(r => r.route === route)
              return { metricLabel: d.metric.label, value: rankingProvenance(d, row, route, request(m)), rank: row?.rank ?? null,
                       of: d.counts.ranked, reason: row ? row.reason : `no matched ${DAYTYPE_TEXT[daytype]} in the period`,
                       dev: { rank: dev?.rank ?? null, reason: dev ? dev.reason : `no matched ${DAYTYPE_TEXT[daytype]} in the development period` } }
            })} />
            <p className="mt-2 text-xs text-ink-2">
              <span className="font-semibold text-ink">How to read this: </span>each value opens how it was made. Stability compares the
              route's rank in the development period with the full matched window. {rankData(fullRank, 'rides_per_scheduled_hour').metric.caveat}
            </p>
          </>
        : <AsyncBlock state={ranksOk.find(s => s.status !== 'ok')!} retry={() => ranksOk.forEach(s => s.retry())} label="Loading ranks">{() => null}</AsyncBlock>}

      <SectionHead title="Recorded rides per day" />
      <Panel title={`Route ${route}, recorded rides`}
             purpose={history.status === 'ok' ? fmtRange(history.data.range.start, history.data.range.end) : undefined}
             aside={first && <button type="button" className="btn-secondary" onClick={() => setFull(f => !f)}>
               {full ? 'Show the analysis window only' : `Show full history since ${first.slice(0, 4)}`}</button>}
             howToRead="Each point is one service day. A break is a day without a ridership record: hover it for the reason. Shaded days come before dated schedules exist.">
        <AsyncBlock state={history} retry={history.retry} label="Loading the route's history" isEmpty={h => h.count === 0}>
          {h => (
            <div className="space-y-3">
              <RidesChart<HistoryDay> days={h.days} rangeStart={h.range.start} scheduleStart={h.range.schedule_window.start} unit={h.units.rides}
                                      extra={d => <>
                                        {d.scheduled_trips != null && <div className="text-xs text-ink-2">Scheduled trips: {fmt(d.scheduled_trips)}</div>}
                                        {d.rides != null && d.reason && <div className="text-xs text-ink-2">{d.reason}</div>}
                                      </>} />
              <StatusLine h={h} />
            </div>
          )}
        </AsyncBlock>
      </Panel>

      <div className="mt-4 grid items-start gap-4 xl:grid-cols-[minmax(0,6fr)_minmax(0,5fr)]">
        <Panel title="Weekly rhythm" purpose={windowHistory.status === 'ok' ? `Analysis window, ${fmtRange(windowHistory.data.range.start, windowHistory.data.range.end)}` : undefined}
               howToRead="Weeks run left to right, Monday to Sunday top to bottom; a darker cell is more recorded rides. An outlined empty cell is a day without a record (hover for the reason).">
          <AsyncBlock state={windowHistory} retry={windowHistory.retry} label="Loading the weekly rhythm" isEmpty={h => h.count === 0}>
            {h => <RhythmGrid days={h.days.map(d => ({ date: d.service_date, rides: d.rides, reason: d.reason }))} unit={h.units.rides} />}
          </AsyncBlock>
        </Panel>
        <Panel title="Map" purpose="The route's most common path in each direction, exact (not simplified).">
          <AsyncBlock state={lines} retry={lines.retry} label="Loading the map" isEmpty={m => m.lines.length === 0}
                      emptyMessage={m => m.routes_without_lines.find(x => x.route === route)?.reason ?? `No lines for route ${route} in timetable ${m.geometry_version}.`}>
            {m => (
              <div className="-mx-4 -my-3">
                <RouteMap lines={m.lines} height={340} weight={3} />
                <MapCaption geometryVersion={m.geometry_version} appliedStart={m.applied.start} appliedEnd={m.applied.end}
                            pathLabel={m.label} displayNote={m.display.note} />
              </div>
            )}
          </AsyncBlock>
        </Panel>
      </div>

      <SectionHead title="Routes that share its stops" />
      <AsyncBlock state={overlap} retry={overlap.retry} label="Loading shared stops">
        {o => {
          const pairs = o.rows.filter(r => r.route_a === route || r.route_b === route)
            .sort((a, b) => b.jaccard_stop_overlap - a.jaccard_stop_overlap || a.rank - b.rank || compareRoutes(a.route_a, b.route_a) || compareRoutes(a.route_b, b.route_b))
          if (!pairs.length) return <Empty message={`Route ${route} shares no stop with another route in timetable ${o.geometry_version}.`} />
          const top = pairs[0]!
          const other = (p: typeof top) => (p.route_a === route ? p.route_b : p.route_a)
          return (
            <Panel title={`${fmt(pairs.length)} routes share at least one stop with route ${route}`}
                   purpose={`Timetable ${o.geometry_version}. The closest ${Math.min(PARTNERS, pairs.length)} by Jaccard stop overlap.`}
                   howToRead="Jaccard is the shared stops divided by all stops on either route (1 = the same stops). The share of the smaller route is how much of the shorter route is shared.">
              <div className="space-y-4">
                <StopShareStrip a={{ route: top.route_a, groupId: groupOf.get(top.route_a) ?? null, stops: top.route_a_stop_count }}
                                b={{ route: top.route_b, groupId: groupOf.get(top.route_b) ?? null, stops: top.route_b_stop_count }}
                                shared={top.shared_stop_count} jaccard={top.jaccard_stop_overlap}
                                smallerOverlap={top.smaller_route_stop_overlap} interpretation={top.interpretation} />
                <div className="-mx-4 overflow-x-auto">
                  <table className="data-table">
                    <thead><tr><th>Route</th><th className="n">Shared stops</th><th className="n">Jaccard</th><th className="n">Share of smaller route</th><th className="n">Review rank</th></tr></thead>
                    <tbody>
                      {pairs.slice(0, PARTNERS).map(p => (
                        <tr key={other(p)}>
                          <td><Link to={`/route/${encodeURIComponent(other(p))}`} className="no-underline" aria-label={`Open route ${other(p)}`}>
                            <RouteSign route={other(p)} groupId={groupOf.get(other(p))} size="sm" /></Link></td>
                          <td className="n num">{fmt(p.shared_stop_count)}</td>
                          <td className="n num">{fmt(p.jaccard_stop_overlap, 3)}</td>
                          <td className="n num">{fmtPct(p.smaller_route_stop_overlap)} %</td>
                          <td className="n num">#{p.rank}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </Panel>
          )
        }}
      </AsyncBlock>
    </div>
  )
}

/** The opening sentence: three ranks, weekend level and record coverage, all counted from the responses. */
function RouteInsight({ route, h, daytype, ranks }: {
  route: string; h: HistoryResponse; daytype: DayType; ranks: Record<RankingMetric, RankingResponse>
}) {
  const means = daytypeMeans(h.days)
  const cov = recordCoverage(h.summary)
  const share = (d: 'A' | 'U'): ProvenanceInfo => ({
    title: `Route ${route} · average ${d === 'A' ? 'Saturday' : 'Sunday/holiday'} as a share of an average weekday`,
    value: (() => { const s = shareOfWeekday(means, d); return s == null ? null : s * 100 })(), digits: 0, unit: '% of a weekday',
    formula: `average ${d === 'A' ? 'Saturday' : 'Sunday/holiday'} recorded rides ÷ average weekday recorded rides × 100 (days with a record only)`,
    numerator: { label: `per ${d === 'A' ? 'Saturday' : 'Sunday/holiday'}, ${fmt(means[d].days)} days`, value: means[d].mean },
    denominator: { label: `per weekday, ${fmt(means.W.days)} days`, value: means.W.mean },
    period: { name: 'Analysis window', start: h.range.start, end: h.range.end },
    missing: shareOfWeekday(means, d) == null ? { reason: means[d].days === 0 ? `no ${d === 'A' ? 'Saturday' : 'Sunday/holiday'} with a ridership record` : 'no weekday with a ridership record' } : undefined,
    dataVersion: h.data_version, request: buildUrl(`/api/routes/${encodeURIComponent(route)}/history`, { mode: 'historical' }),
  })
  const rankText = METRIC_ORDER.map(m => {
    const row = ranks[m].rows.find(r => r.route === route)
    return { label: ranks[m].metric.label.toLowerCase(), rank: row?.rank ?? null, of: ranks[m].counts.ranked, reason: row?.reason ?? 'not in this ranking' }
  })
  return (
    <div className="mt-5 space-y-2 border-l-[3px] border-brand pl-4 text-md leading-8">
      <p>
        On {DAYTYPE_TEXT[daytype]}, route {route}{' '}
        {rankText.every(r => r.rank == null)
          ? <>is not ranked on any measure ({rankText[0]!.reason}).</>
          : <>ranks {rankText.map((r, i) => <span key={r.label}>{i > 0 && (i === rankText.length - 1 ? ' and ' : ', ')}
              {r.rank == null ? <span className="text-ink-2">unranked ({r.reason})</span> : <span className="font-semibold num">#{r.rank}</span>} by {r.label}</span>)}
            {' '}(of {fmt(rankText[0]!.of)} ranked routes).</>}
      </p>
      <p>
        An average Saturday carries <Num p={share('A')} className="font-semibold" /> and an average Sunday or holiday{' '}
        <Num p={share('U')} className="font-semibold" />. <span className="num font-semibold">{fmt(cov.recorded)}</span> of its{' '}
        {fmt(cov.scheduled)} scheduled days in the analysis window have a ridership record.
      </p>
    </div>
  )
}

/** Counts of days by status, in plain words (the status names never appear on screen). */
const STATUS_WORDS: Record<string, string> = {
  matched: 'recorded rides and scheduled service',
  ridership_without_schedule: 'recorded rides, no scheduled service',
  schedule_without_ridership: 'scheduled service, no ridership record',
  no_service_no_record: 'no service and no record',
  recorded_rides_only: 'recorded rides before dated schedules',
  no_record: 'no record before dated schedules',
}
function StatusLine({ h }: { h: HistoryResponse }) {
  const parts = Object.entries(h.summary).filter(([, n]) => (n ?? 0) > 0)
  return (
    <p className="text-xs text-ink-2">
      {fmt(h.count)} days from {fmtDate(h.range.start)}:{' '}
      {parts.map(([k, n], i) => <span key={k}>{i > 0 && ' · '}<Value value={n ?? null} /> {STATUS_WORDS[k] ?? k.replaceAll('_', ' ')}</span>)}.
    </p>
  )
}
