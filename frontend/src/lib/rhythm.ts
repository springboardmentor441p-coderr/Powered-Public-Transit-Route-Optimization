// Weekday-rhythm grid: one column per week (Monday start), one row per weekday (Mon..Sun).
// A missing day stays missing (kind "missing", with its reason); a recorded 0 is a value (kind "zero").

export type DayIn = { date: string; rides: number | null; reason?: string | null }
export type Cell =
  | { kind: 'value'; date: string; rides: number; step: number }
  | { kind: 'zero'; date: string; rides: 0; step: 0 }
  | { kind: 'missing'; date: string; reason: string }
  | { kind: 'outside' }

export const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'] as const
const DAY_MS = 86_400_000

const utc = (iso: string) => Date.parse(`${iso}T00:00:00Z`)
/** 0 = Monday ... 6 = Sunday */
export const weekdayIndex = (iso: string) => (new Date(utc(iso)).getUTCDay() + 6) % 7

/** Bucket a value into `steps` equal bins between lo and hi (inclusive). */
function bin(v: number, lo: number, hi: number, steps: number): number {
  if (hi <= lo) return steps - 1
  return Math.min(steps - 1, Math.floor(((v - lo) / (hi - lo)) * steps))
}

/** Build the grid. Returns weeks[w][d] (d = weekday index) plus the week start dates and the value range. */
export function buildRhythm(days: DayIn[], steps = 5) {
  if (days.length === 0) return { weeks: [] as Cell[][], weekStarts: [] as string[], lo: null, hi: null }
  const sorted = [...days].sort((a, b) => a.date.localeCompare(b.date))
  const first = sorted[0]!.date
  const firstMonday = utc(first) - weekdayIndex(first) * DAY_MS
  const values = sorted.flatMap(d => (d.rides != null && d.rides > 0 ? [d.rides] : []))
  const lo = values.length ? Math.min(...values) : null
  const hi = values.length ? Math.max(...values) : null

  const weeks: Cell[][] = []
  const weekStarts: string[] = []
  for (const d of sorted) {
    const w = Math.floor((utc(d.date) - firstMonday) / (7 * DAY_MS))
    while (weeks.length <= w) {
      weekStarts.push(new Date(firstMonday + weeks.length * 7 * DAY_MS).toISOString().slice(0, 10))
      weeks.push(Array.from({ length: 7 }, (): Cell => ({ kind: 'outside' })))
    }
    const col = weeks[w]!
    col[weekdayIndex(d.date)] =
      d.rides == null ? { kind: 'missing', date: d.date, reason: d.reason ?? 'no record' }
        : d.rides === 0 ? { kind: 'zero', date: d.date, rides: 0, step: 0 }
          : { kind: 'value', date: d.date, rides: d.rides, step: bin(d.rides, lo!, hi!, steps) }
  }
  return { weeks, weekStarts, lo, hi }
}
