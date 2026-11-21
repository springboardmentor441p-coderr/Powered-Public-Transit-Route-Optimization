// Line patterns that tell routes apart on a map when their colour (= their group) is the same.
// Colour keeps meaning the group; the pattern only says which route a line is, and a key names each one.

/** Distinct SVG dash patterns, first solid, then dashed: enough for Compare's 8 routes. */
export const ROUTE_DASHES: (string | null)[] = [null, '10 7', '2 6', '14 5 3 5', '5 3', '18 6', '1 4', '8 4 2 4 2 4']

/** route -> dash pattern (null = solid), in the order given: first route solid, second dashed, and so on. */
export function routeDashes(routes: readonly string[]): Record<string, string | null> {
  return Object.fromEntries(routes.map((r, i) => [r, ROUTE_DASHES[i % ROUTE_DASHES.length] ?? null]))
}
