import { describe, expect, it } from 'vitest'
import type { OverlapRow } from '../api/types'
import { fullyInside, involving, sortPairs, topAgreement } from './sharedStops'

const R = (a: string, b: string, jaccard: number, smaller: number): OverlapRow => ({
  rank: 0, route_a: a, route_b: b, shared_stop_count: 5, route_a_stop_count: 10, route_b_stop_count: 20,
  jaccard_stop_overlap: jaccard, smaller_route_stop_overlap: smaller, route_a_exclusive_fraction: 0.5,
  route_b_exclusive_fraction: 0.75, interpretation: 'corridor review only',
})
const ROWS = [R('1', '2', 0.8, 0.9), R('3', '4', 0.2, 1.0), R('5', '6', 0.5, 0.5), R('7', '8', 0.1, 0.2)]

describe('sortPairs', () => {
  it('orders by the chosen measure, highest or lowest first', () => {
    expect(sortPairs(ROWS, 'jaccard', false).map(r => r.route_a)).toEqual(['1', '5', '3', '7'])
    expect(sortPairs(ROWS, 'smaller', false).map(r => r.route_a)).toEqual(['3', '1', '5', '7'])
    expect(sortPairs(ROWS, 'jaccard', true).map(r => r.route_a)).toEqual(['7', '3', '5', '1'])
  })
  it('does not change the input order', () => {
    sortPairs(ROWS, 'smaller', false)
    expect(ROWS.map(r => r.route_a)).toEqual(['1', '3', '5', '7'])
  })
})

describe('topAgreement', () => {
  it('counts pairs in the top n of both measures', () => {
    expect(topAgreement(ROWS, 2)).toEqual({ n: 2, both: 1 })      // top Jaccard {1,5}, top smaller {3,1}
  })
  it('n never exceeds the pairs, and no pairs gives null', () => {
    expect(topAgreement(ROWS, 10)).toEqual({ n: 4, both: 4 })
    expect(topAgreement([], 10)).toBeNull()
  })
})

describe('fullyInside and involving', () => {
  it('counts pairs where the smaller route shares every stop', () => {
    expect(fullyInside(ROWS)).toBe(1)
  })
  it('keeps pairs with the route on either side; empty keeps all', () => {
    expect(involving(ROWS, '4').map(r => r.route_a)).toEqual(['3'])
    expect(involving(ROWS, '').length).toBe(4)
  })
})
