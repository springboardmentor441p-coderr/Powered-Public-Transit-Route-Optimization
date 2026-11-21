import { describe, expect, it } from 'vitest'
import type { CompareRoute, Indicator } from '../api/types'
import { archiveRange, leaders, parseRoutes } from './compare'

const I = (value: number | null): Indicator => ({ label: 'x', unit: 'u', value, network_rank: null, eligible: value != null,
  reason: value == null ? 'no matched days' : null, numerator: null, denominator: null,
  numerator_label: 'recorded rides', denominator_label: 'observed days' })
const C = (route: string, demand: number | null, hour: number | null): CompareRoute => ({
  route, no_matched_days_reason: null, service: null, map_lines: 0,
  indicators: { observed_daily_demand: I(demand), rides_per_scheduled_trip: I(null), rides_per_scheduled_hour: I(hour) },
  coverage: { observed_days: 1, scheduled_service_days: 1, incomplete_duration_days: 0, recorded_days_without_schedule: 0, scheduled_days_without_record: 0 },
})

describe('parseRoutes', () => {
  it('trims, drops blanks and repeats, keeps at most 8', () => {
    expect(parseRoutes('49, X49,,49,10')).toEqual(['10', '49', 'X49'])
    expect(parseRoutes(null)).toEqual([])
    expect(parseRoutes('1,2,3,4,5,6,7,8,9,10')).toHaveLength(8)
  })
})

describe('leaders', () => {
  it('finds the highest value; a missing value is never treated as 0', () => {
    expect(leaders([C('a', 100, null), C('b', 300, 20), C('c', null, 50)], 'observed_daily_demand')).toEqual({ routes: ['b'], value: 300 })
    expect(leaders([C('a', 100, null), C('b', 300, 20), C('c', null, 50)], 'rides_per_scheduled_hour')).toEqual({ routes: ['c'], value: 50 })
  })
  it('keeps ties, and is null when no route has a value', () => {
    expect(leaders([C('a', 5, null), C('b', 5, null)], 'observed_daily_demand')?.routes).toEqual(['a', 'b'])
    expect(leaders([C('a', 5, null)], 'rides_per_scheduled_trip')).toBeNull()
  })
})

describe('archiveRange', () => {
  const A = [{ geometry_version: 'v1', captured_date: '2026-07-11', applied_start: '2026-07-11', applied_end: '2026-07-31',
               applied_days: 21, bus_routes: 1, scheduled_routes: 1, map_lines: 1 }]
  it("gives the timetable's own applied dates, not the comparison period", () => {
    expect(archiveRange(A, 'v1')).toEqual({ start: '2026-07-11', end: '2026-07-31' })
  })
  it('is null for an unknown or missing version', () => {
    expect(archiveRange(A, 'v9')).toBeNull()
    expect(archiveRange(A, null)).toBeNull()
  })
})
