// Compare (spec 9.16.2 "Compare routes"): 2 to 8 routes over one period and day type, with the "same days only"
// switch, the common-days warning, indicators with network ranks, service, coverage, groups, a map and the shared
// stops among them. Every number and sentence is computed from /api/routes/compare (CLAUDE.md, UI principles).
import type { ReactNode } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api, buildUrl } from '../api/client'
import { useCutoff } from '../api/cutoff'
import type { CompareResponse, CompareRoute, DayType, PeriodName, RankingMetric } from '../api/types'
import { useApi } from '../api/useApi'
import { AsyncBlock } from '../components/AsyncBlock'
import { MapCaption } from '../components/MapCaption'
import { ApiLabel, Panel } from '../components/Panel'
import { Num, type ProvenanceInfo } from '../components/Provenance'
import { RouteMap } from '../components/RouteMap'
import { RouteSign } from '../components/RouteSign'
import { Choice, Sentence } from '../components/Sentence'
import { Empty } from '../components/States'
import { Value } from '../components/Value'
import { DIGITS, METRIC_ORDER } from '../lib/closerLook'
import { archiveRange, leaders, MAX_ROUTES, MIN_ROUTES, parseRoutes } from '../lib/compare'
import { fmtRange } from '../lib/dates'
import { fmt, fmtPct } from '../lib/format'
import { sortByRoute } from '../lib/routeSort'

const DAYTYPE_TEXT: Record<DayType, string> = { W: 'weekdays', A: 'Saturdays', U: 'Sundays and holidays' }
const PERIOD_TEXT: Record<PeriodName, string> = { full_matched_window: 'the full matched window', development: 'the development period' }

export function ComparePage() {
  const [params, setParams] = useSearchParams()
  const chosen = parseRoutes(params.get('routes'))
  const daytype = (['W', 'A', 'U'].includes(params.get('daytype') ?? '') ? params.get('daytype') : 'W') as DayType
  const period = (params.get('period') === 'development' ? 'development' : 'full_matched_window') as PeriodName
  const sameDays = params.get('same_days') === 'true'
  const set = (k: string, v: string | null) => setParams(p => { const n = new URLSearchParams(p); if (v == null || v === '') n.delete(k); else n.set(k, v); return n }, { replace: true })
  const setRoutes = (rs: string[]) => set('routes', rs.join(','))

  const routes = useApi(o => api.routes({}, o), 'routes')
  const ready = chosen.length >= MIN_ROUTES
  const key = `compare:${chosen.join(',')}:${daytype}:${period}:${sameDays}`
  const cmp = useApi(o => (ready ? api.compare(chosen, { daytype, period, same_days: sameDays }, o) : Promise.resolve(null)), key)
  const groupOf = routes.status === 'ok' ? new Map(routes.data.routes.map(r => [r.route, r.group_id])) : new Map<string, number | null>()
  const addable = routes.status === 'ok' ? sortByRoute(routes.data.routes.filter(r => !chosen.includes(r.route)), r => r.route) : []

  return (
    <div>
      <div className="eyebrow">Compare</div>
      <h1 className="text-xl font-semibold tracking-tight">How do these routes differ?</h1>
      <div className="mt-4">
        <Sentence>
          Comparing{' '}
          {chosen.map(r => (
            <span key={r} className="mr-1 inline-flex items-center gap-0.5 align-middle">
              <RouteSign route={r} groupId={groupOf.get(r)} size="sm" />
              <button type="button" className="px-1 text-sm text-ink-2 hover:text-ink" aria-label={`Remove route ${r}`}
                      onClick={() => setRoutes(chosen.filter(x => x !== r))}>×</button>
            </span>
          ))}
          {chosen.length < MAX_ROUTES && routes.status === 'ok' && (
            <Choice label="Add a route" value="" onChange={v => v && setRoutes([...chosen, v])}
                    options={[{ value: '', text: chosen.length ? 'add a route' : 'choose routes' },
                              ...addable.map(r => ({ value: r.route, text: r.route_long_name ? `${r.route} ${r.route_long_name}` : r.route }))]} />
          )}
          {' '}on <Choice label="Day type" value={daytype} onChange={v => set('daytype', v === 'W' ? null : v)}
                          options={(Object.keys(DAYTYPE_TEXT) as DayType[]).map(d => ({ value: d, text: DAYTYPE_TEXT[d] }))} /> in{' '}
          <Choice label="Period" value={period} onChange={v => set('period', v === 'full_matched_window' ? null : v)}
                  options={(Object.keys(PERIOD_TEXT) as PeriodName[]).map(p => ({ value: p, text: PERIOD_TEXT[p] }))} />, using{' '}
          <Choice label="Days compared" value={sameDays ? 'same' : 'own'} onChange={v => set('same_days', v === 'same' ? 'true' : null)}
                  options={[{ value: 'own', text: "each route's own observed days" }, { value: 'same', text: 'the same days only' }]} />.
        </Sentence>
        <p className="-mt-3 mb-5 text-xs text-ink-2">Choose {MIN_ROUTES} to {MAX_ROUTES} routes. The choice is kept in the page address, so it can be shared.</p>
      </div>

      {!ready
        ? <Empty message={`Choose at least ${MIN_ROUTES} routes to compare (${chosen.length} chosen).`} />
        : <AsyncBlock state={cmp} retry={cmp.retry} label="Loading the comparison" isEmpty={c => c == null}>
            {c => <CompareBody c={c!} groupOf={groupOf} onSameDays={() => set('same_days', 'true')} />}
          </AsyncBlock>}
    </div>
  )
}

function CompareBody({ c, groupOf, onSameDays }: { c: CompareResponse; groupOf: Map<string, number | null>; onSameDays: () => void }) {
  const cutoff = useCutoff()
  const coverage = useApi(o => api.coverage(o), 'coverage')
  const applied = coverage.status === 'ok' ? archiveRange(coverage.data.archives, c.map.geometry_version) : null
  const request = buildUrl('/api/routes/compare', { routes: c.routes.map(r => r.route).join(','), daytype: c.daytype, period: c.period.name,
                                                   same_days: c.same_days || undefined }, { cutoff })
  const prov = (r: CompareRoute, m: RankingMetric): ProvenanceInfo => {
    const ind = r.indicators?.[m]
    return {
      title: `Route ${r.route} · ${ind?.label.toLowerCase() ?? m}`, value: ind?.value ?? null, digits: DIGITS[m], unit: ind?.unit,
      formula: ind ? `${ind.numerator_label} ÷ ${ind.denominator_label}, summed over the ${c.basis_label.replace(/^values on /, '')}` : c.basis_label,
      numerator: ind ? { label: ind.numerator_label, value: ind.numerator } : undefined,
      denominator: ind ? { label: ind.denominator_label, value: ind.denominator, digits: m === 'rides_per_scheduled_hour' ? 1 : 0 } : undefined,
      days: { observed: r.coverage.observed_days, gateLabel: c.configuration.gate_label },
      period: { name: c.period.label, start: c.period.start, end: c.period.end }, daytype: DAYTYPE_TEXT[c.daytype],
      missing: ind?.value == null ? { reason: ind?.reason ?? r.no_matched_days_reason ?? 'unavailable' } : undefined,
      dataVersion: c.data_version, request,
    }
  }
  const row = (label: ReactNode, cell: (r: CompareRoute) => ReactNode, sub?: string, key = String(label)) => (
    <tr key={key}><th scope="row" className="text-left font-normal">{label}{sub && <span className="block text-xs text-ink-2">{sub}</span>}</th>
      {c.routes.map(r => <td key={r.route} className="n">{cell(r)}</td>)}</tr>
  )

  return (
    <div className="space-y-6">
      {c.comparable_note && (
        <div className="flex flex-wrap items-center gap-3">
          <ApiLabel warn text={`${c.comparable_note}. All ${c.routes.length} routes were observed on ${fmt(c.common_matched_days)} of the same dates.`} />
          {c.common_matched_days > 0 && <button type="button" className="btn-secondary" onClick={onSameDays}>Use the same days only</button>}
        </div>
      )}
      {c.same_days && <p className="text-sm"><ApiLabel text={`Same days only: ${c.basis_label}`} />{c.rank_note && <span className="ml-2 text-xs text-ink-2">{c.rank_note}.</span>}</p>}

      <CompareInsight c={c} />

      <Panel title={`${c.routes.length} routes, ${DAYTYPE_TEXT[c.daytype]}, ${c.period.label.toLowerCase()}`}
             purpose={`${fmtRange(c.period.start, c.period.end)} · ${c.basis_label}.`}
             howToRead={`Each column is one route. #n is its network rank among all routes${c.same_days ? ' (left out when comparing the same days only)' : ''}; click a value for how it was made. ${c.caveat}`}>
        <div className="-mx-4 overflow-x-auto">
          <table className="data-table">
            <thead><tr><th>Measure</th>{c.routes.map(r => (
              <th key={r.route} className="n"><Link to={`/route/${encodeURIComponent(r.route)}`} className="no-underline" aria-label={`Open route ${r.route}`}>
                <RouteSign route={r.route} groupId={groupOf.get(r.route) ?? r.group?.group_id} size="sm" /></Link></th>))}</tr></thead>
            <tbody>
              {METRIC_ORDER.map(m => row(c.routes.find(r => r.indicators)?.indicators?.[m].label ?? m, r => (
                r.indicators == null
                  ? <Value value={null} reason={r.no_matched_days_reason} />
                  : <span className="whitespace-nowrap"><Num p={prov(r, m)} showUnit={false} />
                      {r.indicators[m].network_rank != null && <span className="ml-1.5 text-xs text-ink-2">#{r.indicators[m].network_rank}</span>}</span>
              ), c.routes.find(r => r.indicators)?.indicators?.[m].unit, m))}
              {row('Scheduled trips per day', r => <Value value={r.service?.mean_scheduled_trips} digits={0} reason={r.no_matched_days_reason} />, c.units.scheduled_trips)}
              {row('Scheduled trip-hours per day', r => <Value value={r.service?.mean_scheduled_service_hours} digits={0} reason={r.no_matched_days_reason} />, c.units.scheduled_service_hours)}
              {row('Observed days', r => <span className="num">{fmt(r.coverage.observed_days)}</span>, 'recorded rides and scheduled service')}
              {row('Recorded days without a schedule', r => <span className="num">{fmt(r.coverage.recorded_days_without_schedule)}</span>, 'in the whole period')}
              {row('Scheduled days without a record', r => <span className="num">{fmt(r.coverage.scheduled_days_without_record)}</span>, 'in the whole period')}
              {row('Days with incomplete trip times', r => <span className="num">{fmt(r.coverage.incomplete_duration_days)}</span>, 'in the whole period')}
              {row('Group', r => r.group?.group_id != null
                ? <span className="text-sm">Group {r.group.group_id}</span>
                : <span className="inline-block max-w-[13rem] whitespace-normal text-xs text-ink-2">{r.group?.ungrouped_reason ? `ungrouped – ${r.group.ungrouped_reason}` : c.groups_note ? `unavailable – ${c.groups_note}` : 'ungrouped'}</span>)}
            </tbody>
          </table>
        </div>
      </Panel>

      <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,7fr)_minmax(0,5fr)]">
        <Panel title="Map" purpose="Each route's most common path per direction, coloured by group.">
          {c.map.lines.length === 0
            ? <Empty message={c.map.routes_without_lines.map(x => `Route ${x.route}: ${x.reason}`).join('; ') || 'No lines for these routes.'} />
            : <div className="-mx-4 -my-3">
                <RouteMap lines={c.map.lines.map(l => ({ ...l, group_id: groupOf.get(l.route) ?? null }))} height={380} weight={3} />
                {c.map.routes_without_lines.length > 0 && (
                  <p className="px-4 pt-2 text-xs text-ink-2">Not drawn: {c.map.routes_without_lines.map(x => `route ${x.route} (${x.reason})`).join('; ')}.</p>
                )}
                <MapCaption geometryVersion={c.map.geometry_version ?? 'unavailable'} appliedStart={applied?.start} appliedEnd={applied?.end}
                            pathLabel={c.map.label} displayNote="stored lines, exact" />
              </div>}
        </Panel>
        <Panel title="Shared stops among these routes" purpose={c.map.geometry_version ? `Timetable ${c.map.geometry_version}.` : undefined}>
          {c.overlap.length === 0
            ? <p className="text-sm text-ink-2">None of these routes share a stop in this timetable.</p>
            : <div className="space-y-3">
                <ApiLabel warn text={c.overlap[0]!.interpretation} />
                <div className="-mx-4 overflow-x-auto">
                  <table className="data-table">
                    <thead><tr><th>Pair</th><th className="n">Shared stops</th><th className="n">Jaccard</th><th className="n">Share of smaller route</th></tr></thead>
                    <tbody>{c.overlap.map(o => (
                      <tr key={`${o.route_a}|${o.route_b}`}>
                        <td className="whitespace-nowrap"><RouteSign route={o.route_a} groupId={groupOf.get(o.route_a)} size="sm" /> and <RouteSign route={o.route_b} groupId={groupOf.get(o.route_b)} size="sm" /></td>
                        <td className="n num">{fmt(o.shared_stop_count)}</td>
                        <td className="n num">{fmt(o.jaccard_stop_overlap, 3)}</td>
                        <td className="n num">{fmtPct(o.smaller_route_stop_overlap)} %</td>
                      </tr>))}</tbody>
                  </table>
                </div>
              </div>}
        </Panel>
      </div>
    </div>
  )
}

/** Which route leads on each measure, and whether one route leads on all three; counted from the response. */
function CompareInsight({ c }: { c: CompareResponse }) {
  const lead = METRIC_ORDER.map(m => ({ m, label: c.routes.find(r => r.indicators)?.indicators?.[m].label.toLowerCase() ?? m, l: leaders(c.routes, m) }))
  const known = lead.filter(x => x.l != null)
  const names = (rs: string[]) => rs.map(r => `route ${r}`).join(' and ')
  const distinct = new Set(known.flatMap(x => x.l!.routes)).size
  return (
    <div className="border-l-[3px] border-brand pl-4 text-md leading-8">
      {known.length === 0
        ? <p>No route has a value on these settings ({c.routes[0]?.no_matched_days_reason ?? 'unavailable'}).</p>
        : <p>
            Highest {known.map((x, i) => <span key={x.m}>{i > 0 && (i === known.length - 1 ? ' and ' : '; ')}{x.label}: <span className="font-semibold">{names(x.l!.routes)}</span></span>)}.
            {' '}{distinct === 1
              ? `One route leads on ${known.length === 1 ? 'the only measure with values' : `all ${known.length} measures with values`}.`
              : `${distinct} different routes lead across the ${known.length} measures, so no single number says which route is "best".`}
          </p>}
    </div>
  )
}
