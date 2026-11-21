import { describe, expect, it } from 'vitest'
import { END_WORDS, rankingEnds } from './ends'

const rows = [
  { route: '9', rank: 2, value: 58 }, { route: '79', rank: 1, value: 61 }, { route: '49', rank: 2, value: 58 },
  { route: '3', rank: 4, value: 40 }, { route: '55A', rank: 5, value: 21 }, { route: '125', rank: 6, value: 9 },
  { route: '10', rank: null, value: null }, { route: '1001', rank: null, value: null },
]

describe('rankingEnds', () => {
  it('highest first at the top end, lowest first at the bottom end', () => {
    const e = rankingEnds(rows, 3)
    expect(e.high.map(r => r.route)).toEqual(['79', '9', '49'])   // tie at rank 2 kept, in natural route order (9 before 49)
    expect(e.low.map(r => r.route)).toEqual(['125', '55A', '3'])
  })
  it('unranked routes are counted, never placed at either end', () => {
    const e = rankingEnds(rows, 3)
    expect(e.unranked).toBe(2)
    expect([...e.high, ...e.low].some(r => r.rank == null)).toBe(false)
  })
  it('the two ends never overlap when few routes are ranked', () => {
    const e = rankingEnds(rows.slice(0, 3), 3)
    expect(e.high.length).toBe(1)
    expect(e.low.length).toBe(1)
    expect(e.high[0]!.route).not.toBe(e.low[0]!.route)
  })
  it('uses neutral words', () => {
    expect(Object.values(END_WORDS)).toEqual(['highest', 'lowest'])
    expect(JSON.stringify(END_WORDS)).not.toMatch(/best|worst/i)
  })
})
