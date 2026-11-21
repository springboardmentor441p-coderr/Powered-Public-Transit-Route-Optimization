// One natural order for route numbers, used everywhere a list of routes appears.
//   numeric routes first, by number, then suffix:   1, 2, 3 ... 8, 8A, 9, 12, 53, 53A, 53AL, 100, 1001
//   then letter-prefixed routes, by prefix, then number, then suffix:   J14, N5, N201, R22, X4, X9, X49
//   anything else last, alphabetically. Distinct names never tie, so the order is stable.
const NUMERIC = /^(\d+)([A-Za-z]*)$/
const PREFIXED = /^([A-Za-z]+)(\d+)([A-Za-z]*)$/

type Key = [group: number, prefix: string, num: number, suffix: string, raw: string]

function key(route: string): Key {
  const r = route.trim()
  let m = NUMERIC.exec(r)
  if (m) return [0, '', Number(m[1]), m[2]!.toUpperCase(), r]
  m = PREFIXED.exec(r)
  if (m) return [1, m[1]!.toUpperCase(), Number(m[2]), m[3]!.toUpperCase(), r]
  return [2, r.toUpperCase(), 0, '', r]
}

export function compareRoutes(a: string, b: string): number {
  const x = key(a), y = key(b)
  return x[0] - y[0] || x[1].localeCompare(y[1]) || x[2] - y[2] || x[3].localeCompare(y[3]) || x[4].localeCompare(y[4])
}

/** A sorted copy of route names. */
export const sortRoutes = (routes: readonly string[]) => [...routes].sort(compareRoutes)

/** A sorted copy of objects by their route name. */
export const sortByRoute = <T,>(items: readonly T[], route: (t: T) => string) => [...items].sort((a, b) => compareRoutes(route(a), route(b)))
