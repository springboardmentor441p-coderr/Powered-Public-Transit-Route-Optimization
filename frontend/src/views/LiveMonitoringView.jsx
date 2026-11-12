import React, { useState, useEffect, useRef } from 'react';
import L from 'leaflet';
import { 
  Bus, 
  Train, 
  Radio, 
  AlertTriangle, 
  RefreshCw, 
  MapPin, 
  Clock, 
  Compass, 
  Gauge,
  Info,
  ShieldAlert
} from 'lucide-react';
import { 
  getBusVehicles, 
  getTrainPositions, 
  getActiveAlerts, 
  getBusRoutes 
} from '../api';
import DataSourceBadge from '../components/DataSourceBadge';
import LoadingSpinner from '../components/LoadingSpinner';

const CTA_RAIL_LINES = [
  { id: 'Red', name: 'Red Line (Howard - 95th/Dan Ryan)', color: '#c60c30' },
  { id: 'Blue', name: 'Blue Line (O\'Hare - Forest Park)', color: '#00a1de' },
  { id: 'Brown', name: 'Brown Line (Kimball - Loop)', color: '#62361b' },
  { id: 'Green', name: 'Green Line (Harlem/Lake - Ashland/63rd/Cottage)', color: '#009b3a' },
  { id: 'Orange', name: 'Orange Line (Midway - Loop)', color: '#f9461c' },
  { id: 'Purple', name: 'Purple Line (Linden - Howard/Loop)', color: '#522398' },
  { id: 'Pink', name: 'Pink Line (54th/Cermak - Loop)', color: '#e27ea6' },
  { id: 'Yellow', name: 'Yellow Line (Skokie - Howard)', color: '#f9e300' }
];

const POPULAR_BUS_ROUTES = [
  { id: '79', name: '79 79th (Top Bus Ridership)' },
  { id: '9', name: '9 Ashland (Major North-South Corridor)' },
  { id: '66', name: '66 Chicago (High Frequency East-West)' },
  { id: '4', name: '4 Cottage Grove' },
  { id: '49', name: '49 Western' },
  { id: 'X9', name: 'X9 Ashland Express' }
];

export default function LiveMonitoringView() {
  const mapRef = useRef(null);
  const mapInstance = useRef(null);
  const markersLayer = useRef(null);

  const [mode, setMode] = useState('bus'); // 'bus' or 'train'
  const [selectedRoute, setSelectedRoute] = useState('79');
  const [selectedTrainLine, setSelectedTrainLine] = useState('Red');
  const [vehicles, setVehicles] = useState([]);
  const [dataSource, setDataSource] = useState('GTFS_SCHEDULE_SIMULATION');
  const [alerts, setAlerts] = useState([]);
  const [allAlerts, setAllAlerts] = useState([]);
  const [showAlertModal, setShowAlertModal] = useState(false);
  const [alertFilterMode, setAlertFilterMode] = useState('corridor'); // 'corridor' or 'all'
  const [loading, setLoading] = useState(true);
  const [lastRefreshed, setLastRefreshed] = useState(new Date());

  // Initialize Leaflet Map
  useEffect(() => {
    if (!mapRef.current) return;
    if (!mapInstance.current) {
      const map = L.map(mapRef.current, {
        center: [41.8781, -87.6298],
        zoom: 12,
        zoomControl: true,
      });

      // Use official OpenStreetMap tile server without API keys or watermarks
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a> contributors | Chicago Transit Authority',
        maxZoom: 19,
      }).addTo(map);

      markersLayer.current = L.layerGroup().addTo(map);
      mapInstance.current = map;
    }

    return () => {
      if (mapInstance.current) {
        mapInstance.current.remove();
        mapInstance.current = null;
      }
    };
  }, []);

  // Fetch Vehicles
  const loadData = async () => {
    setLoading(true);
    try {
      if (mode === 'bus') {
        const data = await getBusVehicles(selectedRoute);
        setVehicles(data.vehicles || []);
        setDataSource(data.metadata?.data_source || data.data_source || 'GTFS_SCHEDULE_SIMULATION');
      } else {
        const data = await getTrainPositions(selectedTrainLine);
        setVehicles(data.trains || []);
        setDataSource(data.metadata?.data_source || data.data_source || 'GTFS_SCHEDULE_SIMULATION');
      }

      const alertData = await getActiveAlerts(mode === 'bus' ? selectedRoute : selectedTrainLine);
      setAlerts(alertData.alerts || []);

      // Also fetch system-wide alerts for complete visibility
      try {
        const sysAlertData = await getActiveAlerts();
        setAllAlerts(sysAlertData.alerts || []);
      } catch (err) {
        console.warn('System alerts fetch warning:', err);
      }
      setLastRefreshed(new Date());
    } catch (e) {
      console.error('Failed to load live data', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [mode, selectedRoute, selectedTrainLine]);

  // Update map markers when vehicles change
  useEffect(() => {
    if (!mapInstance.current || !markersLayer.current) return;

    markersLayer.current.clearLayers();

    if (vehicles.length === 0) return;

    const bounds = [];

    vehicles.forEach((v) => {
      const lat = parseFloat(v.latitude);
      const lon = parseFloat(v.longitude);
      
      // Strict geographic validation: Chicago metropolitan coordinates bounding box
      if (isNaN(lat) || isNaN(lon) || lat < 41.5 || lat > 42.2 || lon < -87.95 || lon > -87.5) {
        return;
      }

      bounds.push([lat, lon]);

      const isTrain = mode === 'train';
      const color = isTrain 
        ? (CTA_RAIL_LINES.find(l => l.id.toLowerCase() === (v.line || selectedTrainLine).toLowerCase())?.color || '#00a1de')
        : '#0284c7';

      const isSimulated = String(dataSource).toUpperCase().includes('SIMULATION') || String(dataSource).toUpperCase().includes('DERIVED');

      const customIcon = L.divIcon({
        className: 'custom-transit-pin',
        html: `
          <div style="
            background-color: ${color}; 
            color: white; 
            padding: 4px 7px; 
            border-radius: 9999px; 
            border: 2px solid white; 
            font-size: 11px; 
            font-weight: bold; 
            display: flex; 
            align-items: center; 
            gap: 4px; 
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.4);
            white-space: nowrap;
          ">
            <span>${isTrain ? '🚆 ' + (v.line || selectedTrainLine) : '🚌 Rt ' + (v.route_id || selectedRoute)}</span>
          </div>
        `,
        iconSize: [60, 24],
        iconAnchor: [30, 12],
      });

      const marker = L.marker([lat, lon], { icon: customIcon });
      
      const popupContent = `
        <div style="color: #0f172a; font-family: sans-serif; font-size: 12px; padding: 4px; min-width: 180px;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
            <strong style="font-size: 13px;">${isTrain ? `Train Run #${v.run_number || v.train_id}` : `Bus #${v.vehicle_id}`}</strong>
            <span style="font-size: 10px; padding: 2px 5px; border-radius: 4px; background: ${isSimulated ? '#e0f2fe' : '#dcfce7'}; color: ${isSimulated ? '#0369a1' : '#15803d'}; font-weight: 600;">
              ${isSimulated ? 'GTFS Schedule' : 'Live GPS'}
            </span>
          </div>
          <div style="color: #64748b; margin-top: 2px;">Destination: <strong>${v.destination || 'In Service'}</strong></div>
          <div style="color: #64748b;">Heading: ${v.heading ? `${v.heading}°` : 'N/A'} | Speed: ${v.speed_mph !== undefined ? `${v.speed_mph} mph` : 'N/A'}</div>
          ${v.next_station ? `<div style="color: #0284c7; margin-top: 4px;">Next Station: ${v.next_station}</div>` : ''}
          <div style="color: #94a3b8; font-size: 10px; margin-top: 6px; border-top: 1px solid #e2e8f0; padding-top: 4px;">
            ${isSimulated ? 'Derived from GTFS timetable trajectory' : 'Live CTA API GPS telemetry'}
          </div>
        </div>
      `;

      marker.bindPopup(popupContent);
      markersLayer.current.addLayer(marker);
    });

    if (bounds.length > 0) {
      mapInstance.current.fitBounds(bounds, { padding: [40, 40], maxZoom: 14 });
    }
  }, [vehicles, mode, selectedRoute, selectedTrainLine, dataSource]);

  const isSimulatedMode = String(dataSource).toUpperCase().includes('SIMULATION') || String(dataSource).toUpperCase().includes('DERIVED');

  return (
    <div className="space-y-6">
      {/* Top Notice: Provenance & Transparency */}
      {isSimulatedMode ? (
        <div className="p-4 rounded-xl bg-sky-950/40 border border-sky-500/30 text-sky-200 text-xs flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Info className="w-4 h-4 text-sky-400 flex-shrink-0" />
            <span>
              <strong>GTFS Schedule Trajectory Emulation:</strong> CTA Bus/Train Tracker developer keys are not configured in <code className="bg-sky-900/60 px-1 py-0.5 rounded text-[11px]">.env</code>. Vehicle coordinates are dynamically calculated along official GTFS route shapes based on scheduled timetables.
            </span>
          </div>
          <DataSourceBadge source="GTFS_SIMULATION" />
        </div>
      ) : (
        <div className="p-4 rounded-xl bg-emerald-950/40 border border-emerald-500/30 text-emerald-200 text-xs flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Radio className="w-4 h-4 text-emerald-400 flex-shrink-0 animate-pulse" />
            <span>
              <strong>Live Telemetry Feed Active:</strong> Streaming real-time GPS positions from Chicago Transit Authority Bus Tracker and Train Tracker APIs.
            </span>
          </div>
          <DataSourceBadge source="LIVE" />
        </div>
      )}

      {/* Controls Bar */}
      <div className="p-5 rounded-2xl bg-slate-900/80 border border-slate-800 flex flex-col md:flex-row md:items-center justify-between gap-4">
        {/* Mode Selector */}
        <div className="flex items-center gap-2">
          <div className="bg-slate-800 p-1 rounded-xl flex items-center border border-slate-700">
            <button
              onClick={() => setMode('bus')}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold transition ${
                mode === 'bus'
                  ? 'bg-sky-500 text-white shadow-md'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              <Bus className="w-3.5 h-3.5" />
              <span>CTA Bus Fleet</span>
            </button>
            <button
              onClick={() => setMode('train')}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold transition ${
                mode === 'train'
                  ? 'bg-teal-500 text-white shadow-md'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              <Train className="w-3.5 h-3.5" />
              <span>CTA 'L' Rapid Transit</span>
            </button>
          </div>

          {/* Route or Line Dropdown */}
          {mode === 'bus' ? (
            <select
              value={selectedRoute}
              onChange={(e) => setSelectedRoute(e.target.value)}
              className="bg-slate-800 border border-slate-700 text-white text-xs font-medium rounded-xl px-3 py-2.5 focus:outline-none focus:border-sky-500"
            >
              {POPULAR_BUS_ROUTES.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.name}
                </option>
              ))}
            </select>
          ) : (
            <select
              value={selectedTrainLine}
              onChange={(e) => setSelectedTrainLine(e.target.value)}
              className="bg-slate-800 border border-slate-700 text-white text-xs font-medium rounded-xl px-3 py-2.5 focus:outline-none focus:border-teal-500"
            >
              {CTA_RAIL_LINES.map((l) => (
                <option key={l.id} value={l.id}>
                  {l.name}
                </option>
              ))}
            </select>
          )}

          <button
            onClick={loadData}
            disabled={loading}
            className="p-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition"
            title="Refresh positions"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-sky-400' : ''}`} />
          </button>
        </div>

        {/* Provenance and Time Badge */}
        <div className="flex items-center gap-3">
          <div className="text-xs text-slate-400 flex items-center gap-1.5 font-mono">
            <Clock className="w-3.5 h-3.5 text-slate-500" />
            <span>Updated: {lastRefreshed.toLocaleTimeString()}</span>
          </div>
        </div>
      </div>

      {/* Main Map + Vehicle Details Sidebar */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Map Container */}
        <div className="lg:col-span-3 rounded-2xl overflow-hidden border border-slate-800 bg-slate-900 h-[560px] relative">
          <div ref={mapRef} className="w-full h-full z-10" />

          {/* Floating Map Legend */}
          <div className="absolute bottom-4 left-4 z-20 p-3 rounded-xl bg-slate-900/90 backdrop-blur border border-slate-700 text-xs space-y-1.5 text-slate-300 shadow-xl pointer-events-none">
            <div className="font-semibold text-white">Map Legend</div>
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-sky-500"></span>
              <span>Bus Fleet Route</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-red-500"></span>
              <span>CTA 'L' Train Vehicle</span>
            </div>
          </div>
        </div>

        {/* Right Details Panel: Active Vehicles & Route Alerts */}
        <div className="space-y-4">
          {/* Active Vehicles Count */}
          <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
                Tracked Vehicles
              </span>
              <span className="text-xs font-mono font-bold text-sky-400 px-2 py-0.5 rounded bg-sky-500/10 border border-sky-500/20">
                {vehicles.length} {isSimulatedMode ? 'Estimated' : 'Active'}
              </span>
            </div>
            <div className="text-xs text-slate-400">
              {mode === 'bus' ? `Route ${selectedRoute} active coaches` : `${selectedTrainLine} Line consist positions`}
            </div>
          </div>

          {/* Vehicle List */}
          <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 space-y-3">
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400">
              Vehicle Positions
            </h4>
            <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
              {vehicles.length === 0 ? (
                <div className="text-xs text-slate-500 text-center py-6">No vehicles reported in corridor</div>
              ) : (
                vehicles.map((v, idx) => (
                  <div key={idx} className="p-2.5 rounded-lg bg-slate-800/50 border border-slate-700/60 text-xs space-y-1">
                    <div className="flex items-center justify-between font-semibold text-white">
                      <span>{mode === 'bus' ? `Coach #${v.vehicle_id}` : `Run #${v.run_number || v.train_id}`}</span>
                      <span className="text-[11px] font-mono text-sky-400">{v.speed_mph || 18} mph</span>
                    </div>
                    <div className="text-[11px] text-slate-400 flex items-center gap-1">
                      <Compass className="w-3 h-3 text-slate-500" />
                      <span>{v.destination || 'In Service'}</span>
                    </div>
                    <div className="text-[10px] text-slate-500 font-mono">
                      Coord: {Number(v.latitude).toFixed(3)}, {Number(v.longitude).toFixed(3)}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Active Route Alerts */}
          <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-amber-400 flex items-center gap-1.5">
                <AlertTriangle className="w-3.5 h-3.5" /> CTA Official Advisories
              </span>
              <div className="flex items-center gap-1">
                <button
                  onClick={() => setAlertFilterMode(alertFilterMode === 'corridor' ? 'all' : 'corridor')}
                  className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition"
                  title="Toggle between corridor-specific and all system alerts"
                >
                  {alertFilterMode === 'corridor' ? `Corridor (${alerts.length})` : `System-Wide (${allAlerts.length})`}
                </button>
              </div>
            </div>
            
            <div className="text-[11px] text-slate-400">
              {alertFilterMode === 'corridor' 
                ? (mode === 'bus' ? `Disruptions affecting Route ${selectedRoute}` : `Disruptions affecting ${selectedTrainLine} Line`)
                : 'All active Chicago CTA system customer alerts'}
            </div>

            <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
              {(alertFilterMode === 'corridor' ? alerts : allAlerts).length === 0 ? (
                <div className="text-xs text-slate-400 text-center py-3 bg-slate-950/40 rounded-lg border border-slate-800/80 p-2">
                  <span className="text-emerald-400 font-medium">✓ Normal Operations</span>: No active alerts on this corridor.
                  {allAlerts.length > 0 && (
                    <div className="mt-1 text-[10px] text-slate-500">
                      ({allAlerts.length} system alerts active elsewhere across CTA)
                    </div>
                  )}
                </div>
              ) : (
                (alertFilterMode === 'corridor' ? alerts : allAlerts).map((a, i) => (
                  <div key={a.alert_id || i} className="p-2 rounded bg-amber-500/10 border border-amber-500/20 text-[11px] text-amber-200">
                    <div className="font-semibold text-amber-300">{a.headline}</div>
                    {a.impact && <div className="text-[10px] text-slate-400 mt-0.5 font-mono">Impact: {a.impact}</div>}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
