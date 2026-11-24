import { describe, expect, it } from 'vitest'
import type { ScenarioResponse, ScenarioRow, ScenarioSide, ScenarioTotal } from '../api/types'
import { builderFromRequest, builderParams, fmtChange, fmtRankMove, fromTo, insights, parseBuilder, toRequest } from './scenarios'

const side = (o: Partial<ScenarioSide>): ScenarioSide => ({
  days: 175, rides_per_day: 13766.5, trips_per_day: 270.6, hours_per_day: 386.7, mean_trip_minutes: 85.8,
  rides_per_scheduled_trip: 50.88, rides_per_scheduled_hour: 35.598, rides_sum: 1, scheduled_trips_sum: 1, scheduled_hours_sum: 1,
  reasons: {}, rank_rides_per_scheduled_trip: 10, rank_rides_per_scheduled_trip_reason: null,
  rank_rides_per_scheduled_hour: 58, rank_rides_per_scheduled_hour_reason: null, ...o,
})
const row = (o: Partial<ScenarioRow>): ScenarioRow => ({
  route: '49', group_id: 0, status: 'changed', note: null, demand_assumed: false, structural_zero: false,
  baseline: side({}), scenario: side({ rides_per_scheduled_hour: 29.665, rides_per_scheduled_trip: 42.4, rank_rides_per_scheduled_hour: 86 }),
  change_percent: { rides_per_day: 0, trips_per_day: 20, hours_per_day: 20, rides_per_scheduled_trip: -16.7, rides_per_scheduled_hour: -16.7 },
  rank_change: { rides_per_scheduled_trip: -11, rides_per_scheduled_hour: -28 }, ...o,
})
const total = (b: number | null, s: number | null, c: number | null = null): ScenarioTotal => ({ baseline: b, scenario: s, routes_included: 2, change_percent: c })
const resp = (rows: ScenarioRow[], stress: number | null = null, group = false): ScenarioResponse => ({
  data_version: 'dv', mode: 'historical_analysis', mode_label: 'Historical analysis',
  cutoff: { requested: null, applied: false, permitted_through: '2026-07-31' }, label: 'Scenario assumption', note: '', spec_reference: '',
  scenario: {
    baseline: { group: group ? { group_id: 1, group_name: 'G', group_version: 'g' } : null } as ScenarioResponse['scenario']['baseline'],
    inputs: { service: [], demand_stress: stress == null ? null : { percent: stress, scope: 'baseline_routes', routes: null } },
    assumptions: [], result_sha256: 'x', versions: { data_version: 'dv', group_version: null, forecast_run_id: null, model_version: null },
    cutoff: '2026-07-31', virtual_date: null, saved: false,
    result: {
      rows, other_rank_changes: [{ route: '1', rank_before: 64, rank_after: 63 }],
      totals: {
        selected: { rides_per_day: total(100, 85, -15), trips_per_day: total(10, 10, 0), hours_per_day: total(5, 5, 0),
                    rides_per_scheduled_trip: total(10, 8.5), rides_per_scheduled_hour: total(20, 17, -15), routes: rows.length, left_out: [] },
        network: { rides_per_day: total(1, 1), trips_per_day: total(1, 1), hours_per_day: total(1, 1), rides_per_scheduled_trip: total(1, 1),
                   rides_per_scheduled_hour: total(1, 1), routes: 125, left_out: [] },
      },
      ranked_routes: { rides_per_scheduled_trip: { baseline: 123, scenario: 123 }, rides_per_scheduled_hour: { baseline: 123, scenario: 123 } },
      units: { rides: '', scheduled_trips: '', scheduled_service_hours: '', rides_per_scheduled_trip: '', rides_per_scheduled_hour: '' },
      ranking: { min_observed_days: 20, reference_min_observed_days: 20, ties: '', direction: '' },
    },
  },
})

describe('builder', () => {
  it('reads the address and builds the request: +20 % trips on route 49, weekdays, full window', () => {
    const b = parseBuilder(new URLSearchParams('routes=49'))
    expect(toRequest(b)).toEqual({
      baseline: { routes: ['49'], group_id: null, period: 'full_matched_window', daytype: 'W', demand: 'recorded' },
      service: [{ routes: null, trips: { how: 'percent', value: 20 }, trip_hours: null }], demand_stress: null,
    })
  })
  it('a decrease is a negative percent; set is a value per day; the stress line is separate', () => {
    expect(toRequest(parseBuilder(new URLSearchParams('routes=49&verb=decrease&amount=10')))!.service[0]!.trips).toEqual({ how: 'percent', value: -10 })
    expect(toRequest(parseBuilder(new URLSearchParams('routes=49&verb=set&measure=trip_hours&amount=300')))!.service[0]!.trip_hours).toEqual({ how: 'per_day', value: 300 })
    const r = toRequest(parseBuilder(new URLSearchParams('group=1&daytype=U&verb=keep&stress=-15')))!
    expect(r.service).toEqual([])
    expect(r.baseline).toMatchObject({ routes: null, group_id: 1, daytype: 'U' })
    expect(r.demand_stress).toEqual({ percent: -15, scope: 'baseline_routes', routes: null })
  })
  it('nothing to calculate: no routes, or keep with no stress', () => {
    expect(toRequest(parseBuilder(new URLSearchParams('')))).toBeNull()
    expect(toRequest(parseBuilder(new URLSearchParams('routes=49&verb=keep')))).toBeNull()
  })
  it('predicted demand sends no period or day type', () => {
    expect(toRequest(parseBuilder(new URLSearchParams('routes=22&demand=predicted')))!.baseline).toMatchObject({ period: null, daytype: null, demand: 'predicted' })
  })
  it('round-trips a saved request and the address', () => {
    const b = parseBuilder(new URLSearchParams('routes=49,22&daytype=A&verb=decrease&amount=5&stress=+10&stress_scope=network'))
    expect(builderFromRequest(toRequest(b)!)).toEqual(b)
    const p = new URLSearchParams(Object.entries(builderParams(b)).filter(([, v]) => v != null) as [string, string][])
    expect(parseBuilder(p)).toEqual(b)
  })
})

describe('insights (computed from the response, never hard-coded)', () => {
  it('one route: the ratio falls because demand is held fixed, and the rank moves', () => {
    const s = insights(resp([row({})]))
    expect(s[0]).toBe('On route 49, rides per scheduled hour falls from 35.6 to 29.7 because demand is held fixed while scheduled trip-hours rise by 20.0 %.')
    expect(s[1]).toBe('It moves from rank 58 to rank 86 of 123 ranked routes on rides per scheduled hour, and 1 other route changes rank as a result.')
  })
  it('a group under a demand stress uses the selected totals', () => {
    const rows = [row({ route: '3', status: 'demand_only', rank_change: { rides_per_scheduled_trip: 0, rides_per_scheduled_hour: 0 } }),
                  row({ route: '4', status: 'demand_only', rank_change: { rides_per_scheduled_trip: 0, rides_per_scheduled_hour: 0 } })]
    const s = insights(resp(rows, -15, true))
    expect(s[0]).toBe('Across the group (2 routes with values on both sides), rides per scheduled hour falls from 20.0 to 17.0 because rides are assumed to fall by 15.0 % while the timetable stays the same.')
    expect(s[1]).toBe('No route in the group changes rank on rides per scheduled hour.')
  })
  it('missing values are counted as unavailable, never 0', () => {
    const zero = row({ route: 'Z', status: 'unchanged', structural_zero: true,
                       scenario: side({ rides_per_scheduled_hour: null, reasons: { rides_per_hour: 'no scheduled service on Sundays and holidays, so nothing to compare' } }) })
    const s = insights(resp([row({}), zero]))
    expect(s.at(-1)).toBe('1 of 2 routes have no rides per scheduled hour to compare, shown as unavailable rather than 0 (no scheduled service on Sundays and holidays, so nothing to compare).')
  })
  it('formats changes and rank moves', () => {
    expect(fromTo(35.6, 35.6)).toBe('stays at 35.6')
    expect(fromTo(null, 2)).toBeNull()
    expect(fmtChange(-16.666)).toBe('−16.7 %')
    expect(fmtChange(0)).toBe('no change')
    expect(fmtChange(null)).toBe('unavailable – one side unavailable')
    expect(fmtRankMove(58, 86)).toBe('58 → 86')
    expect(fmtRankMove(null, null)).toBe('unranked')
  })
})
