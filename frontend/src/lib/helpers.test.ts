import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { Value } from '../components/Value'
import { buildRhythm, weekdayIndex } from './rhythm'
import { stability } from './stability'
import { stopShare } from './stopShare'

describe('rhythm grid', () => {
  const days = [
    { date: '2025-11-24', rides: 8000 },                                  // Monday
    { date: '2025-11-27', rides: null, reason: 'Thanksgiving: no record' }, // Thursday
    { date: '2025-11-30', rides: 0 },                                       // Sunday, recorded zero
    { date: '2025-12-01', rides: 4000 },                                    // next Monday
  ]
  const { weeks, weekStarts } = buildRhythm(days)

  it('places each date in its week and weekday (Monday start)', () => {
    expect(weekdayIndex('2025-11-24')).toBe(0)
    expect(weekdayIndex('2025-11-30')).toBe(6)
    expect(weekStarts).toEqual(['2025-11-24', '2025-12-01'])
    expect(weeks[0]![0]).toMatchObject({ kind: 'value', rides: 8000 })
    expect(weeks[1]![0]).toMatchObject({ kind: 'value', rides: 4000 })
  })
  it('keeps a missing day missing, with its reason, and a recorded 0 as a value', () => {
    expect(weeks[0]![3]).toEqual({ kind: 'missing', date: '2025-11-27', reason: 'Thanksgiving: no record' })
    expect(weeks[0]![6]).toEqual({ kind: 'zero', date: '2025-11-30', rides: 0, step: 0 })
  })
  it('days not in the data are "outside", not zero', () => {
    expect(weeks[0]![1]).toEqual({ kind: 'outside' })
  })
  it('larger values get darker steps', () => {
    const a = weeks[0]![0] as { step: number }
    const b = weeks[1]![0] as { step: number }
    expect(a.step).toBeGreaterThan(b.step)
  })
})

describe('stop-share strip', () => {
  it('segments add up to each route\'s stops and to the union', () => {
    const s = stopShare(120, 40, 40)
    expect(s.aOnly + s.shared).toBe(120)
    expect(s.shared + s.bOnly).toBe(40)
    expect(s.union).toBe(120)
    expect(s.a.only + s.a.shared).toBeCloseTo(1)
  })
  it('refuses impossible counts', () => {
    expect(() => stopShare(10, 5, 6)).toThrow()
    expect(() => stopShare(10, 5, 1.5)).toThrow()
  })
})

describe('rank stability', () => {
  it('moved, same and not comparable', () => {
    expect(stability({ rank: 3 }, { rank: 5 })).toMatchObject({ kind: 'moved', places: 2, direction: 'down' })
    expect(stability({ rank: 3 }, { rank: 5 }).text).toBe('Development 3rd → full window 5th (moved 2 places down)')
    expect(stability({ rank: 12 }, { rank: 11 }).text).toContain('moved 1 place up')
    expect(stability({ rank: 1 }, { rank: 1 }).kind).toBe('same')
    expect(stability({ rank: null, reason: 'fewer than 20 observed days (18)' }, { rank: 4 }).text)
      .toBe('not comparable – unranked in development (fewer than 20 observed days (18))')
  })
})

describe('<Value>: a missing value is quieter than a real one', () => {
  const missing = renderToStaticMarkup(createElement(Value, { value: null, reason: 'no matched days' }))
  it('reads "unavailable – reason"', () => {
    expect(missing).toContain('unavailable – no matched days')
  })
  it('is small, normal weight and muted, whatever surrounds it', () => {
    expect(missing).toMatch(/text-xs/)
    expect(missing).toMatch(/font-normal/)
    expect(missing).toMatch(/text-ink-2/)
    expect(missing).not.toMatch(/font-(semibold|bold)|text-(md|lg|xl)/)
  })
  it('a recorded 0 renders as the number 0', () => {
    expect(renderToStaticMarkup(createElement(Value, { value: 0 }))).toContain('>0<')
  })
})
