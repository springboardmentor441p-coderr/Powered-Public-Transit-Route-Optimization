// The same colours as index.css, for libraries that need a hex value (Leaflet, Recharts).
// Keep the two in step: one colour per route group, used identically on every screen and map.
export const INK = '#1C232B'
export const INK_2 = '#4E5762'
export const RULE = '#D9DDE2'
export const PANEL = '#FFFFFF'

/** Brand slate, chosen 2026-11-21 from three measured shades: white text 12.6:1, menu text #C9D1DA 8.2:1. */
export const BRAND = '#2B3440'

export const GROUP_COLOURS: Record<string, string> = { '0': '#0072B2', '1': '#D55E00' }
export const UNGROUPED = '#8B9099'

/** Group colour for a group id; null/undefined (ungrouped or outside the population) is the neutral grey. */
export function groupColour(groupId: number | null | undefined): string {
  return groupId == null ? UNGROUPED : (GROUP_COLOURS[String(groupId)] ?? UNGROUPED)
}

/** Ungrouped lines are dashed, so identity never depends on colour alone. */
export function groupDash(groupId: number | null | undefined): string | undefined {
  return groupId == null ? '6 5' : undefined
}

/** Magnitude ramp for the rhythm grid: one slate hue, light -> dark (lightness strictly decreasing).
 *  Deliberately not a group colour: blue and orange mean "group" and nothing else. */
export const SLATE_RAMP = ['#E4E8ED', '#C3CBD5', '#98A4B3', '#67768A', '#3A4757'] as const
