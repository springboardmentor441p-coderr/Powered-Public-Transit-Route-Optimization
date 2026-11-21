// Insight sentences are computed from API values at render time (CLAUDE.md, UI design principles): these helpers
// only arrange what the API sent. Nothing here holds a number, a route or a conclusion of its own.
import type { Coverage, TrendSummary } from '../api/types'

export type DaytypeLevel = {
  daytype: TrendSummary['daytype']; label: string; days: number
  mean: number | null; total: number | null          // total = mean x days: the numerator of the mean
  shareOfWeekday: number | null; reason: string | null
}

/** Each day type's average network rides/day and, for Saturday and Sunday/holiday, its share of an average
 *  weekday. A share is null (with a reason) when either average is missing; it is never 0 by default. */
export function daytypeLevels(summary: TrendSummary[]): DaytypeLevel[] {
  const weekday = summary.find(s => s.daytype === 'W')
  return summary.map(s => {
    const hasBoth = s.mean_rides != null && weekday?.mean_rides != null && weekday.mean_rides > 0
    return {
      daytype: s.daytype, label: s.daytype_label, days: s.days, mean: s.mean_rides,
      total: s.mean_rides == null ? null : s.mean_rides * s.days,
      shareOfWeekday: s.daytype === 'W' ? null : hasBoth ? s.mean_rides! / weekday!.mean_rides! : null,
      reason: s.daytype === 'W' ? s.reason
        : s.mean_rides == null ? s.reason
        : hasBoth ? null : 'no weekday with a record in this range',
    }
  })
}

/** Import checks: how many of the identities checked at import hold (0 violations), out of how many. */
export function importChecks(q: Coverage['quality']): { held: number; total: number } {
  const counts = Object.values(q.import_identities)
  return { held: counts.filter(n => n === 0).length, total: counts.length }
}
