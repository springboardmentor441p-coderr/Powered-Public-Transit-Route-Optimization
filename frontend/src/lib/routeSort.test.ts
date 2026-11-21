import { describe, expect, it } from 'vitest'
import { compareRoutes, sortByRoute, sortRoutes } from './routeSort'

describe('natural route order', () => {
  it('numbers by value, then suffix', () => {
    expect(sortRoutes(['12', '9', '8A', '1', '119', '8', '2', '126', '3'])).toEqual(['1', '2', '3', '8', '8A', '9', '12', '119', '126'])
    expect(sortRoutes(['53AL', '53', '54', '53A'])).toEqual(['53', '53A', '53AL', '54'])
    expect(sortRoutes(['1001', '100', '103', '2'])).toEqual(['2', '100', '103', '1001'])
  })
  it('letter-prefixed routes after all numeric ones, by prefix, then number', () => {
    expect(sortRoutes(['X49', '4', 'J14', 'X9', 'N5', '201', 'N201', 'X4', 'R22'])).toEqual(['4', '201', 'J14', 'N5', 'N201', 'R22', 'X4', 'X9', 'X49'])
  })
  it('is stable and total: same input, same order; equal only for the same name', () => {
    const a = ['X49', '49', '49B', 'J14', '9']
    expect(sortRoutes(a)).toEqual(sortRoutes([...a].reverse()))
    expect(compareRoutes('49', '49')).toBe(0)
    expect(compareRoutes('49', '49B')).toBeLessThan(0)
  })
  it('sorts objects by their route and does not change the input', () => {
    const rows = [{ route: '12' }, { route: '1' }, { route: 'X9' }]
    expect(sortByRoute(rows, r => r.route).map(r => r.route)).toEqual(['1', '12', 'X9'])
    expect(rows.map(r => r.route)).toEqual(['12', '1', 'X9'])
  })
})
