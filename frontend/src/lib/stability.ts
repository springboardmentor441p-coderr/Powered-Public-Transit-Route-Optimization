// Rank stability: the same ranking over the development period and the full matched window, side by side.
// Deliberately no "stable/unstable" verdict: the spec defines no threshold, so we show the movement itself.

export function ordinal(n: number): string {
  const s = n % 100 >= 11 && n % 100 <= 13 ? 'th' : ['th', 'st', 'nd', 'rd'][n % 10] ?? 'th'
  return `${n}${s}`
}

export type Stability =
  | { kind: 'same'; text: string }
  | { kind: 'moved'; text: string; places: number; direction: 'up' | 'down' }
  | { kind: 'not_comparable'; text: string }

export function stability(dev: { rank: number | null; reason?: string | null },
                          full: { rank: number | null; reason?: string | null }): Stability {
  if (dev.rank == null) return { kind: 'not_comparable', text: `not comparable – unranked in development (${dev.reason ?? 'no reason given'})` }
  if (full.rank == null) return { kind: 'not_comparable', text: `not comparable – unranked in the full window (${full.reason ?? 'no reason given'})` }
  const head = `Development ${ordinal(dev.rank)} → full window ${ordinal(full.rank)}`
  if (dev.rank === full.rank) return { kind: 'same', text: `${head} (same place)` }
  const places = Math.abs(full.rank - dev.rank)
  return { kind: 'moved', text: `${head} (moved ${places} place${places === 1 ? '' : 's'} ${full.rank < dev.rank ? 'up' : 'down'})`, places, direction: full.rank < dev.rank ? 'up' : 'down' }
}
