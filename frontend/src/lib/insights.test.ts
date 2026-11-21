import { describe, expect, it } from 'vitest'
import type { TrendSummary } from '../api/types'
import { addDays, fmtDate, fmtRange } from './dates'
import { linesBounds } from './geo'
import { daytypeLevels, importChecks } from './insights'

const S = (daytype: TrendSummary['daytype'], days: number, mean: number | null): TrendSummary => ({
  daytype, daytype_label: { W: 'weekday', A: 'Saturday', U: 'Sunday/holiday' }[daytype], days,
  mean_rides: mean, median_rides: mean, reason: mean == null ? `no ${daytype} with a ridership record in this range` : null,
})

describe('daytypeLevels', () => {
  it('weekend shares come from the API averages, not from fixed numbers', () => {
    const [w, a, u] = daytypeLevels([S('W', 4, 1000), S('A', 1, 700), S('U', 1, 500)])
    expect(w!.shareOfWeekday).toBeNull()
    expect(a!.shareOfWeekday).toBeCloseTo(0.7)
    expect(u!.shareOfWeekday).toBeCloseTo(0.5)
    expect(w!.total).toBe(4000)                              // numerator of the mean, for "How was this made?"
    const other = daytypeLevels([S('W', 4, 2000), S('A', 1, 700), S('U', 1, 500)])
    expect(other[1]!.shareOfWeekday).toBeCloseTo(0.35)       // different data, different sentence
  })
  it('a missing average gives a null share with a reason, never 0', () => {
    const [, a, u] = daytypeLevels([S('W', 0, null), S('A', 1, 700), S('U', 0, null)])
    expect(a!.shareOfWeekday).toBeNull()
    expect(a!.reason).toBe('no weekday with a record in this range')
    expect(u!.mean).toBeNull()
    expect(u!.shareOfWeekday).toBeNull()
    expect(u!.reason).toContain('no U')
  })
})

describe('importChecks', () => {
  it('counts identities with 0 violations', () => {
    expect(importChecks({ import_identities: { a: 0, b: 0, c: 2 }, import_identities_hold: false, note: '' }))
      .toEqual({ held: 2, total: 3 })
  })
})

describe('linesBounds', () => {
  it('swaps GeoJSON [lon, lat] to Leaflet [lat, lon] and is null without points', () => {
    const line = (c: [number, number][]) => ({ line_geojson: { type: 'LineString' as const, coordinates: c } })
    expect(linesBounds([line([[-87.7, 41.8], [-87.6, 41.9]]), line([[-87.65, 42.0]])]))
      .toEqual([[41.8, -87.7], [42.0, -87.6]])
    expect(linesBounds([])).toBeNull()
  })
})

describe('dates', () => {
  it('formats and shifts UTC calendar dates', () => {
    expect(fmtDate('2025-11-23')).toBe('23 Nov 2025')
    expect(fmtRange('2025-11-23', '2026-07-31')).toBe('23 Nov 2025 – 31 Jul 2026')
    expect(addDays('2025-11-23', -1)).toBe('2025-11-22')
    expect(addDays('2024-02-28', 1)).toBe('2024-02-29')
  })
})
