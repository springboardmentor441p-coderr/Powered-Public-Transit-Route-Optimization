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

/** The row count every method was scored on, per period, or null when the methods differ (then say nothing). */
export function sameRows(methods: { validation: { scored_rows: number }; test: { scored_rows: number } | null }[]):
    { validation: number; test: number | null } | null {
  if (!methods.length) return null
  const v = new Set(methods.map(m => m.validation.scored_rows))
  const t = new Set(methods.map(m => m.test?.scored_rows ?? -1))
  if (v.size !== 1 || t.size !== 1) return null
  const tv = [...t][0]!
  return { validation: [...v][0]!, test: tv < 0 ? null : tv }
}

/** The first n items, and how many more there are (shown behind a "+ N other ..." toggle). */
export function topAndRest<T>(items: readonly T[], n: number): { top: T[]; rest: T[] } {
  return { top: items.slice(0, n), rest: items.slice(n) }
}

/** A method label as it reads inside a sentence: "Random forest, ride history" -> "random forest (ride history)";
 *  "Neural network (GRU, last 28 days)" -> "neural network (GRU, last 28 days)" (only the first letter is lowered). */
export function inSentence(label: string): string {
  const s = label.charAt(0).toLowerCase() + label.slice(1)
  return !s.includes('(') && s.includes(', ') ? s.replace(', ', ' (') + ')' : s
}

/** How the best neural network did against the serving method and the best simple rule, from validation errors.
 *  The words follow the numbers: lower error = "beat". */
export function networkSentence(net: { label: string; mae: number }, sel: { label: string; mae: number },
                                base: { label: string; mae: number }, fmt1: (x: number) => string): string {
  const n = inSentence(net.label), s = inSentence(sel.label), b = inSentence(base.label)
  const bs = net.mae < sel.mae, bb = net.mae < base.mae
  const vs = `its validation error was ${fmt1(net.mae)}, against ${fmt1(sel.mae)} for the ${s} and ${fmt1(base.mae)} for the ${b}`
  if (!bs && !bb) return `The best, ${n}, beat neither the serving method nor the best simple rule: ${vs}.`
  if (bs && bb) return `The best, ${n}, beat both the serving method and the best simple rule: ${vs}.`
  return `The best, ${n}, beat the ${bb ? b : s} but not the ${bb ? s : b}: ${vs}.`
}
