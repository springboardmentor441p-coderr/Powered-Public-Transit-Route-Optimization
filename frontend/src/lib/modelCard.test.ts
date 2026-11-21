import { describe, expect, it } from 'vitest'
import type { Gain } from '../api/types'
import { gainWords, scoredShare } from './modelCard'

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
