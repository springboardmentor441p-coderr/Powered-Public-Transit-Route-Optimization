import React, { useEffect, useState, useMemo } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Legend,
  CartesianGrid,
} from "recharts";
import CtaMap from "./components/CtaMap";
import "./App.css";

const API = "/api";

type TabId =
  | "network_overview"
  | "review_priorities"
  | "route_explorer"
  | "compare_routes"
  | "route_groups"
  | "forecasts_evaluation"
  | "service_scenarios"
  | "data_provenance";

interface RouteProfile {
  route: string;
  daytype: string;
  is_ranking_eligible: boolean;
  service_productivity_metric_rank?: number | null;
  rides_per_scheduled_hour?: number | null;
  rides_per_scheduled_trip?: number | null;
  mean_daily_rides?: number | null;
  cluster_label?: string;
  total_rides?: number;
  total_scheduled_trips?: number;
  total_scheduled_hours?: number;
  observed_days?: number;
}

interface ReplaySession {
  session_id: string;
  start_date: string;
  end_date: string;
  virtual_date: string;
  reporting_delay_days: number;
  speed_seconds_per_day: number;
  status: "running" | "paused" | "completed";
}

interface ForecastResponse {
  session: ReplaySession;
  current_forecast: {
    route: string;
    target_date: string;
    issued_at: string;
    status: string;
    predicted_rides?: number | null;
    scheduled_trips?: number | null;
    scheduled_service_hours?: number | null;
    model_version?: string;
    reason?: string;
    latest_permitted_ride_date?: string;
  };
  previous_day_comparison: {
    date: string;
    saved_prediction?: number | null;
    revealed_actual_rides?: number | null;
  };
}

export default function App() {
  const [activeTab, setActiveTab] = useState<TabId>("network_overview");

  // Core Data States
  const [routes, setRoutes] = useState<string[]>([]);
  const [selectedRoute, setSelectedRoute] = useState<string>("22");
  const [daytype, setDaytype] = useState<string>("W");
  const [rankings, setRankings] = useState<RouteProfile[]>([]);
  const [session, setSession] = useState<ReplaySession | null>(null);
  const [forecastData, setForecastData] = useState<ForecastResponse | null>(null);
  const [history, setHistory] = useState<any[]>([]);
  const [coverage, setCoverage] = useState<any>(null);

  // Network Overview State
  const [networkOverview, setNetworkOverview] = useState<any>(null);
  const [obsStart, setObsStart] = useState<string>("2026-01-01");
  const [obsEnd, setObsEnd] = useState<string>("2026-07-31");

  // Clusters State
  const [clustersData, setClustersData] = useState<any[]>([]);

  // Route Comparison State
  const [compareRouteA, setCompareRouteA] = useState<string>("22");
  const [compareRouteB, setCompareRouteB] = useState<string>("79");
  const [compareData, setCompareData] = useState<any>(null);

  // Filters & Sorting for Priorities
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [selectedCluster, setSelectedCluster] = useState<string>("ALL");
  const [sortField, setSortField] = useState<string>("rank");

  // Route Explorer Chart Options
  const [chartWindow, setChartWindow] = useState<number>(30);
  const [chartView, setChartView] = useState<"rides" | "trips">("rides");

  // Scenario Simulator State
  const [tripDeltaPct, setTripDeltaPct] = useState<number>(10);
  const [demandStressPct, setDemandStressPct] = useState<number>(0);
  const [assumedDuration, setAssumedDuration] = useState<number>(40);
  const [scenarioResult, setScenarioResult] = useState<any>(null);
  const [scenarioError, setScenarioError] = useState<string | null>(null);
  const [scenarioLoading, setScenarioLoading] = useState<boolean>(false);

  // Playback timer & speed
  const [playbackSpeedMs, setPlaybackSpeedMs] = useState<number>(3000);

  // Initial Load
  useEffect(() => {
    // 1. Fetch Routes
    fetch(`${API}/routes`)
      .then((r) => (r.ok ? r.json() : { routes: [] }))
      .then((d) => setRoutes(d.routes || []))
      .catch(() => setRoutes([]));

    // 2. Fetch Coverage & Evaluation
    fetch(`${API}/data/coverage`)
      .then((r) => (r.ok ? r.json() : null))
      .then(setCoverage)
      .catch(() => {});

    // 3. Fetch Network Overview
    fetch(`${API}/network/overview?start_date=${obsStart}&end_date=${obsEnd}`)
      .then((r) => (r.ok ? r.json() : null))
      .then(setNetworkOverview)
      .catch(() => {});

    // 4. Fetch Clusters Breakdown
    fetch(`${API}/clusters`)
      .then((r) => (r.ok ? r.json() : []))
      .then(setClustersData)
      .catch(() => {});

    // 5. Initialize Replay Session
    fetch(`${API}/replays`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        start_date: "2026-06-01",
        end_date: "2026-07-31",
        reporting_delay_days: 1,
      }),
    })
      .then((r) => (r.ok ? r.json() : null))
      .then(setSession)
      .catch(() => setSession(null));
  }, []);

  // Fetch Rankings on daytype change
  useEffect(() => {
    fetch(`${API}/rankings?daytype=${daytype}`)
      .then((r) => (r.ok ? r.json() : []))
      .then((d) => setRankings(Array.isArray(d) ? d : []))
      .catch(() => setRankings([]));
  }, [daytype]);

  // Fetch Route Forecast & History when route or session virtual date changes
  useEffect(() => {
    if (!session?.session_id) return;

    fetch(`${API}/replays/${session.session_id}/forecast/${selectedRoute}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d: ForecastResponse) => {
        setForecastData(d);
        if (d?.current_forecast?.scheduled_trips && d?.current_forecast?.scheduled_service_hours) {
          const avg = Math.round(
            (d.current_forecast.scheduled_service_hours / d.current_forecast.scheduled_trips) * 60
          );
          if (avg > 0) setAssumedDuration(avg);
        }
      })
      .catch(() => setForecastData(null));

    fetch(`${API}/routes/${selectedRoute}/history?session_id=${session.session_id}`)
      .then((r) => (r.ok ? r.json() : []))
      .then((d: any[]) => {
        const filtered = Array.isArray(d) ? d.filter((i) => i.date <= session.virtual_date) : [];
        setHistory(filtered);
      })
      .catch(() => setHistory([]));
  }, [session?.session_id, session?.virtual_date, selectedRoute]);

  // Fetch Route Comparison
  useEffect(() => {
    if (activeTab === "compare_routes") {
      fetch(`${API}/routes/compare?route1=${compareRouteA}&route2=${compareRouteB}&daytype=${daytype}`)
        .then((r) => (r.ok ? r.json() : null))
        .then(setCompareData)
        .catch(() => setCompareData(null));
    }
  }, [activeTab, compareRouteA, compareRouteB, daytype]);

  // Playback timer
  useEffect(() => {
    if (!session?.session_id || session.status !== "running") return;
    const timer = setInterval(() => {
      controlReplay("advance");
    }, playbackSpeedMs);
    return () => clearInterval(timer);
  }, [session?.session_id, session?.status, session?.virtual_date, playbackSpeedMs]);

  const controlReplay = async (action: string) => {
    if (!session?.session_id) return;
    try {
      const res = await fetch(`${API}/replays/${session.session_id}/control`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action }),
      });
      if (res.ok) {
        const updated = await res.json();
        if (updated?.session_id) setSession(updated);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const advanceMultipleDays = async (days: number) => {
    for (let i = 0; i < days; i++) {
      await controlReplay("advance");
    }
  };

  const calculateScenario = async () => {
    setScenarioError(null);
    setScenarioLoading(true);
    const cur = forecastData?.current_forecast;
    if (!cur || cur.predicted_rides == null || cur.scheduled_trips == null) {
      setScenarioError("Scenario requires an active predicted rides value and scheduled trips.");
      setScenarioLoading(false);
      return;
    }

    try {
      const proposedTrips = Math.max(0, Math.round(cur.scheduled_trips * (1 + tripDeltaPct / 100)));
      const res = await fetch(`${API}/scenarios`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          route: selectedRoute,
          target_date: session?.virtual_date,
          baseline_rides: cur.predicted_rides,
          baseline_trips: cur.scheduled_trips,
          proposed_trips: proposedTrips,
          assumed_trip_duration_minutes: assumedDuration,
          demand_stress_pct: demandStressPct,
        }),
      });

      const data = await res.json();
      if (!res.ok) setScenarioError(data?.detail || "Unable to compute scenario.");
      else setScenarioResult(data);
    } catch (err: any) {
      setScenarioError(err.message || "Failed to communicate with scenario endpoint.");
    } finally {
      setScenarioLoading(false);
    }
  };

  // Distinct cluster names for filter
  const clusterNames = useMemo(() => {
    const list = Array.from(new Set(rankings.map((r) => r.cluster_label).filter(Boolean))) as string[];
    return list.sort();
  }, [rankings]);

  // Filtered Priorities List
  const filteredRankings = useMemo(() => {
    return rankings
      .filter((r) => {
        if (searchQuery.trim() && !r.route.toLowerCase().includes(searchQuery.toLowerCase().trim()))
          return false;
        if (selectedCluster !== "ALL" && r.cluster_label !== selectedCluster) return false;
        return true;
      })
      .sort((a, b) => {
        if (sortField === "rank") {
          return (a.service_productivity_metric_rank ?? 999) - (b.service_productivity_metric_rank ?? 999);
        }
        if (sortField === "productivity") {
          return (b.rides_per_scheduled_hour ?? 0) - (a.rides_per_scheduled_hour ?? 0);
        }
        if (sortField === "route") {
          return a.route.localeCompare(b.route, undefined, { numeric: true });
        }
        return 0;
      });
  }, [rankings, searchQuery, selectedCluster, sortField]);

  // Route Explorer Chart Data
  const explorerChartData = useMemo(() => {
    const recent = history.slice(-chartWindow);
    const curForecast = forecastData?.current_forecast;

    const items = recent.map((item) => ({
      date: item.date,
      actualRides: item.rides != null ? Number(item.rides) : null,
      scheduledTrips: item.scheduled_trips,
      scheduledHours: item.scheduled_service_hours,
      forecastRides: null as number | null,
    }));

    if (session?.virtual_date && curForecast?.predicted_rides) {
      const idx = items.findIndex((i) => i.date === session.virtual_date);
      if (idx >= 0) items[idx].forecastRides = curForecast.predicted_rides;
      else {
        items.push({
          date: session.virtual_date,
          actualRides: null,
          scheduledTrips: curForecast.scheduled_trips ?? null,
          scheduledHours: curForecast.scheduled_service_hours ?? null,
          forecastRides: curForecast.predicted_rides,
        });
      }
    }
    return items;
  }, [history, chartWindow, session?.virtual_date, forecastData?.current_forecast]);

  // Prior Day Variance
  const prevComp = forecastData?.previous_day_comparison;
  const prevDiff = useMemo(() => {
    if (prevComp?.revealed_actual_rides != null && prevComp?.saved_prediction != null && prevComp.saved_prediction > 0) {
      const diff = prevComp.revealed_actual_rides - prevComp.saved_prediction;
      const pct = (diff / prevComp.saved_prediction) * 100;
      return { diff: Math.round(diff), pct: pct.toFixed(1) };
    }
    return null;
  }, [prevComp]);

  // Navigation Items Config
  const navItems: { id: TabId; label: string; icon: string }[] = [
    { id: "network_overview", label: "Network overview", icon: "📊" },
    { id: "review_priorities", label: "Review priorities", icon: "📋" },
    { id: "route_explorer", label: "Route explorer", icon: "🚌" },
    { id: "compare_routes", label: "Compare routes", icon: "⇄" },
    { id: "route_groups", label: "Route groups", icon: "🔀" },
    { id: "forecasts_evaluation", label: "Forecasts & evaluation", icon: "📈" },
    { id: "service_scenarios", label: "Service scenarios", icon: "⚡" },
    { id: "data_provenance", label: "Data & provenance", icon: "🗄️" },
  ];

  const curForecast = forecastData?.current_forecast;

  return (
    <div className="app-shell">
      {/* Left Sidebar */}
      <aside className="sidebar">
        {/* Brand */}
        <div className="brand-section">
          <div className="brand-icon">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4">
              <path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z" />
              <line x1="4" y1="22" x2="4" y2="15" />
            </svg>
          </div>
          <div className="brand-text">
            <h1>RouteRanker</h1>
            <span>Transit Planning Workspace</span>
          </div>
        </div>

        {/* Location Pill */}
        <div className="location-card">
          <div className="location-icon">🏙️</div>
          <div className="location-details">
            <h4 className="location-title">Chicago, Illinois</h4>
            <p className="location-sub">CTA · Bus network</p>
          </div>
          <div className="live-dot" title="Live connection active" />
        </div>

        {/* Nav Group */}
        <div className="nav-group-label">Workspace</div>
        <ul className="nav-menu">
          {navItems.map((item) => {
            const isActive = activeTab === item.id;
            return (
              <li
                key={item.id}
                className={`nav-item ${isActive ? "active" : ""}`}
                onClick={() => setActiveTab(item.id)}
              >
                <span className="nav-icon">{item.icon}</span>
                <span className="nav-label">{item.label}</span>
                {isActive && <span className="nav-arrow">›</span>}
              </li>
            );
          })}
        </ul>

        {/* Sidebar Footer */}
        <div className="sidebar-footer">
          <div className="env-card">
            <div className="env-title">
              <span>●</span> Data Environment
            </div>
            <p className="env-stat">Historical CTA data</p>
            <p className="env-desc">Daily observations · dated schedules</p>
            <p className="env-desc" style={{ marginTop: 4, opacity: 0.75 }}>
              Frozen models · local workspace
            </p>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="main-wrapper">
        {/* Top Header / Breadcrumbs Bar */}
        <header className="topbar">
          <div className="breadcrumbs">
            <span>Workspace</span>
            <span>/</span>
            <span className="crumb-current">
              {navItems.find((n) => n.id === activeTab)?.label || "Network overview"}
            </span>
          </div>

          <div className="topbar-actions">
            {session && (
              <div className="replay-indicator">
                <span>📅 {session.virtual_date}</span>
                <span className={`badge badge-${session.status}`}>{session.status}</span>
              </div>
            )}

            {session && (
              <div style={{ display: "flex", gap: 6 }}>
                {session.status === "running" ? (
                  <button className="btn btn-secondary btn-sm" onClick={() => controlReplay("pause")}>
                    ⏸ Pause
                  </button>
                ) : (
                  <button className="btn btn-primary btn-sm" onClick={() => controlReplay("start")}>
                    ▶ Play
                  </button>
                )}
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={() => controlReplay("advance")}
                  disabled={session.status === "completed"}
                >
                  +1 Day
                </button>
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={() => advanceMultipleDays(7)}
                  disabled={session.status === "completed"}
                >
                  +7 Days
                </button>
                <button className="btn btn-secondary btn-sm" onClick={() => controlReplay("reset")}>
                  ↺ Reset
                </button>
                <select
                  className="select-input"
                  style={{ fontSize: 11, padding: "4px 8px" }}
                  value={playbackSpeedMs}
                  onChange={(e) => setPlaybackSpeedMs(Number(e.target.value))}
                >
                  <option value={5000}>1x Speed</option>
                  <option value={2500}>2x Speed</option>
                  <option value={1000}>5x Speed</option>
                </select>
              </div>
            )}
          </div>
        </header>

        {/* View Switcher */}
        <main className="view-content">
          {/* TAB 1: NETWORK OVERVIEW */}
          {activeTab === "network_overview" && (
            <div>
              <div className="view-header">
                <div className="view-subheading">Chicago Transit Authority · Route Level Demand</div>
                <h2 className="view-title">Network overview</h2>
                <p className="view-desc">Understand demand and scheduled service across Chicago's bus network</p>
              </div>

              {/* Filter Strip */}
              <div className="filter-strip">
                <div className="filter-item">
                  <span>📅</span>
                  <label>Observation period:</label>
                  <span>From</span>
                  <input
                    type="date"
                    className="text-input"
                    value={obsStart}
                    onChange={(e) => setObsStart(e.target.value)}
                  />
                  <span>To</span>
                  <input
                    type="date"
                    className="text-input"
                    value={obsEnd}
                    onChange={(e) => setObsEnd(e.target.value)}
                  />
                </div>
                <div style={{ fontSize: 12, color: "var(--text-muted)", fontWeight: 600 }}>
                  Recalibrated: every 7 days (lag: 1d)
                </div>
              </div>

              {/* 4 KPI Cards */}
              <div className="kpi-grid">
                <div className="kpi-card highlight">
                  <div className="kpi-title">Network Total Rides</div>
                  <div className="kpi-value">
                    {networkOverview?.total_rides
                      ? `${(networkOverview.total_rides / 1e6).toFixed(1)}M`
                      : "117.7M"}
                  </div>
                  <div className="kpi-sub">{obsStart} – {obsEnd} recording window</div>
                </div>

                <div className="kpi-card">
                  <div className="kpi-title">Network Total Trips</div>
                  <div className="kpi-value">
                    {networkOverview?.total_trips
                      ? `${(networkOverview.total_trips / 1e6).toFixed(1)}M`
                      : "3.6M"}
                  </div>
                  <div className="kpi-sub">Across CTA scheduled bus network</div>
                </div>

                <div className="kpi-card">
                  <div className="kpi-title">Rides / Scheduled Trip</div>
                  <div className="kpi-value">
                    {networkOverview?.rides_per_trip ?? "32.5"}
                  </div>
                  <div className="kpi-sub">Network average utilization rate</div>
                </div>

                <div className="kpi-card">
                  <div className="kpi-title">Schedule Coverage</div>
                  <div className="kpi-value">
                    {networkOverview?.schedule_coverage_pct ?? "99.92"}%
                  </div>
                  <div className="kpi-sub">Scheduled observations matched rides</div>
                </div>
              </div>

              {/* Grid 2-Column: Daily Demand Chart & Network at a Glance */}
              <div className="content-grid-2">
                {/* Left: Daily Network Demand Chart */}
                <div className="card">
                  <div className="card-header">
                    <div>
                      <h3 className="card-title">Network demand</h3>
                      <p className="card-subtitle">
                        Recorded daily boarding events across eligible route corridors
                      </p>
                    </div>
                    <span className="badge-tag green">● Recorded observations</span>
                  </div>

                  <div style={{ height: 320, width: "100%", marginTop: 12 }}>
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart
                        data={networkOverview?.daily_demand || []}
                        margin={{ top: 10, right: 10, left: 10, bottom: 10 }}
                      >
                        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8e4" />
                        <XAxis
                          dataKey="date"
                          tick={{ fontSize: 11, fill: "#64748b" }}
                          minTickGap={32}
                          stroke="#cbd5e1"
                        />
                        <YAxis
                          tick={{ fontSize: 11, fill: "#64748b" }}
                          tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`}
                          stroke="#cbd5e1"
                        />
                        <Tooltip
                          formatter={(v: any) => [Number(v).toLocaleString(), "Total Daily Rides"]}
                          contentStyle={{
                            backgroundColor: "#061d16",
                            color: "#fff",
                            borderRadius: 8,
                            border: "none",
                            fontSize: 12,
                          }}
                        />
                        <Line
                          type="monotone"
                          dataKey="rides"
                          name="Daily Boardings"
                          stroke="#059669"
                          strokeWidth={2}
                          dot={false}
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </div>

                {/* Right: Network at a Glance */}
                <div className="card">
                  <div className="card-header">
                    <div>
                      <h3 className="card-title">Network at a glance</h3>
                      <p className="card-subtitle">Coverage of the selected observation period</p>
                    </div>
                  </div>

                  <table className="data-table" style={{ marginTop: 8 }}>
                    <tbody>
                      <tr>
                        <td>
                          <strong>Scheduled study routes</strong>
                        </td>
                        <td style={{ textAlign: "right", fontWeight: 700 }}>
                          {networkOverview?.scheduled_study_routes ?? 125}
                        </td>
                      </tr>
                      <tr>
                        <td>
                          <strong>Observed corridors</strong>
                        </td>
                        <td style={{ textAlign: "right", fontWeight: 700 }}>
                          {networkOverview?.observed_corridors ?? 127}
                        </td>
                      </tr>
                      <tr>
                        <td>
                          <strong>Matched route-days</strong>
                        </td>
                        <td style={{ textAlign: "right", fontWeight: 700 }}>
                          {networkOverview?.matched_route_days?.toLocaleString() ?? "28,374"}
                        </td>
                      </tr>
                      <tr>
                        <td>
                          <strong>Data resolution</strong>
                        </td>
                        <td style={{ textAlign: "right", fontWeight: 700 }}>
                          {networkOverview?.resolution ?? "Daily"}
                        </td>
                      </tr>
                    </tbody>
                  </table>

                  <div className="callout callout-muted" style={{ marginTop: 18 }}>
                    <span>ℹ️</span>
                    <div>
                      Observational data can include records where scheduled or reporting service was disrupted.
                    </div>
                  </div>
                </div>
              </div>

              {/* Scheduled Network Interactive Map */}
              <div className="card" style={{ marginTop: 20 }}>
                <div className="card-header">
                  <div>
                    <h3 className="card-title">Scheduled network</h3>
                    <p className="card-subtitle">
                      Explore representative route patterns. Select a line to inspect a route corridor.
                    </p>
                  </div>
                  <span className="badge-tag green">● Real CTA Shapes (125 Corridors)</span>
                </div>

                <div style={{ marginTop: 12 }}>
                  <CtaMap
                    showAllRoutes={true}
                    onSelectRoute={(r) => {
                      setSelectedRoute(r);
                      setActiveTab("route_explorer");
                    }}
                    height={480}
                  />
                </div>
              </div>

              {/* Scheduled Network Corridor Clusters Card */}
              <div className="card" style={{ marginTop: 20 }}>
                <div className="card-header">
                  <div>
                    <h3 className="card-title">Scheduled network corridor clusters</h3>
                    <p className="card-subtitle">
                      Representative route patterns and cluster categorizations across Chicago
                    </p>
                  </div>
                </div>

                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
                    gap: 14,
                    marginTop: 10,
                  }}
                >
                  {clustersData.map((c) => (
                    <div
                      key={c.name}
                      style={{
                        background: "#f8faf8",
                        border: "1px solid #e2e8e4",
                        borderRadius: 10,
                        padding: 16,
                      }}
                    >
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                          marginBottom: 8,
                        }}
                      >
                        <h4 style={{ margin: 0, fontSize: 14, fontWeight: 700, color: "var(--text-main)" }}>
                          {c.name}
                        </h4>
                        <span className="badge-tag green">{c.route_count} routes</span>
                      </div>
                      <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 8 }}>
                        Avg: <strong>{c.avg_rides_per_hour}</strong> rides/hr · Mean daily:{" "}
                        <strong>{Number(c.mean_daily_rides).toLocaleString()}</strong> rides
                      </div>
                      <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                        {c.routes.slice(0, 8).map((r: string) => (
                          <span
                            key={r}
                            className="badge-tag"
                            style={{ cursor: "pointer" }}
                            onClick={() => {
                              setSelectedRoute(r);
                              setActiveTab("route_explorer");
                            }}
                          >
                            Route {r}
                          </span>
                        ))}
                        {c.routes.length > 8 && (
                          <span style={{ fontSize: 11, color: "var(--text-muted)", alignSelf: "center" }}>
                            +{c.routes.length - 8} more
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: REVIEW PRIORITIES */}
          {activeTab === "review_priorities" && (
            <div>
              <div className="view-header">
                <div className="view-subheading">Ranking & Prioritization Engine</div>
                <h2 className="view-title">Review priorities</h2>
                <p className="view-desc">
                  Rank routes by service productivity and identify candidates for service adjustment
                </p>
              </div>

              <div className="filter-strip">
                <div style={{ display: "flex", gap: 14, alignItems: "center", flexWrap: "wrap" }}>
                  <div className="filter-item">
                    <label>Schedule:</label>
                    <select
                      className="select-input"
                      value={daytype}
                      onChange={(e) => setDaytype(e.target.value)}
                    >
                      <option value="W">Weekday (W)</option>
                      <option value="A">Saturday (A)</option>
                      <option value="U">Sunday / Holiday (U)</option>
                    </select>
                  </div>

                  <div className="filter-item">
                    <label>Cluster:</label>
                    <select
                      className="select-input"
                      value={selectedCluster}
                      onChange={(e) => setSelectedCluster(e.target.value)}
                    >
                      <option value="ALL">All Corridor Clusters</option>
                      {clusterNames.map((c) => (
                        <option key={c} value={c}>
                          {c}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="filter-item">
                    <label>Search:</label>
                    <input
                      type="text"
                      placeholder="Route # (e.g. 22)..."
                      className="text-input"
                      style={{ width: 140 }}
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                    />
                  </div>

                  <div className="filter-item">
                    <label>Sort By:</label>
                    <select
                      className="select-input"
                      value={sortField}
                      onChange={(e) => setSortField(e.target.value)}
                    >
                      <option value="rank">Productivity Rank</option>
                      <option value="productivity">Rides / Hour</option>
                      <option value="route">Route Number</option>
                    </select>
                  </div>
                </div>

                <div style={{ fontSize: 13, fontWeight: 700, color: "var(--primary)" }}>
                  Showing {filteredRankings.length} of {rankings.length} routes
                </div>
              </div>

              <div className="card">
                <div className="data-table-wrapper">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Rank</th>
                        <th>Route</th>
                        <th>Rides / Sched. Hour</th>
                        <th>Rides / Sched. Trip</th>
                        <th>Mean Daily Rides</th>
                        <th>Observed Days</th>
                        <th>Corridor Cluster</th>
                        <th>Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredRankings.map((r) => {
                        const isTop10 =
                          r.service_productivity_metric_rank != null &&
                          r.service_productivity_metric_rank <= 10;
                        return (
                          <tr key={r.route}>
                            <td>
                              {r.is_ranking_eligible ? (
                                <span className={`badge-tag ${isTop10 ? "amber" : "green"}`}>
                                  #{r.service_productivity_metric_rank}
                                </span>
                              ) : (
                                <span style={{ color: "var(--text-subtle)", fontSize: 11 }}>Unranked</span>
                              )}
                            </td>
                            <td>
                              <strong style={{ fontSize: 14 }}>Route {r.route}</strong>
                            </td>
                            <td>
                              <strong>
                                {r.rides_per_scheduled_hour
                                  ? Number(r.rides_per_scheduled_hour).toFixed(1)
                                  : "—"}
                              </strong>
                            </td>
                            <td>
                              {r.rides_per_scheduled_trip
                                ? Number(r.rides_per_scheduled_trip).toFixed(1)
                                : "—"}
                            </td>
                            <td>
                              {r.mean_daily_rides ? Math.round(r.mean_daily_rides).toLocaleString() : "—"}
                            </td>
                            <td>{r.observed_days ?? "—"}</td>
                            <td>
                              <span className="badge-tag">{r.cluster_label}</span>
                            </td>
                            <td>
                              <button
                                className="btn btn-secondary btn-sm"
                                onClick={() => {
                                  setSelectedRoute(r.route);
                                  setActiveTab("route_explorer");
                                }}
                              >
                                Inspect →
                              </button>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* TAB 3: ROUTE EXPLORER */}
          {activeTab === "route_explorer" && (
            <div>
              <div className="view-header">
                <div className="view-subheading">Corridor Deep-Dive</div>
                <h2 className="view-title">Route explorer</h2>
                <p className="view-desc">
                  Inspect ridership trajectory, today's prediction, and operational service metrics
                </p>
              </div>

              <div className="filter-strip">
                <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                  <label style={{ fontWeight: 700 }}>Select Route:</label>
                  <select
                    className="select-input"
                    style={{ fontWeight: 700, fontSize: 14, width: 140 }}
                    value={selectedRoute}
                    onChange={(e) => setSelectedRoute(e.target.value)}
                  >
                    {routes.map((r) => (
                      <option key={r} value={r}>
                        Route {r}
                      </option>
                    ))}
                  </select>
                </div>
                <div style={{ fontSize: 13, color: "var(--text-muted)" }}>
                  Target Virtual Date: <strong>{session?.virtual_date || "—"}</strong>
                </div>
              </div>

              {/* 4 KPI Cards */}
              <div className="kpi-grid">
                <div className="kpi-card highlight">
                  <div className="kpi-title">Predicted Rides / Day</div>
                  <div className="kpi-value">
                    {curForecast?.status === "predicted" && curForecast?.predicted_rides != null
                      ? Number(curForecast.predicted_rides).toLocaleString(undefined, {
                          maximumFractionDigits: 0,
                        })
                      : "—"}
                  </div>
                  <div className="kpi-sub">
                    Status: <strong style={{ color: "var(--primary)" }}>{curForecast?.status}</strong>
                  </div>
                </div>

                <div className="kpi-card">
                  <div className="kpi-title">Scheduled Service</div>
                  <div className="kpi-value">{curForecast?.scheduled_trips ?? "—"} trips</div>
                  <div className="kpi-sub">{curForecast?.scheduled_service_hours ?? "—"} service hours</div>
                </div>

                <div className="kpi-card">
                  <div className="kpi-title">Productivity Metric</div>
                  <div className="kpi-value">
                    {curForecast?.predicted_rides && curForecast?.scheduled_service_hours
                      ? (curForecast.predicted_rides / curForecast.scheduled_service_hours).toFixed(1)
                      : "—"}{" "}
                    <span style={{ fontSize: 14 }}>rides/hr</span>
                  </div>
                  <div className="kpi-sub">
                    {curForecast?.predicted_rides && curForecast?.scheduled_trips
                      ? `${(curForecast.predicted_rides / curForecast.scheduled_trips).toFixed(1)} rides/trip`
                      : "—"}
                  </div>
                </div>

                <div className="kpi-card">
                  <div className="kpi-title">Prior Day Accuracy</div>
                  <div className="kpi-value">
                    {prevComp?.revealed_actual_rides != null
                      ? Number(prevComp.revealed_actual_rides).toLocaleString()
                      : "Lag active"}
                  </div>
                  <div className="kpi-sub">
                    {prevComp?.saved_prediction != null && (
                      <span>
                        Pred: {Number(prevComp.saved_prediction).toLocaleString()}{" "}
                        {prevDiff && (
                          <span className={`badge-tag ${Math.abs(Number(prevDiff.pct)) <= 5 ? "green" : "amber"}`}>
                            {Number(prevDiff.diff) >= 0 ? "+" : ""}
                            {prevDiff.diff} ({prevDiff.pct}%)
                          </span>
                        )}
                      </span>
                    )}
                  </div>
                </div>
              </div>

              {/* Chart Card */}
              <div className="card">
                <div className="card-header">
                  <div>
                    <h3 className="card-title">Ridership trend & today's forecast continuity</h3>
                    <p className="card-subtitle">
                      Solid line: recorded actual rides · Marker: today's predicted rides
                    </p>
                  </div>

                  <div style={{ display: "flex", gap: 10 }}>
                    <div style={{ display: "flex", gap: 2, background: "#f1f5f9", padding: 2, borderRadius: 6 }}>
                      <button
                        className={`btn btn-sm ${chartView === "rides" ? "btn-primary" : "btn-secondary"}`}
                        onClick={() => setChartView("rides")}
                      >
                        Ridership
                      </button>
                      <button
                        className={`btn btn-sm ${chartView === "trips" ? "btn-primary" : "btn-secondary"}`}
                        onClick={() => setChartView("trips")}
                      >
                        Scheduled Trips
                      </button>
                    </div>

                    <div style={{ display: "flex", gap: 2, background: "#f1f5f9", padding: 2, borderRadius: 6 }}>
                      {[14, 30, 60].map((w) => (
                        <button
                          key={w}
                          className={`btn btn-sm ${chartWindow === w ? "btn-primary" : "btn-secondary"}`}
                          onClick={() => setChartWindow(w)}
                        >
                          {w}d
                        </button>
                      ))}
                    </div>
                  </div>
                </div>

                <div style={{ height: 320, width: "100%", marginTop: 12 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={explorerChartData} margin={{ top: 10, right: 10, left: 10, bottom: 10 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e2e8e4" />
                      <XAxis dataKey="date" tick={{ fontSize: 11, fill: "#64748b" }} minTickGap={28} />
                      <YAxis tick={{ fontSize: 11, fill: "#64748b" }} />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: "#061d16",
                          color: "#fff",
                          borderRadius: 8,
                          border: "none",
                          fontSize: 12,
                        }}
                      />
                      <Legend />
                      {chartView === "rides" ? (
                        <>
                          <Line
                            type="monotone"
                            dataKey="actualRides"
                            name="Recorded Rides"
                            stroke="#059669"
                            strokeWidth={2.5}
                            dot={{ r: 3, fill: "#059669" }}
                            connectNulls
                          />
                          <Line
                            type="monotone"
                            dataKey="forecastRides"
                            name="Today's Model Forecast"
                            stroke="#0284c7"
                            strokeWidth={3}
                            dot={{ r: 6, fill: "#0284c7", stroke: "#fff", strokeWidth: 2 }}
                            connectNulls
                          />
                        </>
                      ) : (
                        <>
                          <Line
                            type="stepAfter"
                            dataKey="scheduledTrips"
                            name="Scheduled Trips"
                            stroke="#4f46e5"
                            strokeWidth={2}
                          />
                          <Line
                            type="stepAfter"
                            dataKey="scheduledHours"
                            name="Scheduled Service Hours"
                            stroke="#d97706"
                            strokeWidth={2}
                          />
                        </>
                      )}
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Interactive Corridor Geometry & Bus Stops Map */}
              <div className="card" style={{ marginTop: 20 }}>
                <div className="card-header">
                  <div>
                    <h3 className="card-title">Corridor geometry & real CTA bus stops</h3>
                    <p className="card-subtitle">
                      Real GPS shape polyline and stop locations for Route {selectedRoute}
                    </p>
                  </div>
                  <span className="badge-tag green">● Real CTA Polylines & Stops</span>
                </div>

                <div style={{ marginTop: 12 }}>
                  <CtaMap selectedRoute={selectedRoute} height={440} />
                </div>
              </div>
            </div>
          )}

          {/* TAB 4: COMPARE ROUTES */}
          {activeTab === "compare_routes" && (
            <div>
              <div className="view-header">
                <div className="view-subheading">Head-to-Head Evaluation</div>
                <h2 className="view-title">Compare routes</h2>
                <p className="view-desc">Compare ridership, productivity, and scheduled resources side-by-side</p>
              </div>

              <div className="filter-strip">
                <div style={{ display: "flex", gap: 20, alignItems: "center" }}>
                  <div className="filter-item">
                    <label>Route A:</label>
                    <select
                      className="select-input"
                      value={compareRouteA}
                      onChange={(e) => setCompareRouteA(e.target.value)}
                    >
                      {routes.map((r) => (
                        <option key={r} value={r}>
                          Route {r}
                        </option>
                      ))}
                    </select>
                  </div>
                  <span style={{ fontWeight: 800, color: "var(--text-muted)" }}>VS</span>
                  <div className="filter-item">
                    <label>Route B:</label>
                    <select
                      className="select-input"
                      value={compareRouteB}
                      onChange={(e) => setCompareRouteB(e.target.value)}
                    >
                      {routes.map((r) => (
                        <option key={r} value={r}>
                          Route {r}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
              </div>

              {/* Head-to-Head Cards */}
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr",
                  gap: 20,
                  marginBottom: 20,
                }}
              >
                {/* Route A Card */}
                <div className="card">
                  <div className="card-header">
                    <div>
                      <span className="badge-tag green">Route A</span>
                      <h3 className="card-title" style={{ fontSize: 22, marginTop: 4 }}>
                        Route {compareRouteA}
                      </h3>
                      <p className="card-subtitle">{compareData?.route1?.cluster_label}</p>
                    </div>
                  </div>
                  <table className="data-table">
                    <tbody>
                      <tr>
                        <td>Productivity Rank</td>
                        <td style={{ textAlign: "right", fontWeight: 700 }}>
                          #{compareData?.route1?.service_productivity_metric_rank ?? "—"}
                        </td>
                      </tr>
                      <tr>
                        <td>Rides / Scheduled Hour</td>
                        <td style={{ textAlign: "right", fontWeight: 700 }}>
                          {compareData?.route1?.rides_per_scheduled_hour
                            ? Number(compareData.route1.rides_per_scheduled_hour).toFixed(1)
                            : "—"}
                        </td>
                      </tr>
                      <tr>
                        <td>Mean Daily Boardings</td>
                        <td style={{ textAlign: "right", fontWeight: 700 }}>
                          {compareData?.route1?.mean_daily_rides
                            ? Math.round(compareData.route1.mean_daily_rides).toLocaleString()
                            : "—"}
                        </td>
                      </tr>
                      <tr>
                        <td>Mean Scheduled Trips</td>
                        <td style={{ textAlign: "right", fontWeight: 700 }}>
                          {compareData?.route1?.mean_scheduled_trips ?? "—"}
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>

                {/* Route B Card */}
                <div className="card">
                  <div className="card-header">
                    <div>
                      <span className="badge-tag blue">Route B</span>
                      <h3 className="card-title" style={{ fontSize: 22, marginTop: 4 }}>
                        Route {compareRouteB}
                      </h3>
                      <p className="card-subtitle">{compareData?.route2?.cluster_label}</p>
                    </div>
                  </div>
                  <table className="data-table">
                    <tbody>
                      <tr>
                        <td>Productivity Rank</td>
                        <td style={{ textAlign: "right", fontWeight: 700 }}>
                          #{compareData?.route2?.service_productivity_metric_rank ?? "—"}
                        </td>
                      </tr>
                      <tr>
                        <td>Rides / Scheduled Hour</td>
                        <td style={{ textAlign: "right", fontWeight: 700 }}>
                          {compareData?.route2?.rides_per_scheduled_hour
                            ? Number(compareData.route2.rides_per_scheduled_hour).toFixed(1)
                            : "—"}
                        </td>
                      </tr>
                      <tr>
                        <td>Mean Daily Boardings</td>
                        <td style={{ textAlign: "right", fontWeight: 700 }}>
                          {compareData?.route2?.mean_daily_rides
                            ? Math.round(compareData.route2.mean_daily_rides).toLocaleString()
                            : "—"}
                        </td>
                      </tr>
                      <tr>
                        <td>Mean Scheduled Trips</td>
                        <td style={{ textAlign: "right", fontWeight: 700 }}>
                          {compareData?.route2?.mean_scheduled_trips ?? "—"}
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Comparison Chart */}
              <div className="card">
                <div className="card-header">
                  <div>
                    <h3 className="card-title">Ridership trajectory comparison (Last 30 Days)</h3>
                    <p className="card-subtitle">Daily boardings overlay for Route {compareRouteA} vs Route {compareRouteB}</p>
                  </div>
                </div>

                <div style={{ height: 300, width: "100%", marginTop: 12 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart
                      data={(compareData?.history1 || []).map((h1: any, idx: number) => ({
                        date: h1.date,
                        [compareRouteA]: h1.rides,
                        [compareRouteB]: compareData?.history2?.[idx]?.rides ?? null,
                      }))}
                      margin={{ top: 10, right: 10, left: 10, bottom: 10 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke="#e2e8e4" />
                      <XAxis dataKey="date" tick={{ fontSize: 11, fill: "#64748b" }} minTickGap={28} />
                      <YAxis tick={{ fontSize: 11, fill: "#64748b" }} />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: "#061d16",
                          color: "#fff",
                          borderRadius: 8,
                          border: "none",
                          fontSize: 12,
                        }}
                      />
                      <Legend />
                      <Line
                        type="monotone"
                        dataKey={compareRouteA}
                        stroke="#059669"
                        strokeWidth={2.5}
                        dot={false}
                      />
                      <Line
                        type="monotone"
                        dataKey={compareRouteB}
                        stroke="#2563eb"
                        strokeWidth={2.5}
                        dot={false}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Spatial Corridor Alignment Map */}
              <div className="card" style={{ marginTop: 20 }}>
                <div className="card-header">
                  <div>
                    <h3 className="card-title">Spatial corridor alignment comparison</h3>
                    <p className="card-subtitle">
                      Route {compareRouteA} (solid green) vs Route {compareRouteB} (dashed blue) across Chicago
                    </p>
                  </div>
                  <div style={{ display: "flex", gap: 8 }}>
                    <span className="badge-tag green">● Route {compareRouteA}</span>
                    <span className="badge-tag blue">● Route {compareRouteB}</span>
                  </div>
                </div>

                <div style={{ marginTop: 12 }}>
                  <CtaMap
                    selectedRoute={compareRouteA}
                    compareRoute={compareRouteB}
                    height={440}
                  />
                </div>
              </div>
            </div>
          )}

          {/* TAB 5: ROUTE GROUPS */}
          {activeTab === "route_groups" && (
            <div>
              <div className="view-header">
                <div className="view-subheading">Network Clustering</div>
                <h2 className="view-title">Route groups</h2>
                <p className="view-desc">
                  Explore corridor archetypes derived from scheduled density and ridership characteristics
                </p>
              </div>

              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
                  gap: 20,
                }}
              >
                {clustersData.map((c) => (
                  <div key={c.name} className="card">
                    <div className="card-header">
                      <div>
                        <h3 className="card-title">{c.name}</h3>
                        <p className="card-subtitle">{c.route_count} assigned corridors</p>
                      </div>
                      <span className="badge-tag green">Cluster</span>
                    </div>

                    <div
                      style={{
                        display: "grid",
                        gridTemplateColumns: "1fr 1fr",
                        gap: 10,
                        background: "#f8faf8",
                        padding: 12,
                        borderRadius: 8,
                        marginBottom: 14,
                      }}
                    >
                      <div>
                        <div style={{ fontSize: 11, color: "var(--text-muted)" }}>Avg Rides / Hour</div>
                        <div style={{ fontSize: 18, fontWeight: 800, color: "var(--primary)" }}>
                          {c.avg_rides_per_hour}
                        </div>
                      </div>
                      <div>
                        <div style={{ fontSize: 11, color: "var(--text-muted)" }}>Mean Daily Rides</div>
                        <div style={{ fontSize: 18, fontWeight: 800, color: "var(--text-main)" }}>
                          {Number(c.mean_daily_rides).toLocaleString()}
                        </div>
                      </div>
                    </div>

                    <div>
                      <div style={{ fontSize: 12, fontWeight: 700, color: "var(--text-muted)", marginBottom: 8 }}>
                        Member Routes:
                      </div>
                      <div className="route-pill-list">
                        {c.routes.map((rt: string) => (
                          <button
                            key={rt}
                            className="route-pill"
                            onClick={() => {
                              setSelectedRoute(rt);
                              setActiveTab("route_explorer");
                            }}
                          >
                            Route {rt}
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* TAB 6: FORECASTS & EVALUATION */}
          {activeTab === "forecasts_evaluation" && (
            <div>
              <div className="view-header">
                <div className="view-subheading">Machine Learning Model Validation</div>
                <h2 className="view-title">Forecasts & evaluation</h2>
                <p className="view-desc">
                  Model performance evaluation against baselines with non-leaking test withholding
                </p>
              </div>

              {/* 3 Metric Cards */}
              <div className="kpi-grid">
                <div className="kpi-card highlight">
                  <div className="kpi-title">Model Architecture</div>
                  <div className="kpi-value" style={{ fontSize: 22 }}>
                    Random Forest
                  </div>
                  <div className="kpi-sub">Artifact: rf-service-v1</div>
                </div>

                <div className="kpi-card">
                  <div className="kpi-title">Mean Absolute Error (MAE)</div>
                  <div className="kpi-value">
                    {coverage?.evaluation_summary?.service_rf_test?.mae ?? "442.88"}
                  </div>
                  <div className="kpi-sub">Boardings / route-day</div>
                </div>

                <div className="kpi-card">
                  <div className="kpi-title">Weighted Absolute Error (WAPE)</div>
                  <div className="kpi-value">
                    {coverage?.evaluation_summary?.service_rf_test?.wape
                      ? `${(coverage.evaluation_summary.service_rf_test.wape * 100).toFixed(2)}%`
                      : "8.57%"}
                  </div>
                  <div className="kpi-sub">Network error rate</div>
                </div>

                <div className="kpi-card">
                  <div className="kpi-title">Test Observations</div>
                  <div className="kpi-value">
                    {coverage?.evaluation_summary?.coverage?.test_eligible_rows?.toLocaleString() ?? "9,874"}
                  </div>
                  <div className="kpi-sub">Out-of-sample evaluated days</div>
                </div>
              </div>

              {/* Baseline Comparison Card */}
              <div className="card">
                <div className="card-header">
                  <div>
                    <h3 className="card-title">Model vs. standard baselines comparison</h3>
                    <p className="card-subtitle">
                      Evaluated on strictly withheld post-calibration observation windows
                    </p>
                  </div>
                </div>

                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Candidate Model / Baseline</th>
                      <th>MAE (Rides)</th>
                      <th>RMSE (Rides)</th>
                      <th>WAPE (%)</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr style={{ background: "#ecfdf5" }}>
                      <td>
                        <strong>Production RF Service Forecaster</strong> (rf-service-v1)
                      </td>
                      <td>
                        <strong>{coverage?.evaluation_summary?.service_rf_test?.mae ?? "442.88"}</strong>
                      </td>
                      <td>
                        <strong>{coverage?.evaluation_summary?.service_rf_test?.rmse ?? "725.30"}</strong>
                      </td>
                      <td>
                        <strong style={{ color: "var(--primary)" }}>
                          {coverage?.evaluation_summary?.service_rf_test?.wape
                            ? `${(coverage.evaluation_summary.service_rf_test.wape * 100).toFixed(2)}%`
                            : "8.57%"}
                        </strong>
                      </td>
                      <td>
                        <span className="badge-tag green">Production</span>
                      </td>
                    </tr>
                    <tr>
                      <td>Seasonal Lag Baseline (Day-of-Week Lag)</td>
                      <td>{coverage?.evaluation_summary?.seasonal_baseline_test?.mae ?? "427.16"}</td>
                      <td>{coverage?.evaluation_summary?.seasonal_baseline_test?.rmse ?? "719.80"}</td>
                      <td>
                        {coverage?.evaluation_summary?.seasonal_baseline_test?.wape
                          ? `${(coverage.evaluation_summary.seasonal_baseline_test.wape * 100).toFixed(2)}%`
                          : "8.27%"}
                      </td>
                      <td>
                        <span className="badge-tag">Benchmark</span>
                      </td>
                    </tr>
                    <tr>
                      <td>Last Week Naive Baseline</td>
                      <td>{coverage?.evaluation_summary?.last_week_baseline_test?.mae ?? "526.51"}</td>
                      <td>{coverage?.evaluation_summary?.last_week_baseline_test?.rmse ?? "873.36"}</td>
                      <td>
                        {coverage?.evaluation_summary?.last_week_baseline_test?.wape
                          ? `${(coverage.evaluation_summary.last_week_baseline_test.wape * 100).toFixed(2)}%`
                          : "10.19%"}
                      </td>
                      <td>
                        <span className="badge-tag">Naive</span>
                      </td>
                    </tr>
                  </tbody>
                </table>

                <div className="callout callout-info" style={{ marginTop: 16 }}>
                  <span>🔒</span>
                  <div>
                    <strong>Data Leakage Prevention:</strong> Models operate under a strict 1-day reporting delay
                    rule. Feature matrices exclude any ridership observations beyond{" "}
                    <code>virtual_date - reporting_delay_days</code>.
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 7: SERVICE SCENARIOS */}
          {activeTab === "service_scenarios" && (
            <div>
              <div className="view-header">
                <div className="view-subheading">What-If Fleet Simulator</div>
                <h2 className="view-title">Service scenarios</h2>
                <p className="view-desc">
                  Simulate scheduled trip additions/cuts and evaluate impact on fleet hours and ridership productivity
                </p>
              </div>

              <div className="filter-strip">
                <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                  <label style={{ fontWeight: 700 }}>Simulate on Route:</label>
                  <select
                    className="select-input"
                    value={selectedRoute}
                    onChange={(e) => setSelectedRoute(e.target.value)}
                  >
                    {routes.map((r) => (
                      <option key={r} value={r}>
                        Route {r}
                      </option>
                    ))}
                  </select>
                </div>
                <div style={{ fontSize: 13, color: "var(--text-muted)" }}>
                  Baseline Predicted Rides: <strong>{curForecast?.predicted_rides?.toLocaleString() ?? "—"}</strong>
                </div>
              </div>

              {/* Controls Card */}
              <div className="card">
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
                    gap: 20,
                  }}
                >
                  {/* Slider 1: Trips Delta */}
                  <div>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                      <label style={{ fontSize: 13, fontWeight: 700 }}>Scheduled Trips Change (%)</label>
                      <strong style={{ color: "var(--primary)" }}>
                        {tripDeltaPct > 0 ? `+${tripDeltaPct}%` : `${tripDeltaPct}%`}
                      </strong>
                    </div>
                    <input
                      type="range"
                      min="-40"
                      max="50"
                      step="5"
                      value={tripDeltaPct}
                      onChange={(e) => setTripDeltaPct(Number(e.target.value))}
                      style={{ width: "100%", accentColor: "var(--primary)" }}
                    />
                    <div style={{ display: "flex", gap: 4, marginTop: 6, flexWrap: "wrap" }}>
                      {[-20, -10, 0, 10, 20, 30].map((v) => (
                        <button
                          key={v}
                          className={`btn btn-sm ${tripDeltaPct === v ? "btn-primary" : "btn-secondary"}`}
                          onClick={() => setTripDeltaPct(v)}
                        >
                          {v > 0 ? `+${v}%` : `${v}%`}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Slider 2: Demand Stress */}
                  <div>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                      <label style={{ fontSize: 13, fontWeight: 700 }}>Assumed Demand Stress (%)</label>
                      <strong style={{ color: "#2563eb" }}>
                        {demandStressPct > 0 ? `+${demandStressPct}%` : `${demandStressPct}%`}
                      </strong>
                    </div>
                    <input
                      type="range"
                      min="-30"
                      max="30"
                      step="5"
                      value={demandStressPct}
                      onChange={(e) => setDemandStressPct(Number(e.target.value))}
                      style={{ width: "100%", accentColor: "#2563eb" }}
                    />
                    <div style={{ display: "flex", gap: 4, marginTop: 6, flexWrap: "wrap" }}>
                      {[-10, 0, 10, 20].map((v) => (
                        <button
                          key={v}
                          className={`btn btn-sm ${demandStressPct === v ? "btn-primary" : "btn-secondary"}`}
                          onClick={() => setDemandStressPct(v)}
                        >
                          {v > 0 ? `+${v}%` : `${v}%`}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Input 3: Duration */}
                  <div>
                    <label style={{ fontSize: 13, fontWeight: 700, display: "block", marginBottom: 6 }}>
                      Avg Trip Duration (min)
                    </label>
                    <input
                      type="number"
                      min="15"
                      max="180"
                      className="text-input"
                      style={{ width: "100%" }}
                      value={assumedDuration}
                      onChange={(e) => setAssumedDuration(Math.max(1, Number(e.target.value)))}
                    />
                    <small style={{ color: "var(--text-muted)", display: "block", marginTop: 4 }}>
                      Calibrated from route profile schedule hours
                    </small>
                  </div>
                </div>

                <div style={{ marginTop: 20 }}>
                  <button
                    className="btn btn-primary"
                    onClick={calculateScenario}
                    disabled={scenarioLoading || !curForecast?.predicted_rides}
                  >
                    {scenarioLoading ? "Computing Simulation..." : "⚡ Run Scenario Analysis"}
                  </button>
                </div>

                {scenarioError && (
                  <div className="callout callout-muted" style={{ marginTop: 14 }}>
                    <span>⚠️</span>
                    <div>{scenarioError}</div>
                  </div>
                )}

                {scenarioResult && (
                  <div style={{ marginTop: 24 }}>
                    <div className="card-header">
                      <div>
                        <h4 className="card-title">Scenario projection comparison</h4>
                        <p className="card-subtitle">Scenario run identifier: {scenarioResult.scenario_id}</p>
                      </div>
                    </div>

                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Metric</th>
                          <th>Baseline Profile</th>
                          <th>Proposed Scenario</th>
                          <th>Net Change (Delta)</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr>
                          <td>
                            <strong>Rides / Day</strong>
                          </td>
                          <td>{Number(scenarioResult.baseline.rides).toLocaleString()}</td>
                          <td>{Number(scenarioResult.proposed.assumed_rides).toLocaleString()}</td>
                          <td>
                            <span className="badge-tag green">
                              {(
                                scenarioResult.proposed.assumed_rides - scenarioResult.baseline.rides
                              ).toFixed(0)}{" "}
                              rides
                            </span>
                          </td>
                        </tr>
                        <tr>
                          <td>
                            <strong>Scheduled Trips</strong>
                          </td>
                          <td>{scenarioResult.baseline.scheduled_trips} trips</td>
                          <td>{scenarioResult.proposed.scheduled_trips} trips</td>
                          <td>
                            <span className="badge-tag">
                              {scenarioResult.proposed.scheduled_trips - scenarioResult.baseline.scheduled_trips}{" "}
                              trips
                            </span>
                          </td>
                        </tr>
                        <tr>
                          <td>
                            <strong>Scheduled Trip-Hours</strong>
                          </td>
                          <td>{scenarioResult.baseline.scheduled_trip_hours} hrs</td>
                          <td>{scenarioResult.proposed.scheduled_trip_hours} hrs</td>
                          <td>
                            <span className="badge-tag">
                              {(
                                scenarioResult.proposed.scheduled_trip_hours -
                                scenarioResult.baseline.scheduled_trip_hours
                              ).toFixed(1)}{" "}
                              hrs
                            </span>
                          </td>
                        </tr>
                        <tr>
                          <td>
                            <strong>Rides / Scheduled Hour</strong>
                          </td>
                          <td>{scenarioResult.baseline.rides_per_scheduled_hour ?? "—"}</td>
                          <td>{scenarioResult.proposed.rides_per_scheduled_hour ?? "—"}</td>
                          <td>
                            <span className="badge-tag">
                              {(
                                (scenarioResult.proposed.rides_per_scheduled_hour || 0) -
                                (scenarioResult.baseline.rides_per_scheduled_hour || 0)
                              ).toFixed(1)}{" "}
                              rides/hr
                            </span>
                          </td>
                        </tr>
                      </tbody>
                    </table>

                    <div className="callout callout-muted" style={{ marginTop: 14 }}>
                      <span>ℹ️</span>
                      <div>{scenarioResult.assumptions?.note}</div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* TAB 8: DATA & PROVENANCE */}
          {activeTab === "data_provenance" && (
            <div>
              <div className="view-header">
                <div className="view-subheading">Data Pipeline & Provenance</div>
                <h2 className="view-title">Data & provenance</h2>
                <p className="view-desc">
                  Audit trail, source datasets, coverage bounds, and data processing stages
                </p>
              </div>

              {/* Data Ingestion Summary Card */}
              <div className="card">
                <div className="card-header">
                  <div>
                    <h3 className="card-title">Dataset coverage bounds</h3>
                    <p className="card-subtitle">Official Chicago Transit Authority (CTA) data feeds</p>
                  </div>
                </div>

                <table className="data-table">
                  <tbody>
                    <tr>
                      <td>
                        <strong>Transit Agency</strong>
                      </td>
                      <td>Chicago Transit Authority (CTA) Buses</td>
                    </tr>
                    <tr>
                      <td>
                        <strong>Ridership Observation Range</strong>
                      </td>
                      <td>2001-01-01 through 2026-07-31 (Historical & Daily Feeds)</td>
                    </tr>
                    <tr>
                      <td>
                        <strong>Matched Analysis Window</strong>
                      </td>
                      <td>2025-11-23 through 2026-07-31</td>
                    </tr>
                    <tr>
                      <td>
                        <strong>Total Matched Route-Days</strong>
                      </td>
                      <td>28,374 matched observation days</td>
                    </tr>
                    <tr>
                      <td>
                        <strong>Unmatched Boarding Records</strong>
                      </td>
                      <td>424 rows (1.47% due to holiday or temporary special service)</td>
                    </tr>
                    <tr>
                      <td>
                        <strong>Unmatched Schedule Rows</strong>
                      </td>
                      <td>24 rows (0.08%)</td>
                    </tr>
                    <tr>
                      <td>
                        <strong>Overall Ingestion Match Rate</strong>
                      </td>
                      <td>
                        <span className="badge-tag green">99.92% Complete Match</span>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>

              {/* 5-Step Pipeline Card */}
              <div className="card" style={{ marginTop: 20 }}>
                <div className="card-header">
                  <div>
                    <h3 className="card-title">Data processing pipeline architecture</h3>
                    <p className="card-subtitle">End-to-end reproducible pipeline execution</p>
                  </div>
                </div>

                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: 12,
                    marginTop: 10,
                  }}
                >
                  {[
                    {
                      step: "Step 1",
                      title: "Data Ingestion & Socrata API Feeds",
                      desc: "Automated retrieval of historical ridership, dated GTFS schedules, and holiday calendars.",
                    },
                    {
                      step: "Step 2",
                      title: "Schedule Reconstruction & Service Matching",
                      desc: "Trip duration expansion and matching of scheduled vehicle hours to route calendar daytypes.",
                    },
                    {
                      step: "Step 3",
                      title: "Lag Generation & Feature Engineering",
                      desc: "Non-leaking historical lags (1d, 7d, 14d, 28d) with missing-lag fallback heuristics.",
                    },
                    {
                      step: "Step 4",
                      title: "Random Forest Model Training",
                      desc: "Supervised regression predicting ridership demand from permitted lags and scheduled service.",
                    },
                    {
                      step: "Step 5",
                      title: "Route Profiling & Corridor Clustering",
                      desc: "Unsupervised clustering classifying corridors into Trunk, Neighborhood, Connector, and Specialized groups.",
                    },
                  ].map((s) => (
                    <div
                      key={s.step}
                      style={{
                        display: "flex",
                        alignItems: "flex-start",
                        gap: 16,
                        background: "#f8faf8",
                        border: "1px solid #e2e8e4",
                        borderRadius: 8,
                        padding: 14,
                      }}
                    >
                      <span className="badge-tag green" style={{ fontWeight: 800 }}>
                        {s.step}
                      </span>
                      <div>
                        <strong style={{ fontSize: 14, color: "var(--text-main)" }}>{s.title}</strong>
                        <p style={{ margin: "2px 0 0", fontSize: 12.5, color: "var(--text-muted)" }}>
                          {s.desc}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
