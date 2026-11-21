// Shared stops helpers: they only arrange the /api/rankings?metric=route_overlap_review rows (CLAUDE.md).
import type { OverlapRow } from '../api/types'
import { compareRoutes } from './routeSort'

export type OverlapMeasure = 'jaccard' | 'smaller'
export const measureOf = (r: OverlapRow, m: OverlapMeasure) => (m === 'jaccard' ? r.jaccard_stop_overlap : r.smaller_route_stop_overlap)
export const pairKey = (r: Pick<OverlapRow, 'route_a' | 'route_b'>) => `${r.route_a}|${r.route_b}`

/** Pairs ordered by one measure; ties broken by the other measure, then by route names, so the order is stable. */
export function sortPairs(rows: OverlapRow[], by: OverlapMeasure, lowestFirst: boolean): OverlapRow[] {
  const other: OverlapMeasure = by === 'jaccard' ? 'smaller' : 'jaccard'
  const sign = lowestFirst ? 1 : -1
  return [...rows].sort((a, b) => sign * (measureOf(a, by) - measureOf(b, by)) || sign * (measureOf(a, other) - measureOf(b, other))
    || compareRoutes(a.route_a, b.route_a) || compareRoutes(a.route_b, b.route_b))
}

/** How many of the top n pairs by Jaccard are also in the top n by the smaller-route share (n never above the count). */
export function topAgreement(rows: OverlapRow[], n: number): { n: number; both: number } | null {
  const used = Math.min(n, rows.length)
  if (used === 0) return null
  const top = (m: OverlapMeasure) => new Set(sortPairs(rows, m, false).slice(0, used).map(pairKey))
  const j = top('jaccard'), s = top('smaller')
  return { n: used, both: [...j].filter(k => s.has(k)).length }
}

/** Pairs where every stop of the smaller route is shared (one route's stops lie inside the other's). */
export const fullyInside = (rows: OverlapRow[]) => rows.filter(r => r.smaller_route_stop_overlap >= 1).length

/** Pairs involving a route (either side); all pairs when route is empty. */
export const involving = (rows: OverlapRow[], route: string) => (route ? rows.filter(r => r.route_a === route || r.route_b === route) : rows)
