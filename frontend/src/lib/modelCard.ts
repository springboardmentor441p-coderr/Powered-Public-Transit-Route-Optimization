// Model card helpers: they only arrange /api/models/summary (CLAUDE.md, UI design principles).
import type { Gain } from '../api/types'

/** The gain sentence's words follow the sign of the API's number: lower error is "lower", higher is "higher". */
export function gainWords(g: Gain | null): { pct: number; direction: 'lower' | 'higher' | 'equal' } | null {
  if (g == null || !Number.isFinite(g.mae_reduction_percent)) return null
  const p = g.mae_reduction_percent
  return { pct: Math.abs(p), direction: p > 0 ? 'lower' : p < 0 ? 'higher' : 'equal' }
}

/** Share of rows that were scored, as a 0-1 number from scored and withheld counts (null when there are none). */
export function scoredShare(scored: number, withheld: number): number | null {
  const n = scored + withheld
  return n > 0 ? scored / n : null
}
