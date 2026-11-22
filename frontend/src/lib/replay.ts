// Replay helpers: words built only from the API's replay state and review (CLAUDE.md, UI design principles).
import type { ReplayState, RunningPoint } from '../api/types'
import { fmtDate } from './dates'

/** "Replay day: 5 Jun 2026 · data revealed to 4 Jun 2026", or "Replay complete · data revealed to 31 Jul 2026". */
export function replayHeadline(s: Pick<ReplayState, 'complete' | 'virtual_date' | 'revealed_through'>): string {
  const revealed = `data revealed to ${fmtDate(s.revealed_through)}`
  return s.complete || s.virtual_date == null ? `Replay complete · ${revealed}` : `Replay day: ${fmtDate(s.virtual_date)} · ${revealed}`
}

/** How the model compares with the 4-week average so far: the latest running point, in words that follow the sign.
 *  null when nothing has been scored yet (the screen then says so; it never shows 0). */
export function runningComparison(points: RunningPoint[]): {
  model: number; baseline: number; pct: number; direction: 'lower' | 'higher' | 'equal'; rows: number; through: string
} | null {
  const last = points.at(-1)
  if (!last || last.rows_scored === 0 || !(last.baseline_mae > 0)) return null
  const diff = (last.baseline_mae - last.model_mae) / last.baseline_mae * 100
  return { model: last.model_mae, baseline: last.baseline_mae, pct: Math.abs(diff), rows: last.rows_scored, through: last.date,
           direction: diff > 0 ? 'lower' : diff < 0 ? 'higher' : 'equal' }
}

/** Days on which the model's own-day error beat the 4-week average's, out of the days scored. */
export function daysModelBetter(points: RunningPoint[]): { better: number; days: number } {
  return { better: points.filter(p => p.day_model_mae < p.day_baseline_mae).length, days: points.length }
}

/** Progress through the replay: days revealed of the total, never above the total. */
export function replayProgress(s: Pick<ReplayState, 'days_revealed' | 'days_total'>): number {
  return s.days_total > 0 ? Math.min(1, Math.max(0, s.days_revealed / s.days_total)) : 0
}
