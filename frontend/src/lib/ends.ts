// Both ends of a ranking, in neutral words: the routes with the HIGHEST and the LOWEST values on the chosen
// metric. Never "best"/"worst": a high or low value is a reason to look, not a verdict (spec 9.12 caveat).

export type RankedRow = { route: string; rank: number | null; value: number | null }

export const END_WORDS = { high: 'highest', low: 'lowest' } as const

/** Ranked rows only (unranked rows are counted, never placed at either end). Rank 1 = highest value.
 *  `low` lists the lowest value first. If fewer than 2n routes are ranked, the ends do not overlap. */
export function rankingEnds<T extends RankedRow>(rows: T[], n = 3) {
  const ranked = rows.filter(r => r.rank != null).sort((a, b) => a.rank! - b.rank! || a.route.localeCompare(b.route))
  const k = Math.min(n, Math.floor(ranked.length / 2))
  return {
    high: ranked.slice(0, k),
    low: ranked.slice(ranked.length - k).reverse(),
    ranked: ranked.length,
    unranked: rows.length - ranked.length,
  }
}
