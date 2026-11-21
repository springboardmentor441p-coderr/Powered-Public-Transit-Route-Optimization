import { describe, expect, it } from 'vitest'
import { fmt, fmtRank } from './format'

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
