// Compare helpers: they only arrange /api/routes/compare (CLAUDE.md, UI design principles).
import type { Archive, CompareRoute, RankingMetric } from '../api/types'
import { sortRoutes } from './routeSort'

export const MIN_ROUTES = 2
export const MAX_ROUTES = 8

/** "49,X49,,49, 10" -> ["10", "49", "X49"]: trimmed, no blanks, no repeats, at most MAX_ROUTES (the first ones
 *  given are kept), in natural route order, so the chips and table columns read 10, 49, X49. */
export function parseRoutes(param: string | null): string[] {
  const out: string[] = []
  for (const r of (param ?? '').split(',').map(x => x.trim())) if (r && !out.includes(r)) out.push(r)
  return sortRoutes(out.slice(0, MAX_ROUTES))
}

/** The route(s) with the highest value on a measure; routes without a value are left out, never counted as 0.
 *  Returns null when no route has a value. Ties return every tied route. */
export function leaders(routes: CompareRoute[], metric: RankingMetric): { routes: string[]; value: number } | null {
  const vals = routes.flatMap(r => {
    const v = r.indicators?.[metric]?.value
    return v == null ? [] : [{ route: r.route, v }]
  })
  if (!vals.length) return null
  const top = Math.max(...vals.map(x => x.v))
  return { routes: vals.filter(x => x.v === top).map(x => x.route), value: top }
}

/** The dates a timetable (geometry version) applied, from /api/data/coverage; null when it is not listed. */
export function archiveRange(archives: Archive[], version: string | null): { start: string; end: string } | null {
  const a = version == null ? undefined : archives.find(x => x.geometry_version === version)
  return a ? { start: a.applied_start, end: a.applied_end } : null
}
