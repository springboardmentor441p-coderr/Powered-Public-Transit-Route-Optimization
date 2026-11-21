import { describe, expect, it } from 'vitest'
import type { Gain } from '../api/types'
import { gainWords, inSentence, networkSentence, sameRows, scoredShare, topAndRest } from './modelCard'

const G = (model: number, base: number): Gain => ({
  model_mae: model, baseline_mae: base, mae_reduction: base - model, mae_reduction_percent: (100 * (base - model)) / base,
  model_wape_percent: 0, baseline_wape_percent: 0,
})

describe('gainWords', () => {
  it('a lower error is reported as lower, by how much', () => {
    expect(gainWords(G(345.47, 360.36))).toEqual({ pct: expect.closeTo(4.13, 2), direction: 'lower' })
  })
  it('a loss is reported as a loss (higher error), never hidden', () => {
    expect(gainWords(G(400, 360))?.direction).toBe('higher')
  })
  it('a missing gain is null, never 0', () => {
    expect(gainWords(null)).toBeNull()
  })
})

describe('scoredShare', () => {
  it('is scored / (scored + withheld), and null with no rows', () => {
    expect(scoredShare(6560, 304)).toBeCloseTo(0.9557, 4)
    expect(scoredShare(0, 0)).toBeNull()
  })
})

describe('sameRows', () => {
  const M = (v: number, t: number | null) => ({ validation: { scored_rows: v }, test: t == null ? null : { scored_rows: t } })
  it('gives the shared counts when every method was scored on the same rows', () => {
    expect(sameRows([M(6560, 6542), M(6560, 6542)])).toEqual({ validation: 6560, test: 6542 })
  })
  it('is null as soon as one method differs, so the page never claims it', () => {
    expect(sameRows([M(6560, 6542), M(6559, 6542)])).toBeNull()
    expect(sameRows([M(6560, 6542), M(6560, null)])).toBeNull()
  })
})

describe('topAndRest', () => {
  it('splits after n, keeping order', () => {
    expect(topAndRest([5, 4, 3, 2, 1], 3)).toEqual({ top: [5, 4, 3], rest: [2, 1] })
    expect(topAndRest([1], 3)).toEqual({ top: [1], rest: [] })
  })
})

describe('networkSentence', () => {
  const f = (x: number) => x.toFixed(1)
  const sel = { label: 'Random forest, ride history', mae: 345.47 }
  const base = { label: '4-week average', mae: 360.36 }
  it('GRU (364.9) beat neither the random forest (345.5) nor the 4-week average (360.4)', () => {
    expect(networkSentence({ label: 'Neural network (GRU, last 28 days)', mae: 364.86 }, sel, base, f)).toBe(
      'The best, neural network (GRU, last 28 days), beat neither the serving method nor the best simple rule: its validation ' +
      'error was 364.9, against 345.5 for the random forest (ride history) and 360.4 for the 4-week average.')
  })
  it('the words follow the numbers in every case', () => {
    expect(networkSentence({ label: 'Net', mae: 350 }, sel, base, f)).toContain('beat the 4-week average but not the random forest')
    expect(networkSentence({ label: 'Net', mae: 300 }, sel, base, f)).toContain('beat both')
  })
})

describe('inSentence', () => {
  it('reads labels naturally inside a sentence', () => {
    expect(inSentence('Random forest, ride history')).toBe('random forest (ride history)')
    expect(inSentence('Neural network (GRU, last 28 days)')).toBe('neural network (GRU, last 28 days)')
  })
})
