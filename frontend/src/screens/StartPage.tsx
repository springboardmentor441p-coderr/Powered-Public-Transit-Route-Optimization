// Start (spec 9.16.2 "Network overview"): the planner questions with live one-line answers, the network demand
// trend with its day-type sentence, the dated map and a route summary table. Every number and sentence below is
// computed from API responses at render time; nothing is hard-coded (CLAUDE.md, UI design principles).
import { useMemo, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { api, buildUrl } from '../api/client'
import { useCutoff } from '../api/cutoff'
import type { GroupsResponse, RankingRow, RouteRow, ServiceStatus, TrendResponse } from '../api/types'
import { useApi, type ApiState } from '../api/useApi'
import { AsyncBlock } from '../components/AsyncBlock'
import { EndsPreview } from '../components/EndsPreview'
import { MapCaption } from '../components/MapCaption'
import { ApiLabel, Panel, SectionHead } from '../components/Panel'
import { Num, type ProvenanceInfo } from '../components/Provenance'
import { QuestionIndex } from '../components/QuestionIndex'
import { GroupLegend, RouteMap } from '../components/RouteMap'
import { RouteSign } from '../components/RouteSign'
import { Choice } from '../components/Sentence'
import { TrendChart } from '../components/TrendChart'
import { Value } from '../components/Value'
import { fmtDate, fmtRange } from '../lib/dates'
import { fmt, fmtPct } from '../lib/format'
import { daytypeLevels, importChecks, type DaytypeLevel } from '../lib/insights'
import { compareRoutes } from '../lib/routeSort'

const TABLE_ROWS = 12

/** A one-line preview that follows its request: "…" while loading, a quiet reason if it failed. */
function Live<T>({ s, children }: { s: ApiState<T>; children: (d: T) => ReactNode }) {
  if (s.status === 'loading') return <span aria-busy>…</span>
  if (s.status === 'error') return <span className="text-xs">unavailable – {s.message}</span>
  return <>{children(s.data)}</>
}

const groupNamesOf = (g: GroupsResponse | null): Record<number, string> =>
  g && g.available ? Object.fromEntries(g.groups.map(x => [x.group_id, x.name])) : {}

// ---- the trend sentence ------------------------------------------------------------------------------------------
function TrendSentence({ t, request }: { t: TrendResponse; request: string }) {
  const levels = daytypeLevels(t.summary)
  const period = { name: 'Shown range', start: t.range.start, end: t.range.end }
  const mean = (l: DaytypeLevel): ProvenanceInfo => ({
    title: `Network · average ${l.label} recorded rides`, value: l.mean, digits: 0, unit: t.units.rides,
    formula: `network recorded rides summed over the ${l.label} dates with a record ÷ those dates (dates without any record are not counted)`,
    numerator: { label: 'recorded rides', value: l.total }, denominator: { label: `${l.label} dates`, value: l.days },
    period, daytype: l.label, missing: l.mean == null ? { reason: l.reason ?? 'unavailable' } : undefined,
    dataVersion: t.data_version, request,
  })
  const share = (l: DaytypeLevel, w: DaytypeLevel): ProvenanceInfo => ({
    title: `Network · average ${l.label} as a share of an average weekday`,
    value: l.shareOfWeekday == null ? null : l.shareOfWeekday * 100, digits: 0, unit: '% of a weekday',
    formula: `average ${l.label} recorded rides ÷ average weekday recorded rides × 100`,
    numerator: { label: `per ${l.label}`, value: l.mean }, denominator: { label: 'per weekday', value: w.mean },
    period, missing: l.shareOfWeekday == null ? { reason: l.reason ?? 'unavailable' } : undefined,
    dataVersion: t.data_version, request,
  })
  const [w, a, u] = (['W', 'A', 'U'] as const).map(d => levels.find(l => l.daytype === d)!)
  return (
    <p className="border-l-[3px] border-brand pl-4 text-md leading-8">
      From {fmtRange(t.range.start, t.range.end)}, the network carried <Num p={mean(w!)} className="font-semibold" /> on
      an average weekday ({fmt(w!.days)} weekdays). An average Saturday carried <Num p={mean(a!)} />, which
      is <Num p={share(a!, w!)} className="font-semibold" />, and an average Sunday or holiday <Num p={mean(u!)} />, which
      is <Num p={share(u!, w!)} className="font-semibold" />.
    </p>
  )
}

// ---- route summary table ---------------------------------------------------------------------------------------------
// Short marks so the column fits on one line; the full words are in the tooltip and the "How to read this" line.
const WEEKEND: Record<ServiceStatus, { mark: string; words: string }> = {
  available: { mark: '✓', words: 'service with enough observed days' },
  no_scheduled_service: { mark: '–', words: 'no scheduled service' },
  insufficient_observations: { mark: '?', words: 'too few observed days' },
}
const weekend = (r: RouteRow | undefined) => {
  if (r?.saturday_service_status == null) return <span className="whitespace-nowrap text-xs text-ink-2">not profiled</span>
  const sat = WEEKEND[r.saturday_service_status], sun = WEEKEND[r.sunday_holiday_service_status ?? 'insufficient_observations']
  return (
    <span className="whitespace-nowrap text-xs" title={`Saturday: ${sat.words}. Sunday/holiday: ${sun.words}.`}>
      Sat {sat.mark} · Sun/hol {sun.mark}
    </span>
  )
}
const WEEKEND_KEY = Object.values(WEEKEND).map(w => `${w.mark} ${w.words}`).join(', ')

type SortKey = 'demand' | 'hour'
function RouteTable({ demand, hour, routes }: { demand: RankingRow[]; hour: RankingRow[]; routes: RouteRow[] }) {
  const [sort, setSort] = useState<SortKey>('demand')
  const [all, setAll] = useState(false)
  const byRoute = useMemo(() => new Map(routes.map(r => [r.route, r])), [routes])
  const hourOf = useMemo(() => new Map(hour.map(r => [r.route, r])), [hour])
  const rows = useMemo(() => {
    const joined = demand.map(d => ({ d, h: hourOf.get(d.route), r: byRoute.get(d.route) }))
    const rank = (x: (typeof joined)[number]) => (sort === 'demand' ? x.d.rank : x.h?.rank) ?? Infinity
    return joined.sort((x, y) => rank(x) - rank(y) || compareRoutes(x.d.route, y.d.route))
  }, [demand, hourOf, byRoute, sort])
  const shown = all ? rows : rows.slice(0, TABLE_ROWS)
  return (
    <>
      <p className="mb-2 text-sm">
        Sorted by <Choice label="Sort routes by" value={sort} onChange={setSort}
                          options={[{ value: 'demand', text: 'weekday rides/day' }, { value: 'hour', text: 'rides per scheduled hour' }]} />,
        highest first.
      </p>
      <div className="-mx-4 overflow-x-auto">
        <table className="data-table">
          <thead><tr>
            <th>Route</th><th>Name</th><th className="n">Weekday rides/day</th><th className="n">Rides per scheduled hour</th>
            <th className="n">Matched weekdays</th><th>Weekend service</th>
          </tr></thead>
          <tbody>
            {shown.map(({ d, h, r }) => (
              <tr key={d.route}>
                <td><Link to={`/route/${encodeURIComponent(d.route)}`} className="no-underline" aria-label={`Open route ${d.route}`}>
                  <RouteSign route={d.route} groupId={r?.group_id} groupName={r?.group_name} size="sm" /></Link></td>
                <td className="text-sm">{r?.route_long_name ?? <span className="text-xs text-ink-2">no name in the timetables</span>}</td>
                <td className="n"><Value value={d.value} reason={d.reason} />{d.rank != null && <span className="ml-1.5 text-xs text-ink-2">#{d.rank}</span>}</td>
                <td className="n"><Value value={h?.value} digits={1} reason={h?.reason ?? 'not in this ranking'} />{h?.rank != null && <span className="ml-1.5 text-xs text-ink-2">#{h.rank}</span>}</td>
                <td className="n num">{fmt(d.observed_days)}</td>
                <td>{weekend(r)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {rows.length > TABLE_ROWS && (
        <button type="button" className="btn-secondary mt-3" onClick={() => setAll(a => !a)}>
          {all ? `Show the first ${TABLE_ROWS}` : `Show all ${rows.length} routes`}
        </button>
      )}
    </>
  )
}

// ---- the page ------------------------------------------------------------------------------------------------------
export function StartPage() {
  const cutoff = useCutoff()
  const [full, setFull] = useState(false)
  const coverage = useApi(o => api.coverage(o), 'coverage')
  const routes = useApi(o => api.routes({}, o), 'routes')
  const hour = useApi(o => api.rankings({ metric: 'rides_per_scheduled_hour', daytype: 'W' }, o), 'rank:hour:W')
  const demand = useApi(o => api.rankings({ metric: 'observed_daily_demand', daytype: 'W' }, o), 'rank:demand:W')
  const overlap = useApi(o => api.overlap({}, o), 'overlap')
  const groups = useApi(o => api.groups(o), 'groups')
  const map = useApi(o => api.mapLines({}, o), 'map')
  const first = coverage.status === 'ok' ? coverage.data.observations.first_date : null
  const trendStart = full && first ? first : undefined
  const trend = useApi(o => api.trend({ start: trendStart }, o), `trend:${trendStart ?? 'window'}`)
  const trendRequest = buildUrl('/api/network/trend', { start: trendStart }, { cutoff })

  const groupOf = routes.status === 'ok' ? new Map(routes.data.routes.map(r => [r.route, r.group_id])) : new Map<string, number | null>()
  const gData = groups.status === 'ok' ? groups.data : null

  return (
    <div>
      <div className="eyebrow">Start</div>
      <h1 className="text-xl font-semibold tracking-tight">
        CTA bus routes, <Live s={coverage}>{c => fmtRange(c.analysis_window.start, c.analysis_window.end)}</Live>
      </h1>
      <p className="mt-1 max-w-[80ch] text-base text-ink-2">
        <Live s={coverage}>{c => <>{fmt(c.matching.matched_routes)} routes with recorded rides and scheduled service on the
          same dates ({fmt(c.matching.matched_dates)} dates). Recorded rides go back to {fmtDate(c.observations.first_date)};
          dated schedules start on {fmtDate(c.analysis_window.start)}.</>}</Live>
      </p>

      <SectionHead title="Questions" note="Each answer below is read live from the API. Open a question for the full view." />
      <div className="bg-panel px-5 pb-1 pt-2">
        <QuestionIndex rows={[
          { question: 'Which routes deserve a closer look?', to: '/closer-look',
            preview: <Live s={hour}>{h => <EndsPreview lead={`Weekdays, ${h.metric.label.toLowerCase()}`}
                                                          rows={h.rows.map(r => ({ ...r, groupId: groupOf.get(r.route) }))} />}</Live> },
          { question: 'How is one route doing?', to: '/route',
            preview: <Live s={demand}>{d => <>Pick any of the {fmt(d.counts.routes)} weekday routes to see its ranks, weekly rhythm, group and shared stops.</>}</Live> },
          { question: 'Which routes are alike?', to: '/alike',
            preview: <Live s={groups}>{g => g.available
              ? <>{g.groups.length} groups of {g.groups.map(x => x.size).join(' and ')} routes, {g.ungrouped.length} ungrouped · fitted
                  on {fmtRange(g.profile_period.start, g.profile_period.end)}</>
              : <span className="text-xs">unavailable – {g.reason}</span>}</Live> },
          { question: 'Which routes share stops?', to: '/shared-stops',
            preview: <Live s={overlap}>{o => {
              const top = o.rows.filter(r => r.rank === 1)
              if (!top.length) return <span className="text-xs">unavailable – no route pairs in {o.geometry_version}</span>
              const p = top[0]!
              return <>Most shared{top.length > 1 && ` (${top.length} pairs tied)`}:{' '}
                <RouteSign route={p.route_a} groupId={groupOf.get(p.route_a)} size="sm" />{' and '}
                <RouteSign route={p.route_b} groupId={groupOf.get(p.route_b)} size="sm" />
                {`, ${fmt(p.shared_stop_count)} shared stops, ${fmtPct(p.smaller_route_stop_overlap)} % of the smaller route's stops · timetable ${o.geometry_version}`}</>
            }}</Live> },
          { question: 'How do these routes differ?', to: '/compare',
            preview: <>Put two or more routes side by side for the same period and day type.</> },
          { question: 'Can I trust these numbers?', to: '/data', quiet: true,
            preview: <Live s={coverage}>{c => {
              const k = importChecks(c.quality)
              return <><Value value={c.matching.schedule_conditioned_coverage_pct} digits={3} /> % of scheduled route-days
                have a ride record · {k.held} of {k.total} import checks hold</>
            }}</Live> },
        ]} />
      </div>

      <SectionHead title="The network over time" />
      <Panel title="Recorded rides, whole network" purpose="Daily total over the routes that reported that day."
             aside={first && <button type="button" className="btn-secondary" onClick={() => setFull(f => !f)}>
               {full ? 'Show the analysis window only' : `Show full history since ${first.slice(0, 4)}`}</button>}
             howToRead="Each point is one service day; the weekly zigzag is weekdays against weekends. A break is a day with no record (hover for the reason). Shaded days come before dated schedules exist. Click an underlined number for how it was made.">
        <AsyncBlock state={trend} retry={trend.retry} label="Loading the network trend" isEmpty={t => t.count === 0}>
          {t => (
            <div className="space-y-4">
              <TrendSentence t={t} request={trendRequest} />
              <TrendChart t={t} />
              <p className="text-xs text-ink-2">{t.total_note}.</p>
            </div>
          )}
        </AsyncBlock>
      </Panel>

      <SectionHead title="Routes on the map, and in numbers" />
      <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
        <Panel title="Dated map" purpose="Each route's most common path, coloured by its group.">
          <AsyncBlock state={map} retry={map.retry} label="Loading the map" isEmpty={m => m.lines.length === 0}
                      emptyMessage={m => `No route lines in timetable ${m.geometry_version}.`}>
            {m => (
              <div className="-mx-4 -my-3">
                <RouteMap lines={m.lines} groupNames={groupNamesOf(gData)} height={460} />
                <div className="space-y-2 px-4 py-2">
                  {gData?.available ? <GroupLegend groups={gData.groups} /> : m.groups_note && <ApiLabel warn text={m.groups_note} />}
                </div>
                <MapCaption geometryVersion={m.geometry_version} appliedStart={m.applied.start} appliedEnd={m.applied.end}
                            pathLabel={m.label} displayNote={m.display.note} />
              </div>
            )}
          </AsyncBlock>
        </Panel>
        <Panel title="Route summary" purpose={demand.status === 'ok' ? `Weekdays, ${demand.data.period.label.toLowerCase()}: ${fmtRange(demand.data.period.start, demand.data.period.end)}.` : undefined}
               howToRead={hour.status === 'ok' ? `#n is the route's rank among weekday routes (ties share a rank). Weekend service: ${WEEKEND_KEY}. Click a route sign to open it. ${hour.data.metric.caveat}` : undefined}>
          {demand.status === 'ok' && hour.status === 'ok' && routes.status === 'ok'
            ? <RouteTable demand={demand.data.rows} hour={hour.data.rows} routes={routes.data.routes} />
            : <AsyncBlock state={demand.status !== 'ok' ? demand : hour.status !== 'ok' ? hour : routes}
                          retry={() => { demand.retry(); hour.retry(); routes.retry() }} label="Loading routes">{() => null}</AsyncBlock>}
        </Panel>
      </div>
    </div>
  )
}
