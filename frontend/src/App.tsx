import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import React, { useState, useEffect, useRef } from 'react';
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
    if (activeTab !== 'detail' || !mapContainerRef.current || !(window as any).L) return;
    const L = (window as any).L;

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
    <div className="min-h-screen bg-[#070B14] bg-grid-pattern text-slate-100 flex flex-row app-shell">
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
      <header className="sidebar sticky top-0 z-40 border-r border-slate-800/90 px-5 py-6 flex flex-col">
        <div className="sidebar-brand flex flex-col items-start gap-6">
          <div className="flex items-center gap-3">
            <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-cyan-400 to-violet-600 flex items-center justify-center shadow-lg shadow-cyan-500/20">
              <Bus className="w-5 h-5 text-slate-950" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="font-display font-extrabold text-xl tracking-wide text-white">Route<span className="text-cyan-400">Ranker</span></h1>
                <span className="text-[10px] uppercase tracking-widest px-2 py-0.5 rounded-full bg-cyan-500/15 text-cyan-300 border border-cyan-400/30">
                  CTA v3.8
                </span>
              </div>
              <p className="text-[11px] text-slate-500 mt-1">CHICAGO TRANSIT INTELLIGENCE</p>
            </div>
          </div>

          {/* Global Selectors */}
          <div className="sidebar-controls flex flex-col items-stretch gap-3 w-full">
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

            <div className="flex flex-wrap rounded-lg bg-slate-900/90 p-1 border border-slate-700/70">
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

            <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs border ${
              backendOnline
                ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                : 'bg-amber-500/10 border-amber-500/30 text-amber-300'
            }`}>
              <span className={`w-2 h-2 rounded-full ${backendOnline ? 'bg-emerald-400 animate-pulse' : 'bg-amber-400'}`} />
              {backendOnline ? 'API Connected' : 'Offline Reference'}
            </div>
          </div>
        </div>

        {/* Screen Navigation Tabs (Section 9.16.2) */}
        <div className="sidebar-section-label mt-9 mb-3 text-[10px] font-bold uppercase tracking-[0.2em] text-slate-600">Workspace</div>
        <nav className="sidebar-nav flex flex-col gap-1">
          {[
            { id: 'overview', label: 'Network Overview', icon: Activity },
            { id: 'rankings', label: 'Productivity Rankings', icon: TrendingUp },
            { id: 'detail', label: 'Route Intelligence', icon: Compass },
            { id: 'compare', label: 'Route Comparison', icon: GitCompare },
            { id: 'replay', label: 'Historical Replay', icon: Play },
            { id: 'scenarios', label: 'Scenario Simulator', icon: Sliders },
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
                <Icon className="w-4 h-4" />
                {tab.label}
              </button>
            );
          })}
        </nav>
        <div className="sidebar-footer mt-auto pt-6 border-t border-slate-800/80">
          <div className="flex items-center gap-2 text-xs text-slate-500"><span className="w-2 h-2 rounded-full bg-cyan-400" /> RouteRanker Analytics</div>
          <p className="text-[10px] text-slate-600 mt-2">CTA DATA • GTFS + HISTORICAL RIDERSHIP</p>
        </div>
      </header>

      {/* Main Content Container */}
      <main className="main-content flex-1 min-w-0 w-full px-7 py-7 space-y-6">
        <div className="page-heading flex flex-wrap items-end justify-between gap-4">
          <div><p className="text-[11px] uppercase tracking-[0.22em] text-cyan-400 font-bold">Transit intelligence platform</p><h2 className="text-2xl md:text-3xl font-extrabold tracking-tight text-white mt-1">{({ overview: 'Network overview', rankings: 'Productivity rankings', detail: 'Route intelligence', compare: 'Route comparison', replay: 'Historical replay', scenarios: 'Scenario simulator', coverage: 'Data & coverage' } as Record<ScreenTab, string>)[activeTab]}</h2><p className="text-sm text-slate-500 mt-1">Explore demand patterns, scheduled service and network performance.</p></div>
          <div className="text-xs text-slate-500 border border-slate-800 bg-slate-900/60 rounded-lg px-3 py-2">Chicago Transit Authority <span className="text-slate-700 mx-1">/</span> Research workspace</div>
        </div>
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
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-stretch">
            <div className="lg:col-span-2 glass-panel rounded-2xl p-5 flex flex-col min-h-[680px]">
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
              <div
                ref={mapContainerRef}
                className="w-full flex-1 min-h-[560px] h-[65vh] rounded-xl border border-slate-700/80 z-10"
                style={{ minHeight: '560px' }}
              />
            </div>

            {/* Recent Observations Panel */}
            <div className="glass-panel rounded-2xl p-5 flex flex-col justify-between min-h-[680px]">
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
          </div>
        )}
      </main>
    </div>
  );
}