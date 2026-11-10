import { useState, useEffect, useMemo } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Polyline, useMap } from 'react-leaflet';
import L from 'leaflet';
import { Search, ChevronRight, MapPin, Clock } from 'lucide-react';
import { getRoutes, getRouteDetail, getRouteStops, getRouteSchedule } from '../services/api';
import { useApi } from '../hooks/useApi';
import { LoadingSpinner, ErrorAlert, PageHeader, Card, Badge } from '../components/ui';
import type { RouteDetail, RouteStop, ScheduleEntry } from '../types';
import 'leaflet/dist/leaflet.css';

// Fix default marker icons
delete (L.Icon.Default.prototype as unknown as Record<string, unknown>)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
});

function MapBounds({ stops }: { stops: RouteStop[] }) {
  const map = useMap();
  useEffect(() => {
    if (stops.length > 0) {
      const bounds = L.latLngBounds(stops.map(s => [s.stop_lat, s.stop_lon]));
      map.fitBounds(bounds, { padding: [30, 30] });
    }
  }, [stops, map]);
  return null;
}

export default function RouteExplorerPage() {
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [selectedRouteId, setSelectedRouteId] = useState<string | null>(null);
  const [routeDetail, setRouteDetail] = useState<RouteDetail | null>(null);
  const [routeStops, setRouteStops] = useState<RouteStop[]>([]);
  const [schedule, setSchedule] = useState<ScheduleEntry[]>([]);
  const [detailLoading, setDetailLoading] = useState(false);
  const { data: routes, loading, error, refetch: fetchRoutes } = useApi(() => getRoutes(page, 50, search), [page, search]);

  const selectRoute = async (routeId: string) => {
    setSelectedRouteId(routeId);
    setDetailLoading(true);
    try {
      const [detail, stops, sched] = await Promise.all([
        getRouteDetail(routeId),
        getRouteStops(routeId),
        getRouteSchedule(routeId),
      ]);
      setRouteDetail(detail);
      setRouteStops(stops);
      setSchedule(sched);
    } catch (e) {
      console.error(e);
    }
    setDetailLoading(false);
  };

  const polylinePositions = useMemo(() =>
    routeStops
      .sort((a, b) => a.stop_sequence - b.stop_sequence)
      .map(s => [s.stop_lat, s.stop_lon] as [number, number]),
  [routeStops]);

  const firstDeparture = useMemo(() => {
    if (schedule.length === 0) return null;
    const times = schedule.map(s => s.departure_time).filter(Boolean).sort();
    return times[0] || null;
  }, [schedule]);

  const lastDeparture = useMemo(() => {
    if (schedule.length === 0) return null;
    const times = schedule.map(s => s.departure_time).filter(Boolean).sort();
    return times[times.length - 1] || null;
  }, [schedule]);

  return (
    <div>
      <PageHeader title="Route Explorer" subtitle="Search and inspect Chennai MTC bus routes" />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Route list */}
        <div className="lg:col-span-1">
          <Card>
            <div className="relative mb-4">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              <input
                type="text"
                placeholder="Search by route name or number..."
                value={search}
                onChange={e => { setSearch(e.target.value); setPage(1); }}
                className="w-full pl-10 pr-4 py-2.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 dark:text-white"
              />
            </div>

            {loading ? (
              <LoadingSpinner text="Loading routes..." />
            ) : error ? (
              <ErrorAlert message={error} onRetry={fetchRoutes} />
            ) : routes ? (
              <>
                <div className="space-y-1 max-h-[500px] overflow-y-auto">
                  {routes.items.map(route => (
                    <button
                      key={route.route_id}
                      onClick={() => selectRoute(route.route_id)}
                      className={`w-full text-left px-3 py-2.5 rounded-lg text-sm transition-colors flex items-center justify-between ${
                        selectedRouteId === route.route_id
                          ? 'bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400'
                          : 'hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300'
                      }`}
                    >
                      <div>
                        <span className="font-semibold">{route.route_short_name}</span>
                        <span className="text-slate-500 dark:text-slate-400 ml-2 text-xs truncate">{route.route_long_name}</span>
                      </div>
                      <ChevronRight className="w-4 h-4 text-slate-400 flex-shrink-0" />
                    </button>
                  ))}
                </div>
                <div className="flex items-center justify-between mt-4 pt-3 border-t border-slate-200 dark:border-slate-700">
                  <span className="text-xs text-slate-500">{routes.total} routes total</span>
                  <div className="flex gap-2">
                    <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page <= 1} className="px-3 py-1 text-xs rounded bg-slate-100 dark:bg-slate-800 disabled:opacity-50">Prev</button>
                    <span className="text-xs text-slate-500 py-1">{page}/{routes.total_pages}</span>
                    <button onClick={() => setPage(p => Math.min(routes.total_pages, p + 1))} disabled={page >= routes.total_pages} className="px-3 py-1 text-xs rounded bg-slate-100 dark:bg-slate-800 disabled:opacity-50">Next</button>
                  </div>
                </div>
              </>
            ) : null}
          </Card>
        </div>

        {/* Detail */}
        <div className="lg:col-span-2 space-y-6">
          {detailLoading ? (
            <LoadingSpinner text="Loading route details..." />
          ) : routeDetail ? (
            <>
              {/* Route info */}
              <Card>
                <div className="flex flex-wrap items-start gap-4 mb-4">
                  <div className="bg-blue-600 text-white px-4 py-2 rounded-lg text-lg font-bold">{routeDetail.route_short_name}</div>
                  <div>
                    <h2 className="text-lg font-semibold text-slate-900 dark:text-white">{routeDetail.route_long_name}</h2>
                    <p className="text-sm text-slate-500">Route ID: {routeDetail.route_id}</p>
                  </div>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
                  <div className="bg-slate-50 dark:bg-slate-800 rounded-lg p-3">
                    <p className="text-slate-500 dark:text-slate-400">Trips</p>
                    <p className="text-lg font-bold text-slate-900 dark:text-white">{routeDetail.trip_count}</p>
                  </div>
                  <div className="bg-slate-50 dark:bg-slate-800 rounded-lg p-3">
                    <p className="text-slate-500 dark:text-slate-400">Stops</p>
                    <p className="text-lg font-bold text-slate-900 dark:text-white">{routeDetail.stop_count}</p>
                  </div>
                  <div className="bg-slate-50 dark:bg-slate-800 rounded-lg p-3">
                    <p className="text-slate-500 dark:text-slate-400">First Departure</p>
                    <p className="text-lg font-bold text-slate-900 dark:text-white">{firstDeparture || 'N/A'}</p>
                  </div>
                  <div className="bg-slate-50 dark:bg-slate-800 rounded-lg p-3">
                    <p className="text-slate-500 dark:text-slate-400">Last Departure</p>
                    <p className="text-lg font-bold text-slate-900 dark:text-white">{lastDeparture || 'N/A'}</p>
                  </div>
                </div>
                <div className="flex flex-wrap gap-2 mt-3">
                  {routeDetail.service_ids.map(sid => (
                    <Badge key={sid} color="green">{sid}</Badge>
                  ))}
                  {routeDetail.directions.map(d => (
                    <Badge key={d} color="blue">Direction {d}</Badge>
                  ))}
                </div>
              </Card>

              {/* Map */}
              {routeStops.length > 0 && (
                <Card title="Route Map (Stop-to-Stop Approximate Path)">
                  <div className="h-96 rounded-lg overflow-hidden">
                    <MapContainer center={[13.0827, 80.2707]} zoom={12} className="h-full w-full">
                      <TileLayer
                        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                      />
                      <MapBounds stops={routeStops} />
                      <Polyline positions={polylinePositions} color="#2563eb" weight={3} opacity={0.7} dashArray="8" />
                      {routeStops.map(stop => (
                        <Marker key={`${stop.stop_id}-${stop.stop_sequence}`} position={[stop.stop_lat, stop.stop_lon]}>
                          <Popup>
                            <div className="text-sm">
                              <strong>{stop.stop_name}</strong><br/>
                              Stop #{stop.stop_sequence}<br/>
                              ID: {stop.stop_id}
                            </div>
                          </Popup>
                        </Marker>
                      ))}
                    </MapContainer>
                  </div>
                  <p className="text-xs text-slate-400 mt-2 italic">
                    ⚠ Lines connect stops in sequence order and do not represent actual road paths. No GTFS shapes data is available.
                  </p>
                </Card>
              )}

              {/* Stop list */}
              <Card title="Stops">
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-slate-50 dark:bg-slate-800">
                      <tr>
                        <th className="text-left px-3 py-2 text-slate-600 dark:text-slate-400 font-medium">#</th>
                        <th className="text-left px-3 py-2 text-slate-600 dark:text-slate-400 font-medium">Stop Name</th>
                        <th className="text-left px-3 py-2 text-slate-600 dark:text-slate-400 font-medium">Stop ID</th>
                        <th className="text-left px-3 py-2 text-slate-600 dark:text-slate-400 font-medium">Location</th>
                      </tr>
                    </thead>
                    <tbody>
                      {routeStops.sort((a, b) => a.stop_sequence - b.stop_sequence).map(stop => (
                        <tr key={`${stop.stop_id}-${stop.stop_sequence}`} className="border-t border-slate-100 dark:border-slate-800">
                          <td className="px-3 py-2 text-slate-600 dark:text-slate-400">{stop.stop_sequence}</td>
                          <td className="px-3 py-2 font-medium text-slate-900 dark:text-white">{stop.stop_name}</td>
                          <td className="px-3 py-2 text-slate-500">{stop.stop_id}</td>
                          <td className="px-3 py-2 text-slate-500">{stop.stop_lat.toFixed(4)}, {stop.stop_lon.toFixed(4)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>

              {/* Schedule */}
              {schedule.length > 0 && (
                <Card title="Scheduled Departures (from first stop)">
                  <div className="overflow-x-auto max-h-72 overflow-y-auto">
                    <table className="w-full text-sm">
                      <thead className="bg-slate-50 dark:bg-slate-800 sticky top-0">
                        <tr>
                          <th className="text-left px-3 py-2 text-slate-600 dark:text-slate-400 font-medium">Trip ID</th>
                          <th className="text-left px-3 py-2 text-slate-600 dark:text-slate-400 font-medium">Departure</th>
                          <th className="text-left px-3 py-2 text-slate-600 dark:text-slate-400 font-medium">Direction</th>
                          <th className="text-left px-3 py-2 text-slate-600 dark:text-slate-400 font-medium">Service</th>
                        </tr>
                      </thead>
                      <tbody>
                        {schedule.slice(0, 100).map((entry, i) => (
                          <tr key={i} className="border-t border-slate-100 dark:border-slate-800">
                            <td className="px-3 py-2 text-slate-500">{entry.trip_id}</td>
                            <td className="px-3 py-2 font-medium text-slate-900 dark:text-white flex items-center gap-1">
                              <Clock className="w-3 h-3 text-slate-400" /> {entry.departure_time}
                            </td>
                            <td className="px-3 py-2"><Badge color="blue">Dir {entry.direction_id}</Badge></td>
                            <td className="px-3 py-2"><Badge color="green">{entry.service_id}</Badge></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    {schedule.length > 100 && (
                      <p className="text-xs text-slate-400 p-3">Showing first 100 of {schedule.length} departures</p>
                    )}
                  </div>
                </Card>
              )}
            </>
          ) : (
            <Card>
              <div className="text-center py-12 text-slate-500 dark:text-slate-400">
                <MapPin className="w-12 h-12 mx-auto mb-3 text-slate-300" />
                <p className="text-lg font-medium">Select a Route</p>
                <p className="text-sm">Choose a route from the list to view its details, map, and schedule</p>
              </div>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}

