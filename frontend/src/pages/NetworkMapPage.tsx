import { useCallback, useMemo, useState } from 'react'
import { CircleMarker, MapContainer, Popup, TileLayer } from 'react-leaflet'
import { MapPin, Search } from 'lucide-react'
import { DataNotice, EmptyState, ErrorState, LoadingState, PageTitle, Panel, formatNumber } from '../components/ui'
import { useResource } from '../hooks/useResource'
import { api } from '../services/api'
import type { StopItem } from '../types/api'

export function NetworkMapPage() {
  const [search, setSearch] = useState('')
  const [selected, setSelected] = useState<StopItem | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const loadStops = useCallback(() => api.allStops(), [])
  const { data, loading, error, reload } = useResource(loadStops)
  const loadRoutes = useCallback(() => selectedId ? api.routesAtStop(selectedId) : Promise.resolve([]), [selectedId])
  const routes = useResource(loadRoutes, [loadRoutes])

  const plottedStops = useMemo(() => (data ?? []).filter((stop) =>
    stop.stop_lat_value !== null && stop.stop_lon_value !== null &&
    (!search || `${stop.stop_id} ${stop.stop_name ?? ''}`.toLowerCase().includes(search.toLowerCase())),
  ), [data, search])

  return (
    <>
      <PageTitle eyebrow="Geography" title="Transit network map" description="Actual stop points from the supplied GTFS coordinates. Explore locations and the routes linked to each stop." />
      <div className="space-y-5">
        <DataNotice tone="amber"><strong>Geometry limitation:</strong> the feed does not include <code>shapes.txt</code>. The map shows stop points only; it does not connect stops or depict bus paths.</DataNotice>
        <Panel title="Chennai MTC stop locations" subtitle={data ? `${formatNumber(plottedStops.length)} plotted stops with valid coordinates` : 'Loading GTFS stop coordinates.'} action={<label className="relative w-36 sm:w-64"><Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Find a stop" className="field pl-9" /></label>}>
          {loading && <LoadingState label="Loading stop coordinates…" />}{error && <ErrorState message={error} onRetry={reload} />}
          {!loading && !error && data && (plottedStops.length ? <div className="overflow-hidden rounded-xl border border-slate-200">
            <MapContainer center={[12.95, 80.2]} zoom={10} minZoom={8} maxZoom={18} scrollWheelZoom preferCanvas className="h-[62vh] min-h-[430px] w-full">
              <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
              {plottedStops.map((stop) => <CircleMarker key={stop.stop_id} center={[stop.stop_lat_value as number, stop.stop_lon_value as number]} radius={selected?.stop_id === stop.stop_id ? 7 : 4} pathOptions={{ color: selected?.stop_id === stop.stop_id ? '#0f766e' : '#3156b8', fillColor: selected?.stop_id === stop.stop_id ? '#2dd4bf' : '#7091ee', fillOpacity: 0.76, weight: 1 }} eventHandlers={{ click: () => { setSelected(stop); setSelectedId(stop.stop_id) } }}>
                <Popup><strong>{stop.stop_name || 'Unnamed stop'}</strong><br />Stop ID {stop.stop_id}<br />Routes serving: {stop.route_count ?? '—'}</Popup>
              </CircleMarker>)}
            </MapContainer>
          </div> : <EmptyState title="No coordinate-bearing stops" detail="The processed stop summary does not contain usable coordinates." />)}
        </Panel>
        {selected && <Panel title={selected.stop_name || 'Selected stop'} subtitle={`GTFS stop ${selected.stop_id} · ${selected.stop_lat_value}, ${selected.stop_lon_value}`}>
          <div className="mb-4 flex flex-wrap gap-3 text-xs text-slate-600"><span className="inline-flex items-center gap-1.5 rounded-lg bg-slate-50 px-3 py-2"><MapPin className="h-3.5 w-3.5 text-teal-700" />{formatNumber(selected.route_count)} routes serving</span><span className="rounded-lg bg-slate-50 px-3 py-2">{formatNumber(selected.trip_count)} scheduled stop-time references</span></div>
          {routes.loading && <LoadingState label="Loading serving routes…" />}{routes.error && <ErrorState message={routes.error} onRetry={routes.reload} />}
          {routes.data && (routes.data.length ? <div className="flex flex-wrap gap-2">{routes.data.map((route) => <span key={route.route_id} className="rounded-lg border border-slate-200 px-3 py-2 text-xs"><strong>{route.route_short_name || route.route_id}</strong><span className="ml-2 text-slate-500">{route.route_long_name}</span></span>)}</div> : <EmptyState title="No serving routes returned" />)}
        </Panel>}
      </div>
    </>
  )
}
