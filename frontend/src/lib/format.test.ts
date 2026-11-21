import { describe, expect, it } from 'vitest'
import { fmt, fmtPct, fmtRank } from './format'

describe('fmt: missing is never 0', () => {
  it('null and undefined read "unavailable", with the reason when given', () => {
    expect(fmt(null)).toBe('unavailable')
    expect(fmt(undefined, 2, 'no matched days')).toBe('unavailable – no matched days')
    expect(fmt(Number.NaN, 0, 'x')).toBe('unavailable – x')
  })
  it('a recorded zero stays 0 (it is a value, not a gap)', () => {
    expect(fmt(0)).toBe('0')
    expect(fmt(0, 2)).toBe('0.00')
  })
  it('numbers get thousands separators and fixed decimals', () => {
    expect(fmt(1120604)).toBe('1,120,604')
    expect(fmt(99.915, 3)).toBe('99.915')
  })
})

describe('fmtRank', () => {
  it('unranked rows carry their reason', () => {
    expect(fmtRank(null, 125, 'fewer than 20 observed days')).toBe('unranked – fewer than 20 observed days')
    expect(fmtRank(3, 125)).toBe('rank 3 of 125')
  })
})

describe('fmtPct', () => {
  it('"100" only when the share is exactly 1', () => {
    expect(fmtPct(1)).toBe('100')
    expect(fmtPct(0.9996)).toBe('99.9')
    expect(fmtPct(0.996)).toBe('99.6')
    expect(fmtPct(0.944)).toBe('94')
  })
  it('missing stays unavailable, never 0', () => {
    expect(fmtPct(null, 'no stops')).toBe('unavailable – no stops')
  })
})
