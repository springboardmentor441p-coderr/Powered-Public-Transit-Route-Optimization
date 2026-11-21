import { describe, expect, it } from 'vitest'
import type { RankingRow } from '../api/types'
import { fieldWidth } from './format'
import { displayedGate, higherMeans, orderRanked, parseMinDays, rankMovement, reasonKind, topOverlap, unrankedSummary } from './closerLook'

const R = (route: string, rank: number | null, reason: string | null = null): RankingRow => ({
  route, rank, reason, eligible: rank != null, observed_days: 30, scheduled_service_days: 30,
  incomplete_duration_days: 0, numerator: null, denominator: null, value: null,
})

describe('unrankedSummary', () => {
  it('counts unranked rows by reason, ignoring the per-route day count', () => {
    const s = unrankedSummary([
      R('1', 1), R('2', null, 'no scheduled service of this day type'), R('3', null, 'no scheduled service of this day type'),
      R('4', null, 'fewer than 20 observed days (7)'), R('5', null, 'fewer than 20 observed days (15)'),
      R('6', null, 'no scheduled service of this day type'),
    ])
    expect(s.total).toBe(5)
    expect(s.parts).toEqual([
      { reason: 'no scheduled service of this day type', count: 3 },
      { reason: 'fewer than 20 observed days', count: 2 },
    ])
  })
  it('is empty when every route is ranked', () => {
    expect(unrankedSummary([R('1', 1)])).toEqual({ total: 0, parts: [] })
  })
  it('a missing reason is named, not dropped', () => {
    expect(reasonKind(null)).toBe('no reason given')
  })
})

describe('orderRanked', () => {
  const rows = [R('b', 2), R('x', null, 'r'), R('a', 1), R('c', 2)]
  it('highest first puts rank 1 first and leaves unranked rows out', () => {
    expect(orderRanked(rows, false).map(r => r.route)).toEqual(['a', 'b', 'c'])
  })
  it('lowest first reverses the ranks, ties keep route order', () => {
    expect(orderRanked(rows, true).map(r => r.route)).toEqual(['b', 'c', 'a'])
  })
})

describe('topOverlap', () => {
  it('counts routes in the top n of both', () => {
    expect(topOverlap([R('a', 1), R('b', 2), R('c', 3)], [R('c', 1), R('a', 2), R('b', 3)], 2)).toEqual({ n: 2, both: 1 })
  })
  it('never uses more than the ranked routes, and is null when nothing is ranked', () => {
    expect(topOverlap([R('a', 1)], [R('a', 1), R('b', 2)], 10)).toEqual({ n: 1, both: 1 })
    expect(topOverlap([R('a', null, 'r')], [R('a', 1)], 10)).toBeNull()
  })
})

describe('rankMovement', () => {
  it('compares only routes ranked in both periods', () => {
    const dev = [R('a', 1), R('b', 2), R('c', 9), R('d', null, 'r')]
    const full = [R('a', 1), R('b', 5), R('c', 3), R('d', 4)]
    expect(rankMovement(dev, full)).toEqual({ compared: 3, same: 1, within3: 2 })
  })
})

describe('parseMinDays', () => {
  it('accepts any whole number of 1 or more', () => {
    expect(parseMinDays('1')).toBe(1)
    expect(parseMinDays(' 37 ')).toBe(37)
  })
  it('refuses 0, negatives, decimals and text', () => {
    for (const t of ['0', '-3', '2.5', '', 'ten']) expect(parseMinDays(t)).toBeNull()
  })
})

describe('displayedGate', () => {
  it('shows the gate the API applied, whatever was typed or set before', () => {
    expect(displayedGate(20, null, 20)).toBe(20)
    expect(displayedGate(40, 40, 20)).toBe(40)
    expect(displayedGate(20, 2, 20)).toBe(20)         // a stale "2" never wins over the applied 20
  })
  it('before the first answer: the requested value, else the reference', () => {
    expect(displayedGate(undefined, 7, 20)).toBe(7)
    expect(displayedGate(undefined, null, 20)).toBe(20)
  })
})

describe('fieldWidth', () => {
  it('leaves one ch per digit, plus padding, so the whole gate is visible', () => {
    for (const gate of [1, 20, 120, 1000]) {
      const chars = Number(/calc\((\d+)ch/.exec(fieldWidth(String(gate)))![1])
      expect(chars).toBeGreaterThan(String(gate).length)
    }
  })
})

describe('higherMeans', () => {
  it('reads each measure in plain words from the API labels', () => {
    expect(higherMeans('recorded rides', 'scheduled trip-hours')).toBe('Higher value = more recorded rides for each scheduled trip-hour.')
    expect(higherMeans('recorded rides', 'observed days')).toBe('Higher value = more recorded rides for each observed day.')
  })
})
