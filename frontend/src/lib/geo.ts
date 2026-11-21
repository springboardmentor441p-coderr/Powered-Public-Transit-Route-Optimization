import type { RouteLine } from '../api/types'

/** [[south, west], [north, east]] around every point of every line. GeoJSON is [lon, lat]; Leaflet wants
 *  [lat, lon]. null when there are no points (the caller shows the "no lines" reason instead of a map). */
export function linesBounds(lines: Pick<RouteLine, 'line_geojson'>[]): [[number, number], [number, number]] | null {
  let s = 90, w = 180, n = -90, e = -180
  for (const l of lines) for (const [lon, lat] of l.line_geojson.coordinates) {
    s = Math.min(s, lat); n = Math.max(n, lat); w = Math.min(w, lon); e = Math.max(e, lon)
  }
  return n < s ? null : [[s, w], [n, e]]
}
