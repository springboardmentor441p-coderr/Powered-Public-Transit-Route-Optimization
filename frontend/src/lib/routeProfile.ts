// One route helpers: they only arrange what /api/routes/{route}/history sent (CLAUDE.md, UI design principles).
import type { DayType, HistoryDay, HistoryResponse } from '../api/types'

export type DaytypeMean = { daytype: DayType; days: number; mean: number | null }

/** Average recorded rides per day type over the days WITH a record (a day without one is left out, never 0). */
export function daytypeMeans(days: HistoryDay[]): Record<DayType, DaytypeMean> {
  const acc: Record<DayType, { n: number; sum: number }> = { W: { n: 0, sum: 0 }, A: { n: 0, sum: 0 }, U: { n: 0, sum: 0 } }
  for (const d of days) if (d.daytype && d.rides != null) { acc[d.daytype].n++; acc[d.daytype].sum += d.rides }
  const out = {} as Record<DayType, DaytypeMean>
  for (const k of ['W', 'A', 'U'] as DayType[]) out[k] = { daytype: k, days: acc[k].n, mean: acc[k].n ? acc[k].sum / acc[k].n : null }
  return out
}

/** A day type's average as a share of an average weekday; null when either side has no recorded day. */
export function shareOfWeekday(m: Record<DayType, DaytypeMean>, d: DayType): number | null {
  const w = m.W.mean, x = m[d].mean
  return w == null || x == null || w <= 0 ? null : x / w
}

/** Scheduled days with a ridership record, out of all scheduled days, from the history summary. */
export function recordCoverage(summary: HistoryResponse['summary']): { recorded: number; scheduled: number } {
  const matched = summary.matched ?? 0
  return { recorded: matched, scheduled: matched + (summary.schedule_without_ridership ?? 0) }
}
