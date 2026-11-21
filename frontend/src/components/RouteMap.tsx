import 'leaflet/dist/leaflet.css'
import { MapContainer, Polyline, TileLayer, Tooltip } from 'react-leaflet'
import type { MapLine, RouteLine } from '../api/types'
import { groupColour, groupDash } from '../design/tokens'
import { linesBounds } from '../lib/geo'

type Line = RouteLine & { group_id?: number | null; route_long_name?: string | null }

/** Route lines on greyed OpenStreetMap tiles. Colour = the route's group (dashed grey when ungrouped);
 *  `groupNames` labels the tooltip. The caption with the geometry version sits outside, under the map. */
export function RouteMap({ lines, groupNames = {}, height = 420, weight = 2 }: {
  lines: (Line | MapLine)[]; groupNames?: Record<number, string>; height?: number; weight?: number
}) {
  const bounds = linesBounds(lines)
  if (!bounds) return null
  return (
    <div style={{ height }}>
      <MapContainer bounds={bounds} scrollWheelZoom={false} className="h-full w-full">
        <TileLayer url="https://tile.openstreetmap.org/{z}/{x}/{y}.png" maxZoom={19}
                   attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' />
        {lines.map(l => {
          const g = l.group_id ?? null
          return (
            <Polyline key={`${l.route}-${l.direction_id}-${l.shape_id}`}
                      positions={l.line_geojson.coordinates.map(([lon, lat]) => [lat, lon] as [number, number])}
                      pathOptions={{ color: groupColour(g), weight, opacity: 0.85, dashArray: groupDash(g) }}>
              <Tooltip sticky>
                <strong>Route {l.route}</strong>{l.route_long_name ? ` ${l.route_long_name}` : ''} · {l.direction_label}
                <br />{g == null ? 'ungrouped' : (groupNames[g] ?? `Group ${g}`)}
                {l.tie_label && <><br />{l.tie_label}</>}
              </Tooltip>
            </Polyline>
          )
        })}
      </MapContainer>
    </div>
  )
}

/** Key for the group colours: every colour on a map is named. */
export function GroupLegend({ groups, showUngrouped = true }: {
  groups: { group_id: number; name: string; size?: number }[]; showUngrouped?: boolean
}) {
  return (
    <ul className="flex flex-wrap gap-x-5 gap-y-1 text-xs text-ink-2">
      {groups.map(g => (
        <li key={g.group_id} className="flex items-center gap-1.5">
          <svg width="22" height="6" aria-hidden><line x1="0" y1="3" x2="22" y2="3" stroke={groupColour(g.group_id)} strokeWidth="3" /></svg>
          <span><span className="font-semibold text-ink">Group {g.group_id}</span> · {g.name}{g.size != null && ` (${g.size} routes)`}</span>
        </li>
      ))}
      {showUngrouped && (
        <li className="flex items-center gap-1.5">
          <svg width="22" height="6" aria-hidden><line x1="0" y1="3" x2="22" y2="3" stroke={groupColour(null)} strokeWidth="3" strokeDasharray={groupDash(null)} /></svg>
          <span><span className="font-semibold text-ink">Ungrouped</span> (dashed)</span>
        </li>
      )}
    </ul>
  )
}
