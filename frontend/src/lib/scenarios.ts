// Scenarios screen logic: the sentence builder's state <-> the API request, and the insight sentences.
// Every number in a sentence comes from the API response at render time (CLAUDE.md, UI principles).
import type {
  DayType, PeriodName, ScenarioDemand, ScenarioRequest, ScenarioResponse, ScenarioRow, ScenarioTotal,
} from '../api/types'
import { fmt } from './format'

export type Verb = 'increase' | 'decrease' | 'set' | 'keep'
export type Measure = 'trips' | 'trip_hours'
export type StressScope = 'baseline_routes' | 'network'
export type Builder = {
  routes: string[]; group: number | null; daytype: DayType; period: PeriodName; demand: ScenarioDemand
  verb: Verb; measure: Measure; amount: number
  stress: { dir: 'fall' | 'rise'; percent: number; scope: StressScope } | null
}

export const DAYTYPE_TEXT: Record<DayType, string> = { W: 'weekdays', A: 'Saturdays', U: 'Sundays and holidays' }
export const PERIOD_TEXT: Record<PeriodName, string> = { full_matched_window: 'the full matched window', development: 'the development period' }
export const MEASURE_TEXT: Record<Measure, string> = { trips: 'scheduled trips', trip_hours: 'scheduled trip-hours' }
const VERBS: Verb[] = ['increase', 'decrease', 'set', 'keep']

const num = (s: string | null, fallback: number) => {
  const n = s == null || s === '' ? NaN : Number(s)
  return Number.isFinite(n) ? n : fallback
}

/** The builder, read from the page address (so a scenario being built can be shared or reloaded). */
export function parseBuilder(p: URLSearchParams): Builder {
  const routes = (p.get('routes') ?? '').split(',').map(r => r.trim()).filter(Boolean)
  const group = p.get('group') != null && p.get('group') !== '' && !routes.length ? num(p.get('group'), NaN) : NaN
  const verb = (VERBS as string[]).includes(p.get('verb') ?? '') ? p.get('verb') as Verb : 'increase'
  const stress = p.get('stress')
  return {
    routes: [...new Set(routes)], group: Number.isFinite(group) ? group : null,
    daytype: (['W', 'A', 'U'].includes(p.get('daytype') ?? '') ? p.get('daytype') : 'W') as DayType,
    period: p.get('period') === 'development' ? 'development' : 'full_matched_window',
    demand: p.get('demand') === 'predicted' ? 'predicted' : 'recorded',
    verb, measure: p.get('measure') === 'trip_hours' ? 'trip_hours' : 'trips', amount: num(p.get('amount'), 20),
    stress: stress == null ? null : {
      dir: stress.startsWith('+') ? 'rise' : 'fall', percent: Math.abs(num(stress, 15)),
      scope: p.get('stress_scope') === 'network' ? 'network' : 'baseline_routes',
    },
  }
}

/** The API request for a builder; null when there is nothing to calculate yet (no routes, or no change at all). */
export function toRequest(b: Builder): ScenarioRequest | null {
  if (!b.routes.length && b.group == null) return null
  if (b.verb === 'keep' && !b.stress) return null
  const change = b.verb === 'keep' ? null
    : b.verb === 'set' ? { how: 'per_day' as const, value: b.amount }
    : { how: 'percent' as const, value: b.verb === 'decrease' ? -b.amount : b.amount }
  const predicted = b.demand === 'predicted'
  return {
    baseline: {
      routes: b.group == null ? b.routes : null, group_id: b.group,
      period: predicted ? null : b.period, daytype: predicted ? null : b.daytype, demand: b.demand,
    },
    service: change ? [{ routes: null, trips: b.measure === 'trips' ? change : null, trip_hours: b.measure === 'trip_hours' ? change : null }] : [],
    demand_stress: b.stress ? { percent: b.stress.dir === 'fall' ? -b.stress.percent : b.stress.percent, scope: b.stress.scope, routes: null } : null,
  }
}

/** The builder that rebuilds a saved scenario's request (to make a new version of it). */
export function builderFromRequest(r: ScenarioRequest): Builder {
  const line = r.service[0]
  const c = line?.trips ?? line?.trip_hours ?? null
  const s = r.demand_stress
  return {
    routes: r.baseline.routes ?? [], group: r.baseline.group_id, daytype: r.baseline.daytype ?? 'W',
    period: r.baseline.period ?? 'full_matched_window', demand: r.baseline.demand,
    verb: c == null ? 'keep' : c.how === 'per_day' ? 'set' : c.value < 0 ? 'decrease' : 'increase',
    measure: line?.trip_hours ? 'trip_hours' : 'trips', amount: c == null ? 20 : Math.abs(c.value),
    stress: s ? { dir: s.percent < 0 ? 'fall' : 'rise', percent: Math.abs(s.percent), scope: s.scope === 'network' ? 'network' : 'baseline_routes' } : null,
  }
}

/** Builder -> page address parameters (defaults left out). */
export function builderParams(b: Builder): Record<string, string | null> {
  return {
    routes: b.group == null && b.routes.length ? b.routes.join(',') : null, group: b.group == null ? null : String(b.group),
    daytype: b.daytype === 'W' ? null : b.daytype, period: b.period === 'full_matched_window' ? null : b.period,
    demand: b.demand === 'recorded' ? null : b.demand, verb: b.verb === 'increase' ? null : b.verb,
    measure: b.measure === 'trips' ? null : b.measure, amount: b.amount === 20 ? null : String(b.amount),
    stress: b.stress ? `${b.stress.dir === 'rise' ? '+' : '-'}${b.stress.percent}` : null,
    stress_scope: b.stress?.scope === 'network' ? 'network' : null,
  }
}

const moved = (r: ScenarioRow) => r.status !== 'unchanged'
const pct = (x: number) => `${fmt(Math.abs(x), 1)} %`
const change = (x: number | null | undefined) => x == null || Math.abs(x) < 1e-9 ? null : x

/** "falls from 35.6 to 29.7" / "rises from …" / "stays at …"; null when either side is unavailable. */
export function fromTo(b: number | null, s: number | null, digits = 1): string | null {
  if (b == null || s == null) return null
  const fb = fmt(b, digits), fs = fmt(s, digits)
  if (fb === fs) return `stays at ${fb}`
  return `${s < b ? 'falls' : 'rises'} from ${fb} to ${fs}`
}

function cause(hours: number | null, rides: number | null, stressed: boolean): string {
  const h = change(hours), r = change(rides)
  if (h != null && !stressed) return `because demand is held fixed while scheduled trip-hours ${h > 0 ? 'rise' : 'fall'} by ${pct(h)}`
  if (h == null && r != null) return `because rides are assumed to ${r > 0 ? 'rise' : 'fall'} by ${pct(r)} while the timetable stays the same`
  if (h != null && r != null) return `because scheduled trip-hours ${h > 0 ? 'rise' : 'fall'} by ${pct(h)} and rides are assumed to ${r > 0 ? 'rise' : 'fall'} by ${pct(r)}`
  return 'because neither demand nor trip-hours change'
}

/** The insight sentences above the comparison, computed from the response. */
export function insights(resp: ScenarioResponse): string[] {
  const s = resp.scenario, res = s.result
  const rows = res.rows.filter(moved)
  const stressed = s.inputs.demand_stress != null
  const out: string[] = []
  if (rows.length === 0) {
    out.push('Nothing changes: the service change could not be applied to any route in this baseline (see the notes below).')
    return out
  }
  const single = rows.length === 1 || res.rows.length === 1
  if (single && rows[0]!.status === 'service_added') {
    // One sentence says what was added and why its ratios stay unknown; the reason is not repeated after it
    const r = rows[0]!
    out.push(`Route ${r.route} gets ${fmt(r.scenario.trips_per_day, 1)} scheduled trips per day on ${s.baseline.daytype_label}, where it had none. Its rides per scheduled trip and hour stay unavailable: ${r.scenario.reasons.rides_per_trip ?? 'no value'}.`)
    return out
  }
  if (single) {
    const r = rows[0]!
    const ft = fromTo(r.baseline.rides_per_scheduled_hour, r.scenario.rides_per_scheduled_hour)
    const ftTrip = fromTo(r.baseline.rides_per_scheduled_trip, r.scenario.rides_per_scheduled_trip)
    if (ft) out.push(`On route ${r.route}, rides per scheduled hour ${ft} ${cause(r.change_percent.hours_per_day, r.change_percent.rides_per_day, stressed)}.`)
    else if (ftTrip) out.push(`On route ${r.route}, rides per scheduled trip ${ftTrip} ${cause(r.change_percent.trips_per_day, r.change_percent.rides_per_day, stressed)}; rides per scheduled hour is unavailable – ${r.scenario.reasons.rides_per_hour ?? 'no value'}.`)
    else out.push(`On route ${r.route}, rides per scheduled trip and hour are unavailable – ${r.scenario.reasons.rides_per_trip ?? r.note ?? 'no value'}.`)
    const a = r.baseline.rank_rides_per_scheduled_hour, b = r.scenario.rank_rides_per_scheduled_hour
    const of = res.ranked_routes.rides_per_scheduled_hour.scenario
    if (a != null && b != null) {
      out.push(a === b ? `It keeps rank ${a} of ${of} ranked routes on rides per scheduled hour.`
        : `It moves from rank ${a} to rank ${b} of ${of} ranked routes on rides per scheduled hour${res.other_rank_changes.length ? `, and ${res.other_rank_changes.length} other route${res.other_rank_changes.length === 1 ? '' : 's'} change${res.other_rank_changes.length === 1 ? 's' : ''} rank as a result` : ''}.`)
    }
  } else {
    const t: ScenarioTotal = res.totals.selected.rides_per_scheduled_hour
    const ft = fromTo(t.baseline, t.scenario)
    const who = s.baseline.group ? 'the group' : `the ${res.rows.length} routes`
    if (ft) out.push(`Across ${who} (${t.routes_included} routes with values on both sides), rides per scheduled hour ${ft} ${cause(res.totals.selected.hours_per_day.change_percent, res.totals.selected.rides_per_day.change_percent, stressed)}.`)
    const up = res.rows.filter(r => (r.rank_change.rides_per_scheduled_hour ?? 0) > 0).length
    const down = res.rows.filter(r => (r.rank_change.rides_per_scheduled_hour ?? 0) < 0).length
    out.push(up + down === 0 ? `No route in ${who} changes rank on rides per scheduled hour.`
      : `In ${who}, ${down} route${down === 1 ? '' : 's'} move${down === 1 ? 's' : ''} down and ${up} move${up === 1 ? 's' : ''} up the ranking on rides per scheduled hour.`)
  }
  if (res.rows.length === 1) return out  // the route's own sentence already gave any reason
  const unknown = res.rows.filter(r => r.scenario.rides_per_scheduled_hour == null)
  if (unknown.length) {
    const reasons = new Map<string, number>()
    for (const r of unknown) { const k = r.scenario.reasons.rides_per_hour ?? 'no value'; reasons.set(k, (reasons.get(k) ?? 0) + 1) }
    const [top, n] = [...reasons.entries()].sort((a, b) => b[1] - a[1])[0]!
    out.push(`${unknown.length} of ${res.rows.length} route${res.rows.length === 1 ? ' has' : 's have'} no rides per scheduled hour to compare, shown as unavailable rather than 0 (${n === unknown.length ? '' : `most often: `}${top}).`)
  }
  const added = res.rows.filter(r => r.status === 'service_added')
  if (added.length) {  // their reason is already in the sentence above
    out.push(`${added.map(r => `Route ${r.route}`).join(', ')} ${added.length === 1 ? 'gets' : 'get'} new scheduled trips where ${added.length === 1 ? 'it' : 'they'} had none; ${added.length === 1 ? 'its' : 'their'} ratios are among those unavailable.`)
  }
  return out
}

/** "+20.0 %" / "−16.7 %" / "no change"; unavailable stays unavailable. */
export function fmtChange(x: number | null | undefined, reason = 'one side unavailable'): string {
  if (x == null) return `unavailable – ${reason}`
  if (Math.abs(x) < 0.05) return 'no change'
  return `${x > 0 ? '+' : '−'}${fmt(Math.abs(x), 1)} %`
}

/** "58 → 86" (down 28) for a rank pair; unranked sides say so. */
export function fmtRankMove(a: number | null, b: number | null): string {
  if (a == null && b == null) return 'unranked'
  if (a == null) return `unranked → ${b}`
  if (b == null) return `${a} → unranked`
  return a === b ? `${a} (same)` : `${a} → ${b}`
}
