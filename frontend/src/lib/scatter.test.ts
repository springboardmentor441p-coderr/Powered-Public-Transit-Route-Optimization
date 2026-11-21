import { describe, expect, it } from 'vitest'
import type { RouteValues } from '../api/types'
import { insideOtherGroup, scatterPoints, type ScatterPoint } from './scatter'

const X = 'mean_weekday_rides'
const Y = 'sunday_holiday_to_weekday_rides_ratio'

function route(r: string, g: number | null, x: number | null, y: RouteValues['values'][number]): RouteValues {
  return {
    route: r, group_id: g, weekday_observed_days: 85,
    values: [{ feature: X, label: 'Average weekday rides', unit: 'rides/day', value: x, status: x == null ? 'unavailable' : 'available',
               reason: x == null ? 'unavailable in the stored development profile' : null }, y],
  }
}
const ROUTES: RouteValues[] = [
  route('22', 0, 15000, { feature: Y, label: 'Sunday/holiday level vs weekday', unit: 'ratio', value: 0.61, status: 'available', reason: null }),
  route('169', 1, 900, { feature: Y, label: 'Sunday/holiday level vs weekday', unit: 'ratio', value: null, status: 'insufficient_observations',
                         reason: 'unavailable: 0 matched Sunday/holiday days of 3 scheduled (fewer than 8)' }),
  route('55A', 1, 1200, { feature: Y, label: 'Sunday/holiday level vs weekday', unit: 'ratio', value: 0, status: 'no_scheduled_service',
                          reason: 'no scheduled Sunday/holiday service: a structural zero' }),
  route('X1', null, null, { feature: Y, label: 'Sunday/holiday level vs weekday', unit: 'ratio', value: 0.4, status: 'available', reason: null }),
]

describe('scatterPoints', () => {
  it('leaves a missing value off the scatter with a note naming the route and the reason', () => {
    const { plotted, leftOff } = scatterPoints(ROUTES, X, Y)
    expect(plotted.map(p => p.route)).not.toContain('169')
    expect(leftOff.find(l => l.route === '169')?.note)
      .toBe('Route 169 is not plotted (sunday/holiday level vs weekday: unavailable: 0 matched Sunday/holiday days of 3 scheduled (fewer than 8)).')
  })
  it('the note names the measure in words, never by its column key', () => {
    for (const l of scatterPoints(ROUTES, X, Y).leftOff) expect(l.note).not.toMatch(/[a-z]+_[a-z]+/)
  })
  it('never draws a missing value at 0 or at a filled-in value', () => {
    const { plotted } = scatterPoints(ROUTES, X, Y)
    expect(plotted.every(p => Number.isFinite(p.x) && Number.isFinite(p.y))).toBe(true)
    expect(plotted.filter(p => p.y === 0).map(p => p.route)).toEqual(['55A'])   // only the structural zero
  })
  it('plots a structural zero at 0 and keeps its status for the tooltip', () => {
    const p = scatterPoints(ROUTES, X, Y).plotted.find(q => q.route === '55A')
    expect(p).toMatchObject({ x: 1200, y: 0, yStatus: 'no_scheduled_service', groupId: 1 })
  })
  it('a missing value on the x axis is left off too; every route lands in exactly one list', () => {
    const { plotted, leftOff } = scatterPoints(ROUTES, X, Y)
    expect(leftOff.map(l => l.route)).toEqual(['169', 'X1'])
    expect(plotted.length + leftOff.length).toBe(ROUTES.length)
  })
})

describe('insideOtherGroup', () => {
  const P = (route: string, groupId: number | null, x: number, y: number): ScatterPoint =>
    ({ route, groupId, x, y, xStatus: 'available', yStatus: 'available' })
  it('counts grouped routes inside another group box on both axes', () => {
    const pts = [P('a', 0, 10, 10), P('b', 0, 20, 20), P('c', 1, 15, 15), P('d', 1, 30, 30), P('u', null, 15, 15)]
    // c (group 1) sits in group 0's box [10-20]x[10-20]; b (group 0) sits in group 1's box [15-30]x[15-30]
    expect(insideOtherGroup(pts)).toEqual({ inside: 2, grouped: 4 })
  })
  it('separated groups give 0', () => {
    expect(insideOtherGroup([P('a', 0, 1, 1), P('b', 0, 2, 2), P('c', 1, 8, 8), P('d', 1, 9, 9)])).toEqual({ inside: 0, grouped: 4 })
  })
})
