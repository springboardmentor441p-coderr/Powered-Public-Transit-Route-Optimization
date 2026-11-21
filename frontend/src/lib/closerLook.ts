// Closer look helpers. They only arrange what /api/rankings sent: no number, route or conclusion of their own
// (CLAUDE.md, UI design principles).
import type { RankingMetric, RankingRow } from '../api/types'
import { compareRoutes } from './routeSort'

export const METRIC_ORDER: RankingMetric[] = ['observed_daily_demand', 'rides_per_scheduled_trip', 'rides_per_scheduled_hour']
export const DIGITS: Record<RankingMetric, number> = {
  observed_daily_demand: 0, rides_per_scheduled_trip: 1, rides_per_scheduled_hour: 1,
}

/** A reason without its trailing per-route count: "fewer than 20 observed days (7)" -> "fewer than 20 observed days". */
export const reasonKind = (reason: string | null) => (reason ?? 'no reason given').replace(/\s*\(\d+\)\s*$/, '')

/** "Why unranked": the unranked rows counted by reason, most common first (ties alphabetical). */
export function unrankedSummary(rows: RankingRow[]): { total: number; parts: { reason: string; count: number }[] } {
  const counts = new Map<string, number>()
  for (const r of rows) if (r.rank == null) counts.set(reasonKind(r.reason), (counts.get(reasonKind(r.reason)) ?? 0) + 1)
  const parts = [...counts].map(([reason, count]) => ({ reason, count }))
    .sort((a, b) => b.count - a.count || a.reason.localeCompare(b.reason))
  return { total: parts.reduce((s, p) => s + p.count, 0), parts }
}

/** Ranked rows in the chosen order. Highest first = rank 1 first (the API ranks the highest value 1); lowest first
 *  reverses it. Ties keep the route order, so equal ranks never swap places between renders. */
export function orderRanked<T extends { rank: number | null; route: string }>(rows: T[], lowestFirst: boolean): T[] {
  const ranked = rows.filter(r => r.rank != null)
  return ranked.sort((a, b) => (lowestFirst ? b.rank! - a.rank! : a.rank! - b.rank!) || compareRoutes(a.route, b.route))
}

/** How many routes are in the top n of both rankings (rank <= n, ties included), and the n actually used:
 *  never more than the smaller count of ranked routes. */
export function topOverlap(a: RankingRow[], b: RankingRow[], n: number): { n: number; both: number } | null {
  const ra = a.filter(r => r.rank != null), rb = b.filter(r => r.rank != null)
  const used = Math.min(n, ra.length, rb.length)
  if (used === 0) return null
  const top = (rows: RankingRow[]) => new Set(rows.filter(r => r.rank! <= used).map(r => r.route))
  const ta = top(ra), tb = top(rb)
  return { n: used, both: [...ta].filter(r => tb.has(r)).length }
}

/** Ranks compared between the development period and the full window, over routes ranked in both. */
export function rankMovement(dev: RankingRow[], full: RankingRow[]): { compared: number; same: number; within3: number } {
  const devRank = new Map(dev.filter(r => r.rank != null).map(r => [r.route, r.rank!]))
  let compared = 0, same = 0, within3 = 0
  for (const r of full) {
    const d = devRank.get(r.route)
    if (r.rank == null || d == null) continue
    compared++
    if (d === r.rank) same++
    if (Math.abs(d - r.rank) <= 3) within3++
  }
  return { compared, same, within3 }
}

/** The minimum-days field: a whole number of 1 or more, or null (with the field left as typed). */
export function parseMinDays(text: string): number | null {
  if (!/^\s*\d+\s*$/.test(text)) return null
  const n = Number(text)
  return Number.isSafeInteger(n) && n >= 1 ? n : null
}

/** The gate the minimum-days box shows: the one the API applied (its configuration), so the box can never
 *  disagree with the ranking under it. Before the first answer: the requested value, else the API's reference. */
export function displayedGate(applied: number | undefined, requested: number | null, reference: number | undefined): number | undefined {
  return applied ?? requested ?? reference
}

/** "Higher value = more recorded rides for each scheduled trip-hour": the table subtitle in plain words, built from
 *  the API's numerator and denominator labels (plural denominator made singular). */
export function higherMeans(numeratorLabel: string, denominatorLabel: string): string {
  const one = denominatorLabel.replace(/s$/, '')
  return `Higher value = more ${numeratorLabel} for each ${one}.`
}
