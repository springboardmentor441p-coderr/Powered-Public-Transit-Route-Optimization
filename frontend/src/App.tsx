import React, { useState, useEffect, useRef } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import {
  Activity, Bus, Calendar, Clock, Compass, Database, GitCompare,
  Layers, Play, Pause, SkipForward, RotateCcw, Sliders, TrendingUp,
  AlertTriangle, CheckCircle2, ShieldAlert, Sparkles, ArrowUpRight, Info
} from 'lucide-react';

const API_BASE = 'http://127.0.0.1:8000/api';

// --- Types aligned with v3.8 Technical Specification ---
type ScreenTab = 'overview' | 'rankings' | 'detail' | 'compare' | 'replay' | 'scenarios' | 'coverage';

interface RouteSummary {
  route: string;
  avg_daily_rides: number;
  avg_trips_per_day: number;
  boardings_per_trip: number;
  weekend_weekday_ratio: number;
  cluster: number;
  cluster_label: string;
  served_stop_count?: number;
  exclusive_stop_fraction?: number;
}

interface RankingRow {
  route: string;
  daytype: string;
  observed_days: number;
  total_rides: number;
  total_scheduled_trips: number;
  total_scheduled_hours: number;
  rides_per_scheduled_trip: number;
  rides_per_scheduled_hour: number;
  is_eligible: boolean;
  eligibility_reason: string;
  service_productivity_rank: number | null;
  cluster_label?: string;
}


type ChartDatum = { label: string; value: number; color?: string };

function ChartPanel({ title, subtitle, children, className = '' }: { title: string; subtitle?: string; children: React.ReactNode; className?: string }) {
  return (
    <section className={`glass-panel rounded-2xl border border-slate-800/90 p-5 ${className}`}>
      <div className="mb-4">
        <h3 className="font-display text-sm font-bold text-white">{title}</h3>
        {subtitle && <p className="mt-1 text-xs text-slate-400">{subtitle}</p>}
      </div>
      {children}
    </section>
  );
}

function HorizontalBarChart({ data, suffix = '', maxItems = 8 }: { data: ChartDatum[]; suffix?: string; maxItems?: number }) {
  const items = data.filter(d => Number.isFinite(d.value)).slice(0, maxItems);
  const max = Math.max(1, ...items.map(d => d.value));
  if (!items.length) return <p className="py-8 text-center text-xs text-slate-500">No chart data available for this selection.</p>;
  return (
    <div className="space-y-3">
      {items.map((d, i) => (
        <div key={`${d.label}-${i}`} className="grid grid-cols-[100px_1fr_76px] items-center gap-3">
          <span className="truncate text-xs text-slate-300">{d.label}</span>
          <div className="h-3 overflow-hidden rounded-full bg-slate-800">
            <div className="h-full rounded-full transition-all duration-500" style={{ width: `${Math.max(1, d.value / max * 100)}%`, background: d.color || 'linear-gradient(90deg,#06b6d4,#8b5cf6)' }} />
          </div>
          <span className="text-right text-xs font-semibold tabular-nums text-slate-200">{d.value.toLocaleString(undefined, { maximumFractionDigits: 1 })}{suffix}</span>
        </div>
      ))}
    </div>
  );
}

function TrendLineChart({ data, valueKey = 'rides', labelKey = 'service_date' }: { data: any[]; valueKey?: string; labelKey?: string }) {
  const points = data.filter(d => Number.isFinite(Number(d?.[valueKey]))).slice(-30);
  if (points.length < 2) return <p className="py-8 text-center text-xs text-slate-500">At least two matched observations are needed to draw this trend.</p>;
  const values = points.map(d => Number(d[valueKey]));
  const min = Math.min(...values), max = Math.max(...values), span = Math.max(1, max - min);
  const coords = values.map((v, i) => `${24 + i * (552 / (values.length - 1))},${145 - ((v - min) / span) * 105}`).join(' ');
  const area = `24,145 ${coords} 576,145`;
  return (
    <div>
      <svg viewBox="0 0 600 174" className="h-44 w-full overflow-visible" role="img" aria-label="Historical daily ridership trend">
        {[40, 92, 145].map(y => <line key={y} x1="24" x2="576" y1={y} y2={y} stroke="#263449" strokeDasharray="4 5" />)}
        <defs><linearGradient id="routeTrendFill" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stopColor="#22d3ee" stopOpacity=".35"/><stop offset="100%" stopColor="#22d3ee" stopOpacity="0"/></linearGradient></defs>
        <polygon points={area} fill="url(#routeTrendFill)" />
        <polyline points={coords} fill="none" stroke="#22d3ee" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
        {values.map((v, i) => {
          const cx = 24 + i * (552 / (values.length - 1));
          const cy = 145 - ((v - min) / span) * 105;
          return <circle key={i} cx={cx} cy={cy} r="4" fill="#22d3ee" stroke="#0b1424" strokeWidth="2"><title>{`${points[i]?.[labelKey] || 'Date'}: ${v.toLocaleString()} rides`}</title></circle>;
        })}
        <text x="24" y="18" fill="#a5b4c8" fontSize="11">{Math.round(max).toLocaleString()} rides</text>
        <text x="24" y="165" fill="#8494aa" fontSize="10">{String(points[0]?.[labelKey] || '').slice(5)}</text>
        <text x="576" y="165" fill="#8494aa" fontSize="10" textAnchor="end">{String(points[points.length - 1]?.[labelKey] || '').slice(5)}</text>
      </svg>
      <p className="text-[11px] text-slate-500">Latest {points.length} matched observations • Daily boardings</p>
    </div>
  );
}

function ComparisonBars({ labels, values, colors = ['#22d3ee', '#a78bfa'], suffix = '' }: { labels: string[]; values: number[]; colors?: string[]; suffix?: string }) {
  const max = Math.max(1, ...values.filter(Number.isFinite));
  return (
    <div className="space-y-4">
      {labels.map((label, i) => (
        <div key={label}>
          <div className="mb-1.5 flex justify-between gap-3 text-xs"><span className="text-slate-300">{label}</span><strong className="tabular-nums text-white">{Number.isFinite(values[i]) ? values[i].toLocaleString(undefined, { maximumFractionDigits: 2 }) : 'N/A'}{suffix}</strong></div>
          <div className="h-4 overflow-hidden rounded-full bg-slate-800"><div className="h-full rounded-full transition-all duration-500" style={{ width: `${Number.isFinite(values[i]) ? Math.max(1, values[i] / max * 100) : 0}%`, background: colors[i % colors.length] }} /></div>
        </div>
      ))}
    </div>
  );
}



const CLUSTER_PALETTE: Record<number, string> = {
  0: '#38bdf8', 1: '#a78bfa', 2: '#34d399', 3: '#f59e0b'
};

function ClusterDonutChart({ routes }: { routes: RouteSummary[] }) {
  const groups = [0, 1, 2, 3].map(id => ({
    id,
    label: ({ 0: 'Local Feeders', 1: 'High-Density Trunks', 2: 'Urban Connectors', 3: 'Weekend Outliers' } as Record<number, string>)[id],
    count: routes.filter(r => r.cluster === id).length,
    color: CLUSTER_PALETTE[id]
  }));
  const total = groups.reduce((sum, g) => sum + g.count, 0);
  let cursor = 0;
  const stops = groups.map(g => {
    const start = cursor;
    cursor += total ? (g.count / total) * 100 : 0;
    return `${g.color} ${start}% ${cursor}%`;
  }).join(', ');
  return (
    <div className="flex flex-col sm:flex-row items-center gap-6">
      <div className="relative h-40 w-40 shrink-0 rounded-full" style={{ background: total ? `conic-gradient(${stops})` : '#263449' }}>
        <div className="absolute inset-5 rounded-full bg-[#0b1424] flex flex-col items-center justify-center">
          <strong className="text-3xl text-white">{total}</strong>
          <span className="text-[10px] tracking-widest text-slate-400">ROUTES</span>
        </div>
      </div>
      <div className="w-full flex-1 space-y-3">
        {groups.map(g => <div key={g.id} className="flex items-center justify-between gap-3 text-xs">
          <span className="flex items-center gap-2 text-slate-300"><i className="h-2.5 w-2.5 rounded-full" style={{ background: g.color }} />{g.label}</span>
          <strong className="text-white">{g.count} <span className="text-slate-500">({total ? (g.count / total * 100).toFixed(1) : '0.0'}%)</span></strong>
        </div>)}
      </div>
    </div>
  );
}

function MetricBar({ label, value, max = 100, color, helper }: { label: string; value: number; max?: number; color: string; helper: string }) {
  const width = Math.max(0, Math.min(100, (value / max) * 100));
  return <div className="space-y-1.5">
    <div className="flex items-center justify-between gap-3 text-xs"><span className="text-slate-300">{label}</span><strong className="text-white tabular-nums">{value.toFixed(2)}%</strong></div>
    <div className="h-3 overflow-hidden rounded-full bg-slate-800"><div className="h-full rounded-full transition-all" style={{ width: `${width}%`, background: color }} /></div>
    <p className="text-[10px] text-slate-500">{helper}</p>
  </div>;
}

function DemandSupplyScatter({ routes, selectedRoute, onSelect }: { routes: RouteSummary[]; selectedRoute: string; onSelect: (route: string) => void }) {
  const w = 700, h = 310, left = 66, right = 24, top = 20, bottom = 48;
  const maxX = Math.max(1, ...routes.map(r => Number(r.avg_trips_per_day) || 0)) * 1.08;
  const maxY = Math.max(1, ...routes.map(r => Number(r.avg_daily_rides) || 0)) * 1.08;
  const px = (v: number) => left + (v / maxX) * (w - left - right);
  const py = (v: number) => h - bottom - (v / maxY) * (h - top - bottom);
  return <div className="w-full overflow-x-auto">
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full min-w-[500px]" role="img" aria-label="Demand versus scheduled supply scatter plot">
      {[0,1,2,3,4].map(i => { const yy = top + i * (h-top-bottom)/4; return <line key={i} x1={left} x2={w-right} y1={yy} y2={yy} stroke="#263449" strokeDasharray="4 5" />; })}
      {routes.map(r => <circle key={r.route} cx={px(Number(r.avg_trips_per_day)||0)} cy={py(Number(r.avg_daily_rides)||0)} r={r.route === selectedRoute ? 8 : 5}
        fill={CLUSTER_PALETTE[r.cluster] || '#94a3b8'} stroke={r.route === selectedRoute ? '#fff' : '#0b1424'} strokeWidth={r.route === selectedRoute ? 2.5 : 1}
        opacity={r.route === selectedRoute ? 1 : .8} style={{ cursor: 'pointer' }} onClick={() => onSelect(r.route)}>
        <title>{`Route ${r.route} | ${Number(r.avg_trips_per_day).toFixed(1)} scheduled trips/day | ${Math.round(r.avg_daily_rides).toLocaleString()} mean rides/day | Cluster ${r.cluster}`}</title>
      </circle>)}
      <line x1={left} x2={w-right} y1={h-bottom} y2={h-bottom} stroke="#64748b" />
      <line x1={left} x2={left} y1={top} y2={h-bottom} stroke="#64748b" />
      <text x={(left+w-right)/2} y={h-8} textAnchor="middle" fill="#94a3b8" fontSize="11">Scheduled Trips / Day</text>
      <text transform={`translate(15 ${(h+top-bottom)/2}) rotate(-90)`} textAnchor="middle" fill="#94a3b8" fontSize="11">Mean Daily Rides</text>
    </svg>
    <div className="mt-2 flex flex-wrap gap-3">{[0,1,2,3].map(id => <span key={id} className="flex items-center gap-1.5 text-[10px] text-slate-400"><i className="h-2 w-2 rounded-full" style={{ background: CLUSTER_PALETTE[id] }} />Cluster {id}</span>)}</div>
    <p className="mt-2 text-[10px] text-slate-500">Click a point to select that route across the dashboard. Hover for route values.</p>
  </div>;
}

function ForecastTrailChart({ entries }: { entries: any[] }) {
  const rows = [...entries].reverse().slice(-12);
  if (!rows.length) return <p className="py-6 text-center text-xs text-slate-500">Advance the replay by +1 Day to build the forecast trail.</p>;
  return <HorizontalBarChart data={rows.map((item, i) => ({ label: String(item.target_date || `Forecast ${i+1}`), value: Number(item.predicted_rides) || 0, color: i === rows.length - 1 ? '#22d3ee' : '#64748b' }))} maxItems={12} suffix=" rides" />;
}

export default function App() {
  // Navigation & Global Controls (Section 9.16.1)
  const [activeTab, setActiveTab] = useState<ScreenTab>('overview');
  const [selectedRoute, setSelectedRoute] = useState<string>('22');
  const [compareRouteB, setCompareRouteB] = useState<string>('36');
  const [dayType, setDayType] = useState<'W' | 'A' | 'U'>('W');
  const [rankingMetric, setRankingMetric] = useState<string>('rides_per_scheduled_hour');
  const [clusterFilter, setClusterFilter] = useState<number | 'ALL'>('ALL');
  const [toast, setToast] = useState<{ msg: string; type: 'info' | 'warn' } | null>(null);

  // Backend Data States
  const [coverageData, setCoverageData] = useState<any>(null);
  const [routes, setRoutes] = useState<RouteSummary[]>([]);
  const [rankings, setRankings] = useState<RankingRow[]>([]);
  const [routeHistory, setRouteHistory] = useState<any>(null);
  const [compareData, setCompareData] = useState<any>(null);
  const [backendOnline, setBackendOnline] = useState<boolean>(true);

  // Historical Replay State Machine (Section 9.14)
  const [replaySession, setReplaySession] = useState<any>({
    session_id: 'demo-local',
    virtual_date: '2026-06-01',
    min_date: '2026-06-01',
    max_date: '2026-07-31',
    reporting_delay_days: 1,
    speed_seconds: 5,
    status: 'paused',
    model_version: 'xgb_option2_v1.0'
  });
  const [replayForecast, setReplayForecast] = useState<any>(null);
  const [replayLog, setReplayLog] = useState<any[]>([]);

  // Conditional Service Scenario State (Section 9.15)
  const [scenBaselineRides, setScenBaselineRides] = useState<number>(12800);
  const [scenBaselineTrips, setScenBaselineTrips] = useState<number>(240);
  const [scenBaselineHours, setScenBaselineHours] = useState<number>(195);
  const [scenProposedTrips, setScenProposedTrips] = useState<number>(288);
  const [scenDemandStress, setScenDemandStress] = useState<number>(0);
  const [savedScenarios, setSavedScenarios] = useState<any[]>([]);

  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const leafletMapRef = useRef<any>(null);

  const showToast = (msg: string, type: 'info' | 'warn' = 'info') => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3500);
  };

  // --- Initial Data Fetching ---
  useEffect(() => {
    async function initLoad() {
      try {
        const [covRes, routesRes] = await Promise.all([
          fetch(`${API_BASE}/data/coverage`),
          fetch(`${API_BASE}/routes`)
        ]);
        if (!covRes.ok) throw new Error('Backend unreachable');
        setCoverageData(await covRes.json());
        const rData = await routesRes.json();
        setRoutes(rData);
        setBackendOnline(true);

        // Initialize Replay Session
        const repRes = await fetch(`${API_BASE}/replays`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ start_date: '2026-06-01', reporting_delay_days: 1, speed_seconds: 5 })
        });
        if (repRes.ok) setReplaySession(await repRes.json());
      } catch {
        setBackendOnline(false);
        showToast('FastAPI offline — displaying cached v3.8 reference metrics', 'warn');
        setRoutes([
          { route: '22', avg_daily_rides: 14820, avg_trips_per_day: 295, boardings_per_trip: 50.2, weekend_weekday_ratio: 0.78, cluster: 1, cluster_label: 'High-Density Commuter Trunk', served_stop_count: 142, exclusive_stop_fraction: 0.34 },
          { route: '79', avg_daily_rides: 18450, avg_trips_per_day: 340, boardings_per_trip: 54.3, weekend_weekday_ratio: 0.74, cluster: 1, cluster_label: 'High-Density Commuter Trunk', served_stop_count: 168, exclusive_stop_fraction: 0.41 },
          { route: '36', avg_daily_rides: 11200, avg_trips_per_day: 245, boardings_per_trip: 45.7, weekend_weekday_ratio: 0.81, cluster: 1, cluster_label: 'High-Density Commuter Trunk', served_stop_count: 130, exclusive_stop_fraction: 0.29 },
          { route: '66', avg_daily_rides: 15600, avg_trips_per_day: 310, boardings_per_trip: 50.3, weekend_weekday_ratio: 0.71, cluster: 1, cluster_label: 'High-Density Commuter Trunk', served_stop_count: 118, exclusive_stop_fraction: 0.38 },
          { route: '151', avg_daily_rides: 9430, avg_trips_per_day: 215, boardings_per_trip: 43.8, weekend_weekday_ratio: 0.76, cluster: 2, cluster_label: 'Moderate Urban Connector', served_stop_count: 112, exclusive_stop_fraction: 0.22 },
        ]);
      }
    }
    initLoad();
  }, []);

  // --- Fetch Rankings whenever DayType or Metric changes ---
  useEffect(() => {
    if (!backendOnline) return;
    fetch(`${API_BASE}/rankings?daytype=${dayType}&metric=${rankingMetric}&eligible_only=false`)
      .then(r => r.json())
      .then(d => setRankings(d.results || []))
      .catch(() => {});
  }, [dayType, rankingMetric, backendOnline]);

  // --- Fetch Route Detail & Map Geometry ---
  useEffect(() => {
    if (!backendOnline) return;
    const mode = activeTab === 'replay' ? 'replay' : 'historical';
    const cutoff = replaySession?.virtual_date || '2026-07-31';
    fetch(`${API_BASE}/routes/${selectedRoute}/history?mode=${mode}&max_permitted_date=${cutoff}`)
      .then(r => r.json())
      .then(data => {
        setRouteHistory(data);
        if (data.history?.length) {
          const latest = data.history[data.history.length - 1];
          setScenBaselineRides(latest.rides || 12000);
          setScenBaselineTrips(latest.scheduled_trips || 220);
          setScenBaselineHours(latest.scheduled_service_hours || 180);
          setScenProposedTrips(Math.round((latest.scheduled_trips || 220) * 1.2));
        }
      })
      .catch(() => {});
  }, [selectedRoute, activeTab, replaySession?.virtual_date, backendOnline]);

  // --- Fetch Route Comparison ---
  useEffect(() => {
    if (!backendOnline || activeTab !== 'compare') return;
    fetch(`${API_BASE}/routes/compare?route_a=${selectedRoute}&route_b=${compareRouteB}&daytype=${dayType}`)
      .then(r => r.json())
      .then(setCompareData)
      .catch(() => {});
  }, [selectedRoute, compareRouteB, dayType, activeTab, backendOnline]);

  // --- Replay Clock Timer & State Polling (Section 9.14.2) ---
  useEffect(() => {
    if (!backendOnline || replaySession.status !== 'running') return;
    const interval = setInterval(async () => {
      await handleReplayControl('advance');
    }, (replaySession.speed_seconds || 5) * 1000);
    return () => clearInterval(interval);
  }, [replaySession.status, replaySession.speed_seconds, backendOnline]);

  useEffect(() => {
    if (!backendOnline || !replaySession.session_id || replaySession.session_id === 'demo-local') return;
    fetch(`${API_BASE}/replays/${replaySession.session_id}?route=${selectedRoute}`)
      .then(r => r.json())
      .then(data => {
        setReplayForecast(data.active_route_forecast);
        if (data.active_route_forecast?.status === 'predicted') {
          setReplayLog(prev => {
            const exists = prev.some(x => x.target_date === data.active_route_forecast.target_date && x.route === selectedRoute);
            return exists ? prev : [data.active_route_forecast, ...prev].slice(0, 12);
          });
        }
      })
      .catch(() => {});
  }, [replaySession.virtual_date, selectedRoute, backendOnline]);

  const handleReplayControl = async (action: string) => {
    if (!backendOnline) {
      showToast('Start FastAPI backend to run live replay state machine', 'warn');
      return;
    }
    const res = await fetch(`${API_BASE}/replays/${replaySession.session_id}/control`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action })
    });
    if (res.ok) {
      const updated = await res.json();
      setReplaySession(updated);
      if (action === 'reset') setReplayLog([]);
    }
  };

  // --- Leaflet Map Initialization for Route Detail ---
  useEffect(() => {
    if (activeTab !== 'detail' || !mapContainerRef.current) return;

    if (!leafletMapRef.current) {
      leafletMapRef.current = L.map(mapContainerRef.current).setView([41.8781, -87.6298], 11);
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap | CTA GTFS 2026-09'
      }).addTo(leafletMapRef.current);
    }

    const map = leafletMapRef.current;
    map.eachLayer((layer: any) => {
      if (layer instanceof L.Polyline) map.removeLayer(layer);
    });

    const coords = routeHistory?.shape_coordinates;
    if (coords && coords.length > 0) {
      const polyline = L.polyline(coords, { color: '#22d3ee', weight: 4, opacity: 0.9 }).addTo(map);
      map.fitBounds(polyline.getBounds(), { padding: [24, 24] });
    }
  }, [activeTab, routeHistory]);

  if (leafletMapRef.current) {
  requestAnimationFrame(() => {
    leafletMapRef.current?.invalidateSize();
  });
}

  // --- Scenario Arithmetic Calculation (Section 9.15) ---
  const meanDurMins = scenBaselineTrips > 0 ? (scenBaselineHours * 60) / scenBaselineTrips : 40;
  const stressedRides = scenBaselineRides * (1 + scenDemandStress / 100);
  const scenarioHours = Number(((scenProposedTrips * meanDurMins) / 60).toFixed(2));
  const baseRidesPerTrip = scenBaselineTrips > 0 ? (scenBaselineRides / scenBaselineTrips).toFixed(2) : 'N/A';
  const scenRidesPerTrip = scenProposedTrips > 0 ? (stressedRides / scenProposedTrips).toFixed(2) : 'Unavailable';
  const baseRidesPerHour = scenBaselineHours > 0 ? (scenBaselineRides / scenBaselineHours).toFixed(2) : 'N/A';
  const scenRidesPerHour = scenarioHours > 0 ? (stressedRides / scenarioHours).toFixed(2) : 'Unavailable';

  const saveScenario = async () => {
    const payload = {
      route: selectedRoute,
      service_date: replaySession.virtual_date,
      daytype: dayType,
      baseline_rides: scenBaselineRides,
      baseline_trips: scenBaselineTrips,
      baseline_hours: scenBaselineHours,
      proposed_trips: scenProposedTrips,
      demand_stress_pct: scenDemandStress
    };
    if (backendOnline) {
      const res = await fetch(`${API_BASE}/scenarios`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (res.ok) {
        const saved = await res.json();
        setSavedScenarios(prev => [saved, ...prev]);
        showToast(`Scenario ${saved.scenario_id} saved with explicit assumptions`);
        return;
      }
    }
    setSavedScenarios(prev => [{
      scenario_id: Math.random().toString(36).substring(2, 8),
      route: selectedRoute,
      assumptions: { demand_stress_pct: scenDemandStress, assumed_mean_trip_duration_mins: meanDurMins.toFixed(1) },
      baseline: { rides: scenBaselineRides, scheduled_trips: scenBaselineTrips, rides_per_trip: baseRidesPerTrip },
      scenario: { rides: Math.round(stressedRides), proposed_trips: scenProposedTrips, rides_per_trip: scenRidesPerTrip }
    }, ...prev]);
    showToast('Scenario saved locally');
  };

  const filteredRoutes = clusterFilter === 'ALL'
    ? routes
    : routes.filter(r => r.cluster === clusterFilter);

  return (
    <div className="min-h-screen bg-[#060913] bg-grid-pattern text-slate-100 flex flex-col">
      {/* Toast Notification */}
      {toast && (
        <div className={`fixed bottom-5 right-5 z-50 px-4 py-3 rounded-xl glass-panel border flex items-center gap-3 shadow-2xl transition-all ${
          toast.type === 'warn' ? 'border-amber-500/40 text-amber-200' : 'border-cyan-400/40 text-cyan-200'
        }`}>
          <Info className="w-4 h-4 shrink-0" />
          <span className="text-sm font-medium">{toast.msg}</span>
        </div>
      )}

      {/* Top Navigation & Global Provenance Bar (Section 9.16.1) */}
      <header className="sticky top-0 z-40 glass-panel border-b border-cyan-500/20 px-6 py-3">
        <div className="max-w-7xl mx-auto flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-cyan-400 to-violet-600 flex items-center justify-center shadow-lg shadow-cyan-500/20">
              <Bus className="w-5 h-5 text-slate-950" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="font-display font-bold text-lg tracking-wide text-white">ROUTERANKER</h1>
                <span className="text-[10px] uppercase tracking-widest px-2 py-0.5 rounded-full bg-cyan-500/15 text-cyan-300 border border-cyan-400/30">
                  CTA v3.8
                </span>
              </div>
              <p className="text-xs text-slate-400">Chicago Transit Authority • Daily Demand & Scheduled Service</p>
            </div>
          </div>

          {/* Global Selectors */}
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2 bg-slate-900/90 border border-slate-700/70 rounded-lg px-3 py-1.5">
              <Compass className="w-4 h-4 text-cyan-400" />
              <label className="text-xs text-slate-400">Route:</label>
              <select
                value={selectedRoute}
                onChange={e => setSelectedRoute(e.target.value)}
                className="bg-transparent text-sm font-semibold text-white focus:outline-none"
              >
                {routes.map(r => (
                  <option key={r.route} value={r.route} className="bg-slate-900">
                    Route {r.route}
                  </option>
                ))}
              </select>
            </div>

            <div className="flex rounded-lg bg-slate-900/90 p-1 border border-slate-700/70">
              {(['W', 'A', 'U'] as const).map(dt => (
                <button
                  key={dt}
                  onClick={() => setDayType(dt)}
                  className={`px-2.5 py-1 rounded-md text-xs font-medium transition ${
                    dayType === dt
                      ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-400/40'
                      : 'text-slate-400 hover:text-white'
                  }`}
                >
                  {dt === 'W' ? 'Weekday (W)' : dt === 'A' ? 'Saturday (A)' : 'Sun/Hol (U)'}
                </button>
              ))}
            </div>

          </div>
        </div>

        {/* Screen Navigation Tabs (Section 9.16.2) */}
        <nav className="max-w-7xl mx-auto mt-3 pt-2 border-t border-slate-800/80 flex gap-1 overflow-x-auto">
          {[
            { id: 'overview', label: 'Network Overview', icon: Activity },
            { id: 'rankings', label: 'Review Priorities', icon: TrendingUp },
            { id: 'detail', label: 'Route Detail & Map', icon: Compass },
            { id: 'compare', label: 'Compare Routes', icon: GitCompare },
            { id: 'replay', label: 'Forecast & Replay', icon: Play },
            { id: 'scenarios', label: 'Service Scenarios', icon: Sliders },
            { id: 'coverage', label: 'Data & Coverage', icon: Database },
          ].map(tab => {
            const Icon = tab.icon;
            const active = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as ScreenTab)}
                className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-medium whitespace-nowrap transition-all ${
                  active
                    ? 'bg-gradient-to-r from-cyan-500/20 to-violet-500/20 text-cyan-200 border border-cyan-400/40 neon-border-cyan'
                    : 'text-slate-400 hover:text-slate-100 hover:bg-slate-800/50'
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                {tab.label}
              </button>
            );
          })}
        </nav>
      </header>

      {/* Main Content Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-6 py-6 space-y-6">
        {/* Provenance Banner (Section 9.13.3) */}
        <div className="flex flex-wrap items-center justify-between gap-2 px-4 py-2 rounded-xl bg-slate-900/70 border border-slate-800 text-xs text-slate-400">
          <div className="flex items-center gap-4">
            <span><strong className="text-slate-200">Observation Window:</strong> 2024-08-01 – 2026-07-31</span>
            <span><strong className="text-slate-200">Matched Schedule Window:</strong> 2025-11-23 – 2026-07-31 (8 GTFS Snapshots)</span>
          </div>
          <span className="text-cyan-400/90">Units: Daily boardings (rides/day) & Scheduled trips/day • Not onboard occupancy</span>
        </div>

        {/* =========================================================
            SCREEN 1: NETWORK OVERVIEW & ROUTE GROUPS
           ========================================================= */}
        {activeTab === 'overview' && (
          <div className="space-y-6">
            {/* KPI Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {[
                { label: 'Matched Route/Date Rows', val: '28,374', sub: 'Across 251 calendar dates (125 routes)', accent: 'text-cyan-400' },
                { label: '2-Year Demand Records', val: '83,997', sub: '1,120,604 total historical rows', accent: 'text-violet-400' },
                { label: 'XGBoost Option 2 WAPE', val: '6.73%', sub: 'Test R²: 98.37% | Val WAPE: 6.45%', accent: 'text-emerald-400' },
                { label: 'KMeans Route Profiles', val: '4 Groups', sub: '129 routes segmented by demand/supply', accent: 'text-fuchsia-400' },
              ].map((kpi, i) => (
                <div key={i} className="glass-panel rounded-2xl p-5 hover:-translate-y-0.5 transition-transform">
                  <p className="text-xs uppercase tracking-wider text-slate-400">{kpi.label}</p>
                  <p className={`font-display text-2xl font-bold mt-2 ${kpi.accent}`}>{kpi.val}</p>
                  <p className="text-xs text-slate-400 mt-1">{kpi.sub}</p>
                </div>
              ))}
            </div>

            <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
              <ChartPanel title="Route Demand Leaders" subtitle="Top 8 routes ranked by mean daily ridership; selected route is highlighted">
                <HorizontalBarChart data={[...routes].sort((a, b) => b.avg_daily_rides - a.avg_daily_rides).slice(0, 8).map(r => ({ label: `Route ${r.route}${r.route === selectedRoute ? ' ★' : ''}`, value: r.avg_daily_rides, color: r.route === selectedRoute ? '#22d3ee' : '#64748b' }))} suffix=" rides" />
              </ChartPanel>
              <ChartPanel title="KMeans Cluster Distribution" subtitle="Live breakdown calculated from the route summaries loaded from the API">
                <ClusterDonutChart routes={routes} />
              </ChartPanel>
              <ChartPanel title="XGBoost Model Accuracy Gauges" subtitle="Reported Option 2 evaluation metrics; WAPE is lower-is-better">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
                  <div className="space-y-5">
                    <MetricBar label="Test WAPE" value={6.73} max={10} color="#22d3ee" helper="6.73% reported test error" />
                    <MetricBar label="Validation WAPE" value={6.45} max={10} color="#a78bfa" helper="6.45% reported validation error" />
                  </div>
                  <div className="space-y-5">
                    <MetricBar label="Test R²" value={98.37} color="#34d399" helper="98.37% test fit" />
                    <MetricBar label="Validation R²" value={98.72} color="#f472b6" helper="98.72% validation fit" />
                  </div>
                </div>
              </ChartPanel>
              <ChartPanel title="Interactive Demand vs Supply" subtitle="Each point represents a route. X = scheduled trips/day; Y = mean daily rides.">
                <DemandSupplyScatter routes={routes} selectedRoute={selectedRoute} onSelect={setSelectedRoute} />
              </ChartPanel>
            </div>

            {/* Cluster Filter Pills */}
            <div className="glass-panel rounded-2xl p-5">
              <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
                <div>
                  <h2 className="font-display text-base font-bold text-white flex items-center gap-2">
                    <Layers className="w-4 h-4 text-cyan-400" />
                    KMeans Structural Route Profiles (2024-08 to 2026-07)
                  </h2>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Cluster numbers denote operational similarity, not automated efficiency grades (Section 9.11).
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  {[
                    { id: 'ALL', label: 'All Routes (129)' },
                    { id: 1, label: 'High-Density Trunks (16)' },
                    { id: 2, label: 'Urban Connectors (45)' },
                    { id: 0, label: 'Local Feeders (66)' },
                    { id: 3, label: 'Weekend Outliers (2)' },
                  ].map(pill => (
                    <button
                      key={String(pill.id)}
                      onClick={() => setClusterFilter(pill.id as any)}
                      className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition ${
                        clusterFilter === pill.id
                          ? 'bg-cyan-500/20 border-cyan-400 text-cyan-200'
                          : 'bg-slate-900/60 border-slate-700/70 text-slate-400 hover:text-white'
                      }`}
                    >
                      {pill.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Routes Table */}
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="border-b border-slate-800 text-[11px] uppercase tracking-wider text-slate-400">
                      <th className="py-3 px-3">Route</th>
                      <th className="py-3 px-3">Cluster Group</th>
                      <th className="py-3 px-3 text-right">Mean Rides/Day</th>
                      <th className="py-3 px-3 text-right">Scheduled Trips/Day</th>
                      <th className="py-3 px-3 text-right">Rides / Trip</th>
                      <th className="py-3 px-3 text-right">Weekend/Wkdy Ratio</th>
                      <th className="py-3 px-3 text-right">Inspect</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60 text-sm">
                    {filteredRoutes.slice(0, 15).map(r => (
                      <tr key={r.route} className="hover:bg-cyan-500/5 transition">
                        <td className="py-2.5 px-3 font-display font-bold text-cyan-300">Route {r.route}</td>
                        <td className="py-2.5 px-3">
                          <span className="text-xs px-2.5 py-0.5 rounded-full bg-violet-500/15 text-violet-200 border border-violet-500/30">
                            {r.cluster_label}
                          </span>
                        </td>
                        <td className="py-2.5 px-3 text-right font-medium">{Math.round(r.avg_daily_rides).toLocaleString()}</td>
                        <td className="py-2.5 px-3 text-right text-slate-300">{r.avg_trips_per_day.toFixed(1)}</td>
                        <td className="py-2.5 px-3 text-right text-emerald-300 font-medium">{r.boardings_per_trip.toFixed(1)}</td>
                        <td className="py-2.5 px-3 text-right text-slate-300">{r.weekend_weekday_ratio.toFixed(2)}</td>
                        <td className="py-2.5 px-3 text-right">
                          <button
                            onClick={() => { setSelectedRoute(r.route); setActiveTab('detail'); }}
                            className="inline-flex items-center gap-1 text-xs text-cyan-400 hover:text-cyan-200"
                          >
                            Details <ArrowUpRight className="w-3.5 h-3.5" />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* =========================================================
            SCREEN 2: REVIEW PRIORITIES & RANKINGS (Section 9.12)
           ========================================================= */}
        {activeTab === 'rankings' && (
          <div className="glass-panel rounded-2xl p-6 space-y-5">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <h2 className="font-display text-lg font-bold text-white">Planner Review Priorities ({dayType === 'W' ? 'Weekday' : dayType === 'A' ? 'Saturday' : 'Sunday/Holiday'})</h2>
                <p className="text-xs text-slate-400 mt-0.5">
                  Computed via ratio of sums across matched dates (2025-11-23 to 2026-07-31). Minimum 20 matched days required for ranking eligibility (Section 9.7.2).
                </p>
              </div>
              <div className="flex items-center gap-2">
                <label className="text-xs text-slate-400">Indicator:</label>
                <select
                  value={rankingMetric}
                  onChange={e => setRankingMetric(e.target.value)}
                  className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white"
                >
                  <option value="rides_per_scheduled_hour">Rides per Scheduled Hour</option>
                  <option value="rides_per_scheduled_trip">Rides per Scheduled Trip</option>
                  <option value="total_rides">Total Observed Boardings</option>
                </select>
              </div>
            </div>

            <ChartPanel title="Top 8 Eligible Routes" subtitle={`Eligible routes ranked by ${rankingMetric.replaceAll('_', ' ')} • ${dayType === 'W' ? 'Weekday' : dayType === 'A' ? 'Saturday' : 'Sunday / Holiday'}`}>
              <HorizontalBarChart data={[...rankings].filter(r => r.is_eligible).sort((a, b) => Number(b[rankingMetric as keyof RankingRow] || 0) - Number(a[rankingMetric as keyof RankingRow] || 0)).slice(0, 8).map((r, i) => ({ label: `Route ${r.route}${r.route === selectedRoute ? ' ★' : ''}`, value: Number(r[rankingMetric as keyof RankingRow] || 0), color: r.route === selectedRoute ? '#22d3ee' : i === 0 ? '#34d399' : '#64748b' }))} suffix={rankingMetric === 'total_rides' ? ' rides' : ''} />
            </ChartPanel>

            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-slate-800 text-[11px] uppercase tracking-wider text-slate-400">
                    <th className="py-3 px-3">Rank</th>
                    <th className="py-3 px-3">Route</th>
                    <th className="py-3 px-3">Observed Days</th>
                    <th className="py-3 px-3 text-right">Rides / Sched. Hour</th>
                    <th className="py-3 px-3 text-right">Rides / Sched. Trip</th>
                    <th className="py-3 px-3 text-right">Total Matched Rides</th>
                    <th className="py-3 px-3">Eligibility Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 text-sm">
                  {rankings.slice(0, 25).map(row => (
                    <tr key={`${row.route}-${row.daytype}`} className="hover:bg-cyan-500/5">
                      <td className="py-2.5 px-3 font-display font-bold text-cyan-400">
                        {row.is_eligible && row.service_productivity_rank ? `#${row.service_productivity_rank}` : '—'}
                      </td>
                      <td className="py-2.5 px-3 font-semibold text-white">Route {row.route}</td>
                      <td className="py-2.5 px-3 text-slate-300">{row.observed_days} days</td>
                      <td className="py-2.5 px-3 text-right font-semibold text-emerald-300">
                        {row.rides_per_scheduled_hour ?? 'Unavailable'}
                      </td>
                      <td className="py-2.5 px-3 text-right text-slate-200">
                        {row.rides_per_scheduled_trip ?? 'Unavailable'}
                      </td>
                      <td className="py-2.5 px-3 text-right text-slate-300">{row.total_rides.toLocaleString()}</td>
                      <td className="py-2.5 px-3">
                        <span className={`text-xs px-2 py-0.5 rounded-full border ${
                          row.is_eligible
                            ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                            : 'bg-amber-500/10 border-amber-500/30 text-amber-300'
                        }`}>
                          {row.eligibility_reason}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* =========================================================
            SCREEN 3: ROUTE DETAIL & INTERACTIVE LEAFLET MAP
           ========================================================= */}
        {activeTab === 'detail' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 glass-panel rounded-2xl p-5 flex flex-col">
              <div className="flex items-center justify-between mb-3">
                <div>
                  <h2 className="font-display text-base font-bold text-white">Route {selectedRoute} Geography & Alignment</h2>
                  <p className="text-xs text-slate-400">
                    Geometry Version: <span className="text-cyan-300">{routeHistory?.geometry_version || 'google_transit_2026_09'}</span>
                  </p>
                </div>
                {routeHistory?.coverage && (
                  <div className="text-right text-xs">
                    <span className="text-slate-400">Served Stops: </span>
                    <strong className="text-white">{routeHistory.coverage.served_stop_count}</strong>
                    <span className="mx-2 text-slate-600">|</span>
                    <span className="text-slate-400">Exclusive: </span>
                    <strong className="text-cyan-300">{(routeHistory.coverage.exclusive_stop_fraction * 100).toFixed(1)}%</strong>
                  </div>
                )}
              </div>
              <div ref={mapContainerRef} className="w-full h-80 rounded-xl border border-slate-700/80 z-10" />
            </div>

            {/* Recent Observations Panel */}
            <div className="glass-panel rounded-2xl p-5 flex flex-col justify-between">
              <div>
                <h3 className="font-display text-base font-bold text-white mb-1">Recent Matched Observations</h3>
                <p className="text-xs text-slate-400 mb-4">Exact route/date join against dated GTFS archives</p>
                <div className="space-y-2.5 max-h-72 overflow-y-auto pr-1">
                  {(routeHistory?.history || []).slice(-8).reverse().map((h: any, idx: number) => (
                    <div key={idx} className="p-3 rounded-xl bg-slate-900/80 border border-slate-800 flex justify-between items-center text-xs">
                      <div>
                        <p className="font-semibold text-slate-200">{h.service_date} ({h.daytype})</p>
                        <p className="text-slate-400 mt-0.5">Snapshot: {h.source_snapshot}</p>
                      </div>
                      <div className="text-right">
                        <p className="font-display font-bold text-cyan-300">{h.rides?.toLocaleString()} rides</p>
                        <p className="text-slate-400">{h.scheduled_trips ?? 'N/A'} trips/day</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
              <button
                onClick={() => setActiveTab('scenarios')}
                className="mt-4 w-full py-2.5 rounded-xl bg-gradient-to-r from-cyan-500 to-violet-600 text-slate-950 font-display font-bold text-xs uppercase tracking-wider hover:opacity-95 transition"
              >
                Simulate Frequency Scenario for Route {selectedRoute}
              </button>
            </div>
          </div>
        )}

        {activeTab === 'detail' && (
          <ChartPanel title={`Route ${selectedRoute} ridership trend`} subtitle="Historical matched daily boardings from the selected route history">
            <TrendLineChart data={routeHistory?.history || []} />
          </ChartPanel>
        )}

        {/* =========================================================
            SCREEN 4: COMPARE ROUTES & CORRIDOR OVERLAP
           ========================================================= */}
        {activeTab === 'compare' && (
          <div className="glass-panel rounded-2xl p-6 space-y-6">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <h2 className="font-display text-lg font-bold text-white">Corridor & Route Comparison</h2>
                <p className="text-xs text-slate-400">Side-by-side demand/service profile and structural stop overlap (Section 9.7)</p>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-xs text-cyan-300 font-semibold">Route {selectedRoute}</span>
                <span className="text-xs text-slate-500">vs.</span>
                <select
                  value={compareRouteB}
                  onChange={e => setCompareRouteB(e.target.value)}
                  className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white"
                >
                  {routes.filter(r => r.route !== selectedRoute).map(r => (
                    <option key={r.route} value={r.route}>Route {r.route}</option>
                  ))}
                </select>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="p-4 rounded-xl bg-slate-900/80 border border-cyan-500/30">
                <p className="text-xs text-cyan-400 font-semibold">Route {selectedRoute} ({dayType})</p>
                <p className="font-display text-xl font-bold mt-2">
                  {compareData?.route_a?.profile?.rides_per_scheduled_hour ?? 'N/A'} <span className="text-xs font-normal text-slate-400">rides/hr</span>
                </p>
                <p className="text-xs text-slate-400 mt-1">
                  Total Rides: {compareData?.route_a?.profile?.total_rides?.toLocaleString() ?? 'N/A'}
                </p>
              </div>

              <div className="p-4 rounded-xl bg-slate-900/80 border border-fuchsia-500/30 flex flex-col justify-center items-center text-center">
                <p className="text-xs uppercase tracking-wider text-fuchsia-300">Stop-Set Overlap</p>
                <p className="font-display text-2xl font-bold text-white mt-1">
                  {compareData?.overlap?.shared_stop_count ?? 0} Shared Stops
                </p>
                <p className="text-xs text-slate-400 mt-1">
                  Jaccard: {((compareData?.overlap?.jaccard_overlap ?? 0) * 100).toFixed(1)}% • Smaller-Route: {((compareData?.overlap?.smaller_route_overlap ?? 0) * 100).toFixed(1)}%
                </p>
              </div>

              <div className="p-4 rounded-xl bg-slate-900/80 border border-violet-500/30">
                <p className="text-xs text-violet-400 font-semibold">Route {compareRouteB} ({dayType})</p>
                <p className="font-display text-xl font-bold mt-2">
                  {compareData?.route_b?.profile?.rides_per_scheduled_hour ?? 'N/A'} <span className="text-xs font-normal text-slate-400">rides/hr</span>
                </p>
                <p className="text-xs text-slate-400 mt-1">
                  Total Rides: {compareData?.route_b?.profile?.total_rides?.toLocaleString() ?? 'N/A'}
                </p>
              </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
              <ChartPanel title="Service productivity comparison" subtitle="Rides carried per scheduled service hour">
                <ComparisonBars labels={[`Route ${selectedRoute}`, `Route ${compareRouteB}`]} values={[Number(compareData?.route_a?.profile?.rides_per_scheduled_hour), Number(compareData?.route_b?.profile?.rides_per_scheduled_hour)]} suffix=" rides/hr" />
              </ChartPanel>
              <ChartPanel title="Total ridership comparison" subtitle="Matched total rides for the selected day type">
                <ComparisonBars labels={[`Route ${selectedRoute}`, `Route ${compareRouteB}`]} values={[Number(compareData?.route_a?.profile?.total_rides), Number(compareData?.route_b?.profile?.total_rides)]} colors={['#22d3ee', '#a78bfa']} suffix=" rides" />
              </ChartPanel>
            </div>
            <ChartPanel title="Shared-stop overlap" subtitle="Structural overlap between the two route stop sets">
              <ComparisonBars labels={['Jaccard overlap', 'Smaller-route overlap']} values={[Number(compareData?.overlap?.jaccard_overlap ?? 0) * 100, Number(compareData?.overlap?.smaller_route_overlap ?? 0) * 100]} colors={['#d946ef', '#8b5cf6']} suffix="%" />
            </ChartPanel>
          </div>
        )}

        {/* =========================================================
            SCREEN 5: HISTORICAL REPLAY & FORECASTING (Section 9.14)
           ========================================================= */}
        {activeTab === 'replay' && (
          <div className="space-y-6">
            {/* Virtual Clock Controller */}
            <div className="glass-panel rounded-2xl p-5 border border-cyan-400/30 flex flex-wrap items-center justify-between gap-4">
              <div>
                <div className="flex items-center gap-2">
                  <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase bg-fuchsia-500/20 text-fuchsia-300 border border-fuchsia-500/40">
                    Historical Replay Simulation
                  </span>
                  <span className="text-xs text-slate-400">Policy: 1-day reporting delay • Frozen XGBoost Option 2</span>
                </div>
                <div className="flex items-baseline gap-3 mt-2">
                  <h2 className="font-display text-2xl font-bold text-white">Virtual Date: {replaySession.virtual_date}</h2>
                  <span className="text-xs text-cyan-300">Permitted History ≤ {replayForecast?.latest_permitted_ride_date || '2026-05-31'}</span>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={() => handleReplayControl(replaySession.status === 'running' ? 'pause' : 'start')}
                  className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-cyan-500 text-slate-950 font-bold text-xs hover:bg-cyan-400 transition"
                >
                  {replaySession.status === 'running' ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
                  {replaySession.status === 'running' ? 'Pause' : 'Start Replay'}
                </button>
                <button
                  onClick={() => handleReplayControl('advance')}
                  className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-white text-xs font-medium border border-slate-700"
                >
                  <SkipForward className="w-4 h-4" /> +1 Day
                </button>
                <button
                  onClick={() => handleReplayControl('reset')}
                  className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium border border-slate-700"
                >
                  <RotateCcw className="w-4 h-4" /> Reset
                </button>
              </div>
            </div>

            {/* Active Route Prediction Card */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="glass-panel rounded-2xl p-5">
                <p className="text-xs text-slate-400">Predicted Daily Rides (Route {selectedRoute})</p>
                <p className="font-display text-3xl font-bold text-cyan-300 mt-2">
                  {replayForecast?.status === 'predicted'
                    ? `${Math.round(replayForecast.predicted_rides).toLocaleString()} rides`
                    : replayForecast?.status || 'Ready'}
                </p>
                <p className="text-xs text-slate-400 mt-1">
                  {replayForecast?.reason || `28-Day Lag Donor Flag: ${replayForecast?.rides_28_days_before_available ?? 1}`}
                </p>
              </div>

              <div className="glass-panel rounded-2xl p-5">
                <p className="text-xs text-slate-400">Planned Schedule (GTFS Snapshot)</p>
                <p className="font-display text-3xl font-bold text-violet-300 mt-2">
                  {replayForecast?.scheduled_trips ?? 'N/A'} <span className="text-sm font-normal text-slate-400">trips/day</span>
                </p>
                <p className="text-xs text-slate-400 mt-1">
                  Forecast Rides / Trip: {replayForecast?.predicted_rides_per_trip ?? 'N/A'}
                </p>
              </div>

              <div className="glass-panel rounded-2xl p-5">
                <p className="text-xs text-slate-400">Target Actual Outcome Revelation</p>
                <p className="font-display text-xl font-bold text-amber-300 mt-2">
                  {replayForecast?.actual_rides != null ? `${replayForecast.actual_rides.toLocaleString()} rides` : 'Withheld Until Day Completes'}
                </p>
                <p className="text-xs text-slate-400 mt-1">Anti-leakage gate enforced by backend</p>
              </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
              <ChartPanel title="Replay Demand & Schedule" subtitle="Predicted rides and matched scheduled trips for the current virtual date">
                <ComparisonBars labels={['Predicted daily rides', 'Scheduled trips/day']} values={[Number(replayForecast?.predicted_rides), Number(replayForecast?.scheduled_trips)]} colors={['#22d3ee', '#a78bfa']} />
                <p className="mt-3 text-[10px] text-slate-500">Different units are shown together for a compact operational snapshot; compare values within each metric, not as a common scale.</p>
              </ChartPanel>
              <ChartPanel title="Session Forecast Trail" subtitle="Forecasts recorded as the replay advances through virtual dates">
                <ForecastTrailChart entries={replayLog} />
              </ChartPanel>
            </div>
          </div>
        )}

        {/* =========================================================
            SCREEN 6: CONDITIONAL SERVICE SCENARIOS (Section 9.15)
           ========================================================= */}
        {activeTab === 'scenarios' && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="glass-panel rounded-2xl p-6 space-y-5">
              <div>
                <span className="text-[10px] uppercase tracking-wider px-2.5 py-0.5 rounded-full bg-amber-500/15 text-amber-300 border border-amber-500/30">
                  Scenario Assumption Engine
                </span>
                <h2 className="font-display text-lg font-bold text-white mt-2">Route {selectedRoute} Service Adjustment</h2>
                <p className="text-xs text-slate-400">
                  Evaluates conditional arithmetic holding demand fixed unless an explicit stress parameter is applied.
                </p>
              </div>

              <div className="space-y-4">
                <div>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-slate-300">Proposed Scheduled Trips/Day</span>
                    <span className="font-bold text-cyan-300">{scenProposedTrips} trips (Baseline: {scenBaselineTrips})</span>
                  </div>
                  <input
                    type="range"
                    min={Math.max(10, Math.round(scenBaselineTrips * 0.5))}
                    max={Math.round(scenBaselineTrips * 1.8)}
                    value={scenProposedTrips}
                    onChange={e => setScenProposedTrips(Number(e.target.value))}
                    className="w-full accent-cyan-400"
                  />
                </div>

                <div>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-slate-300">Hypothetical Demand Stress (%)</span>
                    <span className="font-bold text-fuchsia-300">{scenDemandStress >= 0 ? `+${scenDemandStress}%` : `${scenDemandStress}%`}</span>
                  </div>
                  <input
                    type="range"
                    min={-30}
                    max={50}
                    step={5}
                    value={scenDemandStress}
                    onChange={e => setScenDemandStress(Number(e.target.value))}
                    className="w-full accent-fuchsia-400"
                  />
                </div>
              </div>

              <button
                onClick={saveScenario}
                className="w-full py-2.5 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-display font-bold text-xs uppercase tracking-wider transition"
              >
                Save Scenario & Log Assumptions
              </button>
            </div>

            {/* Baseline vs Scenario Comparison Table */}
            <div className="glass-panel rounded-2xl p-6 flex flex-col justify-between">
              <div>
                <h3 className="font-display text-base font-bold text-white mb-4">Baseline vs. Scenario Output</h3>
                <table className="w-full text-sm text-left">
                  <thead>
                    <tr className="border-b border-slate-800 text-xs text-slate-400">
                      <th className="py-2">Metric</th>
                      <th className="py-2 text-right">Baseline</th>
                      <th className="py-2 text-right text-cyan-300">Scenario</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60">
                    <tr>
                      <td className="py-2.5 text-slate-300">Daily Rides (Assumed/Forecast)</td>
                      <td className="py-2.5 text-right">{Math.round(scenBaselineRides).toLocaleString()}</td>
                      <td className="py-2.5 text-right font-semibold text-white">{Math.round(stressedRides).toLocaleString()}</td>
                    </tr>
                    <tr>
                      <td className="py-2.5 text-slate-300">Scheduled Trips / Day</td>
                      <td className="py-2.5 text-right">{scenBaselineTrips}</td>
                      <td className="py-2.5 text-right font-semibold text-cyan-300">{scenProposedTrips}</td>
                    </tr>
                    <tr>
                      <td className="py-2.5 text-slate-300">Scheduled Trip-Hours (at {meanDurMins.toFixed(1)}m/trip)</td>
                      <td className="py-2.5 text-right">{scenBaselineHours} hrs</td>
                      <td className="py-2.5 text-right font-semibold text-cyan-300">{scenarioHours} hrs</td>
                    </tr>
                    <tr>
                      <td className="py-2.5 text-slate-300">Rides per Scheduled Trip</td>
                      <td className="py-2.5 text-right">{baseRidesPerTrip}</td>
                      <td className="py-2.5 text-right font-bold text-emerald-300">{scenRidesPerTrip}</td>
                    </tr>
                    <tr>
                      <td className="py-2.5 text-slate-300">Rides per Scheduled Hour</td>
                      <td className="py-2.5 text-right">{baseRidesPerHour}</td>
                      <td className="py-2.5 text-right font-bold text-emerald-300">{scenRidesPerHour}</td>
                    </tr>
                  </tbody>
                </table>
                <div className="mt-6 border-t border-slate-800 pt-5">
                  <h4 className="mb-4 text-xs font-bold uppercase tracking-wider text-slate-300">Visual scenario comparison</h4>
                  <div className="space-y-5">
                    <ComparisonBars labels={['Baseline rides', 'Scenario rides']} values={[scenBaselineRides, stressedRides]} colors={['#64748b', '#22d3ee']} />
                    <ComparisonBars labels={['Baseline trips', 'Proposed trips']} values={[scenBaselineTrips, scenProposedTrips]} colors={['#64748b', '#a78bfa']} />
                    <ComparisonBars labels={['Baseline rides / trip', 'Proposed rides / trip']} values={[Number(baseRidesPerTrip), Number(scenRidesPerTrip)]} colors={['#f59e0b', '#34d399']} suffix=" rides/trip" />
                  </div>
                </div>
              </div>

              <div className="mt-4 p-3 rounded-xl bg-slate-900/90 border border-slate-800 text-[11px] text-slate-400">
                <strong>Interpretation Limit:</strong> Conditional arithmetic only. Does not verify vehicle/crew availability or measure real-time onboard occupancy.
              </div>
            </div>
          </div>
        )}

        {/* =========================================================
            SCREEN 7: DATA PROVENANCE & RECONCILIATION AUDIT
           ========================================================= */}
        {activeTab === 'coverage' && (
          <div className="glass-panel rounded-2xl p-6 space-y-6">
            <div>
              <h2 className="font-display text-lg font-bold text-white">Source Provenance & Directional Reconciliation</h2>
              <p className="text-xs text-slate-400 mt-0.5">Exact audit records from Section 9.6.4 and Option 2 model pipeline metadata</p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 space-y-2 text-xs">
                <h3 className="font-display font-bold text-cyan-300 text-sm mb-2">Schedule & Ridership Reconciliation</h3>
                <div className="flex justify-between py-1 border-b border-slate-800/80">
                  <span className="text-slate-400">Matched Route/Date Observations</span>
                  <span className="font-bold text-emerald-300">28,374 (251 dates, 125 routes)</span>
                </div>
                <div className="flex justify-between py-1 border-b border-slate-800/80">
                  <span className="text-slate-400">Scheduled Service Without Rides</span>
                  <span className="font-bold text-amber-300">24 rows (Route 169 — kept missing, not zero)</span>
                </div>
                <div className="flex justify-between py-1 border-b border-slate-800/80">
                  <span className="text-slate-400">Rides Without Selected Schedule</span>
                  <span className="font-bold text-amber-300">424 rows (incl. Route 1001, 19, 130, 10)</span>
                </div>
                <div className="flex justify-between py-1">
                  <span className="text-slate-400">Active Geometry Snapshot</span>
                  <span className="font-mono text-slate-200">google_transit_2026_09</span>
                </div>
              </div>

              <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 space-y-2 text-xs">
                <h3 className="font-display font-bold text-violet-300 text-sm mb-2">Model & Policy Contract</h3>
                <div className="flex justify-between py-1 border-b border-slate-800/80">
                  <span className="text-slate-400">Selected Regressor</span>
                  <span className="font-bold text-white">XGBoost (xgb_option2_v1.0)</span>
                </div>
                <div className="flex justify-between py-1 border-b border-slate-800/80">
                  <span className="text-slate-400">Missing History Policy</span>
                  <span className="text-cyan-300">Option 2 (D-01): 28d Donor Fill + Flag</span>
                </div>
                <div className="flex justify-between py-1 border-b border-slate-800/80">
                  <span className="text-slate-400">Validation / Test WAPE</span>
                  <span className="text-emerald-300">6.45% Val / 6.73% Test</span>
                </div>
                <div className="flex justify-between py-1">
                  <span className="text-slate-400">Validation / Test R²</span>
                  <span className="text-emerald-300">98.72% Val / 98.37% Test</span>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
              <ChartPanel title="Data reconciliation exceptions" subtitle="Rows retained as exceptions rather than silently converted to zero">
                <HorizontalBarChart data={[{ label: 'Schedule only', value: 24, color: '#f59e0b' }, { label: 'Rides only', value: 424, color: '#f97316' }]} suffix=" rows" />
              </ChartPanel>
              <ChartPanel title="Model evaluation metrics" subtitle="Reported validation and test metrics from the current model contract">
                <ComparisonBars labels={['Validation R²', 'Test R²']} values={[98.72, 98.37]} colors={['#34d399', '#22d3ee']} suffix="%" />
                <div className="mt-5">
                  <ComparisonBars labels={['Validation WAPE', 'Test WAPE']} values={[6.45, 6.73]} colors={['#a78bfa', '#f472b6']} suffix="%" />
                </div>
              </ChartPanel>
            </div>
            <ChartPanel title="Audit Volume Overview" subtitle="Matched observations compared with retained reconciliation exceptions">
              <HorizontalBarChart data={[
                { label: 'Matched rows', value: 28374, color: '#34d399' },
                { label: 'Schedule only', value: 24, color: '#f59e0b' },
                { label: 'Rides only', value: 424, color: '#f97316' }
              ]} suffix=" rows" maxItems={3} />
            </ChartPanel>
          </div>
        )}
      </main>
    </div>
  );
}