// Points for the "Alike" scatter of two profile features. The rules (agreed for Stage 6c):
//  - a route with a missing value on either axis is LEFT OFF the scatter and listed in a note with its reason.
//    It is never drawn at 0 and never at the median the clustering filled in.
//  - a structural zero (no scheduled weekend service) is a known value: it is plotted at 0 and keeps its status,
//    so the tooltip can say "no scheduled Saturday service".
import type { RouteProfileValue, RouteValues } from '../api/types'

export type ScatterPoint = {
  route: string; groupId: number | null; x: number; y: number
  xStatus: RouteProfileValue['status']; yStatus: RouteProfileValue['status']
}
export type LeftOff = { route: string; groupId: number | null; note: string }

export function scatterPoints(routes: RouteValues[], xFeature: string, yFeature: string) {
  const plotted: ScatterPoint[] = []
  const leftOff: LeftOff[] = []
  for (const r of routes) {
    const x = r.values.find(v => v.feature === xFeature)
    const y = r.values.find(v => v.feature === yFeature)
    const missing = [x ?? { label: xFeature, value: null, reason: 'not in the profile' },
                     y ?? { label: yFeature, value: null, reason: 'not in the profile' }]
      .filter(v => v.value == null)
    if (x && y && x.value != null && y.value != null) {
      plotted.push({ route: r.route, groupId: r.group_id, x: x.value, y: y.value, xStatus: x.status, yStatus: y.status })
    } else {
      const why = missing.map(v => `${v.label.toLowerCase()}: ${v.reason ?? 'unavailable'}`).join('; ')
      leftOff.push({ route: r.route, groupId: r.group_id, note: `Route ${r.route} is not plotted (${why}).` })
    }
  }
  return { plotted, leftOff }
}

export type Range = { groupId: number; min: number; max: number }

/** Routes whose point lies inside ANOTHER group's [min, max] on both axes (ranges from the plotted points). */
export function insideOtherGroup(points: ScatterPoint[]): { inside: number; grouped: number } {
  const ids = [...new Set(points.map(p => p.groupId).filter((g): g is number => g != null))]
  const box = new Map(ids.map(g => {
    const own = points.filter(p => p.groupId === g)
    return [g, { x0: Math.min(...own.map(p => p.x)), x1: Math.max(...own.map(p => p.x)),
                 y0: Math.min(...own.map(p => p.y)), y1: Math.max(...own.map(p => p.y)) }]
  }))
  const grouped = points.filter(p => p.groupId != null)
  const inside = grouped.filter(p => ids.some(g => {
    const b = box.get(g)!
    return g !== p.groupId && p.x >= b.x0 && p.x <= b.x1 && p.y >= b.y0 && p.y <= b.y1
  })).length
  return { inside, grouped: grouped.length }
}
