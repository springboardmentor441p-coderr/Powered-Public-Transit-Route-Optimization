import { useState, useEffect } from 'react';
import { MapContainer, TileLayer, CircleMarker, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import { useApi } from '../hooks/useApi';
import { getCoverageSummary, getCoverageStops } from '../services/api';
import { LoadingSpinner, ErrorAlert, PageHeader, StatCard, Card, EmptyState } from '../components/ui';
import { MapPin, Navigation, Share2, AlertTriangle } from 'lucide-react';
import type { CoverageStop } from '../types';
import 'leaflet/dist/leaflet.css';

function CoverageMapContent({ stops }: { stops: CoverageStop[] }) {
  const map = useMap();
  useEffect(() => {
    if (stops.length > 0) {
      const bounds = L.latLngBounds(stops.map(s => [s.stop_lat, s.stop_lon]));
      map.fitBounds(bounds, { padding: [20, 20] });
    }
  }, [stops, map]);

  const getColor = (routeCount: number) => {
    if (routeCount >= 10) return '#dc2626';
    if (routeCount >= 5) return '#f59e0b';
    if (routeCount >= 2) return '#2563eb';
    return '#94a3b8';
  };

  return (
    <>
      {stops.map(stop => (
        <CircleMarker
          key={stop.stop_id}
          center={[stop.stop_lat, stop.stop_lon]}
          radius={Math.min(3 + stop.route_count, 12)}
          fillColor={getColor(stop.route_count)}
          fillOpacity={0.7}
          color={getColor(stop.route_count)}
          weight={1}
        >
          <Popup>
            <div className="text-sm">
              <strong>{stop.stop_name}</strong><br/>
              Routes: {stop.route_count}<br/>
              {stop.route_names.slice(0, 5).join(', ')}
              {stop.route_names.length > 5 && ` +${stop.route_names.length - 5} more`}
            </div>
          </Popup>
        </CircleMarker>
      ))}
    </>
  );
}

export default function CoveragePage() {
  const { data: summary, loading: sLoad, error: sErr, refetch: sRefetch } = useApi(getCoverageSummary);
  const [mapStops, setMapStops] = useState<CoverageStop[]>([]);
  const [minRoutes, setMinRoutes] = useState(1);
  const [mapLoading, setMapLoading] = useState(false);
  const [mapError, setMapError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      setMapLoading(true);
      try {
        // The API caps page_size at 500; map the highest-coverage page and label it accordingly.
        const res = await getCoverageStops(1, 500, minRoutes >= 5);
        setMapStops(res.items.filter(stop => stop.route_count >= minRoutes));
        setMapError(null);
      } catch (e) {
        setMapError(e instanceof Error ? e.message : 'Failed to load coverage stops');
      }
      setMapLoading(false);
    }
    load();
  }, [minRoutes]);

  if (sLoad) return <LoadingSpinner text="Loading coverage data..." />;
  if (sErr) return <ErrorAlert message={sErr} onRetry={sRefetch} />;
  if (!summary) return null;

  return (
    <div>
      <PageHeader title="Route Coverage Analysis" subtitle="Analyse geographical stop coverage across the MTC network" />

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <StatCard title="Total Stops" value={summary.total_stops} icon={MapPin} color="blue" />
        <StatCard title="Single-Route Stops" value={summary.stops_single_route} icon={Navigation} color="amber" subtitle="Served by only one route" />
        <StatCard title="Multi-Route Stops" value={summary.stops_multi_route} icon={Share2} color="green" subtitle="Served by 2+ routes" />
        <StatCard title="Max Routes/Stop" value={summary.max_routes_per_stop} icon={AlertTriangle} color="purple" subtitle={`Avg: ${summary.avg_routes_per_stop.toFixed(1)}`} />
      </div>

      {/* Map */}
      <Card title="Stop Coverage Map">
        <div className="flex items-center gap-4 mb-4">
          <label className="text-sm text-slate-600 dark:text-slate-400">Minimum routes per stop (map shows up to 500 highest-coverage results):</label>
          <select
            value={minRoutes}
            onChange={e => setMinRoutes(Number(e.target.value))}
            className="rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm px-3 py-1.5 dark:text-white"
          >
            <option value={1}>1+ (all stops)</option>
            <option value={2}>2+ routes</option>
            <option value={5}>5+ routes</option>
            <option value={10}>10+ routes</option>
          </select>
          <div className="flex items-center gap-3 text-xs ml-auto">
            <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-full bg-slate-400 inline-block" /> 1 route</span>
            <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-full bg-blue-600 inline-block" /> 2-4</span>
            <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-full bg-amber-500 inline-block" /> 5-9</span>
            <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-full bg-red-600 inline-block" /> 10+</span>
          </div>
        </div>
        <div className="h-[500px] rounded-lg overflow-hidden">
          {mapLoading ? (
            <LoadingSpinner text="Loading stops..." />
          ) : mapError ? (
            <ErrorAlert message={mapError} />
          ) : mapStops.length === 0 ? (
            <EmptyState title="No stops match this filter" description="Try a lower minimum route count." />
          ) : (
            <MapContainer key={minRoutes} center={[13.0827, 80.2707]} zoom={11} className="h-full w-full">
              <TileLayer
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              />
              <CoverageMapContent stops={mapStops} />
            </MapContainer>
          )}
        </div>
        <p className="text-xs text-slate-400 mt-2 italic">
          Coverage analysis is based on GTFS stop data. Areas without stops may still have bus service not captured in this dataset.
        </p>
      </Card>

      {/* Top shared stops */}
      <Card title="Most Connected Stops (Highest Number of Routes)" className="mt-6">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 dark:bg-slate-800">
              <tr>
                <th className="text-left px-3 py-2 text-slate-600 dark:text-slate-400 font-medium">Stop Name</th>
                <th className="text-left px-3 py-2 text-slate-600 dark:text-slate-400 font-medium">Stop ID</th>
                <th className="text-left px-3 py-2 text-slate-600 dark:text-slate-400 font-medium">Routes</th>
                <th className="text-left px-3 py-2 text-slate-600 dark:text-slate-400 font-medium">Location</th>
              </tr>
            </thead>
            <tbody>
              {summary.top_shared_stops.map(stop => (
                <tr key={stop.stop_id} className="border-t border-slate-100 dark:border-slate-800">
                  <td className="px-3 py-2 font-medium text-slate-900 dark:text-white">{stop.stop_name}</td>
                  <td className="px-3 py-2 text-slate-500">{stop.stop_id}</td>
                  <td className="px-3 py-2"><span className="bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 px-2 py-0.5 rounded-full text-xs font-medium">{stop.route_count}</span></td>
                  <td className="px-3 py-2 text-slate-500">{stop.stop_lat.toFixed(4)}, {stop.stop_lon.toFixed(4)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

