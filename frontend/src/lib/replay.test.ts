import { describe, expect, it } from 'vitest'
import type { RunningPoint } from '../api/types'
import { daysModelBetter, replayHeadline, replayProgress, runningComparison } from './replay'

const P = (date: string, rows: number, m: number, b: number, dm = m, db = b): RunningPoint => ({
  date, rows_scored: rows, day_rows_scored: rows, day_model_mae: dm, day_baseline_mae: db, model_mae: m, baseline_mae: b,
  model_wape_percent: 0, baseline_wape_percent: 0,
})

describe('replayHeadline', () => {
  it('names the replay day and the last revealed day', () => {
    expect(replayHeadline({ complete: false, virtual_date: '2026-06-05', revealed_through: '2026-06-04' }))
      .toBe('Replay day: 5 Jun 2026 · data revealed to 4 Jun 2026')
  })
  it('says complete at the end instead of a day past the supported range', () => {
    expect(replayHeadline({ complete: true, virtual_date: null, revealed_through: '2026-07-31' }))
      .toBe('Replay complete · data revealed to 31 Jul 2026')
  })
})

describe('runningComparison', () => {
  it('is null before anything is scored (never 0)', () => {
    expect(runningComparison([])).toBeNull()
  })
  it('words follow the sign: lower error is "lower", a loss is "higher"', () => {
    expect(runningComparison([P('2026-07-31', 6542, 398.0, 421.2)])).toMatchObject({ direction: 'lower', rows: 6542 })
    expect(runningComparison([P('2026-06-03', 300, 450, 400)])?.direction).toBe('higher')
    expect(runningComparison([P('2026-07-31', 6542, 398.0, 421.2)])!.pct).toBeCloseTo(5.51, 2)
  })
})

describe('daysModelBetter and replayProgress', () => {
  it('counts days by their own-day error', () => {
    expect(daysModelBetter([P('a', 1, 0, 0, 10, 20), P('b', 2, 0, 0, 30, 20)])).toEqual({ better: 1, days: 2 })
  })
  it('progress stays within 0..1', () => {
    expect(replayProgress({ days_revealed: 7, days_total: 61 })).toBeCloseTo(7 / 61)
    expect(replayProgress({ days_revealed: 70, days_total: 61 })).toBe(1)
  })
})
