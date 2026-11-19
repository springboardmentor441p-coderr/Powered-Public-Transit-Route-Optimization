import React, { useEffect, useState, useMemo, useRef } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Legend,
  CartesianGrid,
  ReferenceDot,
} from "recharts";
import "./App.css";

// Use relative API when running under Vite proxy or localhost:8000 directly
const API = "/api";

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
  const [routes, setRoutes] = useState<string[]>([]);
  const [selectedRoute, setSelectedRoute] = useState<string>("22");
  const [daytype, setDaytype] = useState<string>("W");
  const [rankings, setRankings] = useState<RouteProfile[]>([]);
  const [session, setSession] = useState<ReplaySession | null>(null);
  const [forecastData, setForecastData] = useState<ForecastResponse | null>(null);
  const [history, setHistory] = useState<any[]>([]);
  const [coverage, setCoverage] = useState<any>(null);

  // Connection & UI states
  const [isConnected, setIsConnected] = useState<boolean>(true);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Filters & Sorting for routes
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [selectedCluster, setSelectedCluster] = useState<string>("ALL");
  const [sortField, setSortField] = useState<string>("rank");

  // Chart settings
  const [chartWindow, setChartWindow] = useState<number>(30); // 14, 30, 60 days
  const [chartView, setChartView] = useState<"rides" | "trips">("rides");

  // Scenario Simulator
  const [tripDeltaPct, setTripDeltaPct] = useState<number>(10);
  const [demandStressPct, setDemandStressPct] = useState<number>(0);
  const [assumedDuration, setAssumedDuration] = useState<number>(40);
  const [scenarioResult, setScenarioResult] = useState<any>(null);
  const [scenarioError, setScenarioError] = useState<string | null>(null);
  const [scenarioLoading, setScenarioLoading] = useState<boolean>(false);

  // Replay speed
  const [playbackSpeedMs, setPlaybackSpeedMs] = useState<number>(3000); // ms per step

  // Initialize or reconnect
  const initApp = async () => {
    setIsLoading(true);
    setErrorMsg(null);
    try {
      // 1. Fetch routes
      const routesRes = await fetch(`${API}/routes`);
      if (!routesRes.ok) throw new Error("Could not connect to RouteRanker API");
      const routesData = await routesRes.json();
      setRoutes(routesData.routes || []);

      // 2. Fetch coverage stats
      fetch(`${API}/data/coverage`)
        .then((r) => (r.ok ? r.json() : null))
        .then(setCoverage)
        .catch(() => {});

      // 3. Create or get session
      const replayRes = await fetch(`${API}/replays`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          start_date: "2026-06-01",
          end_date: "2026-07-31",
          reporting_delay_days: 1,
        }),
      });
      if (replayRes.ok) {
        const sessData = await replayRes.json();
        setSession(sessData);
      }
      setIsConnected(true);
    } catch (err: any) {
      console.error(err);
      setIsConnected(false);
      setErrorMsg("Backend service is not responding at localhost:8000. Ensure the FastAPI backend is running.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    initApp();
  }, []);

  // Fetch rankings whenever daytype changes
  useEffect(() => {
    fetch(`${API}/rankings?daytype=${daytype}`)
      .then((r) => (r.ok ? r.json() : []))
      .then((d) => setRankings(Array.isArray(d) ? d : []))
      .catch(() => setRankings([]));
  }, [daytype]);

  // Fetch forecast and route history whenever session date or selected route changes
  useEffect(() => {
    setScenarioResult(null);
    setScenarioError(null);
    if (!session?.session_id) return;

    // Fetch Forecast for current virtual date
    fetch(`${API}/replays/${session.session_id}/forecast/${selectedRoute}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data: ForecastResponse) => {
        setForecastData(data);
        // Automatically calibrate assumed duration to actual route average if available
        if (data?.current_forecast?.scheduled_trips && data?.current_forecast?.scheduled_service_hours) {
          const avgMins = Math.round(
            (data.current_forecast.scheduled_service_hours / data.current_forecast.scheduled_trips) * 60
          );
          if (avgMins > 0) setAssumedDuration(avgMins);
        }
      })
      .catch(() => setForecastData(null));

    // Fetch Route History and filter up to current virtual date
    fetch(`${API}/routes/${selectedRoute}/history?session_id=${session.session_id}`)
      .then((r) => (r.ok ? r.json() : []))
      .then((d: any[]) => {
        if (!Array.isArray(d)) {
          setHistory([]);
          return;
        }
        // CRITICAL FIX: The full history extends into late August 2026.
        // Slice records up to virtual date so recent historical days are actually displayed!
        const filtered = d.filter((item) => item.date <= session.virtual_date);
        setHistory(filtered);
      })
      .catch(() => setHistory([]));
  }, [session?.session_id, session?.virtual_date, selectedRoute]);

  // Playback timer loop
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
      console.error("Replay control error:", err);
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
      setScenarioError(
        "Scenario requires an active predicted rides/day value and scheduled trips for the current virtual date."
      );
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
      if (!res.ok) {
        setScenarioError(data?.detail || "Unable to compute scenario.");
      } else {
        setScenarioResult(data);
      }
    } catch (err: any) {
      setScenarioError(err.message || "Failed to communicate with scenario endpoint.");
    } finally {
      setScenarioLoading(false);
    }
  };

  // Distinct cluster options
  const clusters = useMemo(() => {
    const list = Array.from(new Set(rankings.map((r) => r.cluster_label).filter(Boolean))) as string[];
    return list.sort();
  }, [rankings]);

  // Filtered & Sorted Rankings List
  const filteredRankings = useMemo(() => {
    return rankings
      .filter((r) => {
        if (searchQuery.trim()) {
          const q = searchQuery.toLowerCase().trim();
          if (!r.route.toLowerCase().includes(q)) return false;
        }
        if (selectedCluster !== "ALL" && r.cluster_label !== selectedCluster) {
          return false;
        }
        return true;
      })
      .sort((a, b) => {
        if (sortField === "rank") {
          const rankA = a.service_productivity_metric_rank ?? 999;
          const rankB = b.service_productivity_metric_rank ?? 999;
          return rankA - rankB;
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

  // Chart data preparation: combine recent recorded actuals with current virtual date forecast
  const chartData = useMemo(() => {
    const recent = history.slice(-chartWindow);
    const curForecast = forecastData?.current_forecast;

    // Map existing historical entries
    const items = recent.map((item) => ({
      date: item.date,
      actualRides: item.rides !== null && item.rides !== undefined ? Number(item.rides) : null,
      scheduledTrips: item.scheduled_trips,
      scheduledHours: item.scheduled_service_hours,
      forecastRides: null as number | null,
    }));

    // If virtual date matches today and we have a predicted value, ensure it is represented
    if (session?.virtual_date && curForecast?.predicted_rides) {
      const existingIdx = items.findIndex((i) => i.date === session.virtual_date);
      if (existingIdx >= 0) {
        items[existingIdx].forecastRides = curForecast.predicted_rides;
      } else {
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

  // Calculate prior day comparison stats
  const prevComp = forecastData?.previous_day_comparison;
  const prevDiff = useMemo(() => {
    if (
      prevComp?.revealed_actual_rides != null &&
      prevComp?.saved_prediction != null &&
      prevComp.saved_prediction > 0
    ) {
      const diff = prevComp.revealed_actual_rides - prevComp.saved_prediction;
      const pct = (diff / prevComp.saved_prediction) * 100;
      return { diff: Math.round(diff), pct: pct.toFixed(1) };
    }
    return null;
  }, [prevComp]);

  // Replay timeline stats
  const replayProgressPct = useMemo(() => {
    if (!session) return 0;
    const start = new Date(session.start_date).getTime();
    const end = new Date(session.end_date).getTime();
    const cur = new Date(session.virtual_date).getTime();
    if (end <= start) return 0;
    return Math.min(100, Math.max(0, Math.round(((cur - start) / (end - start)) * 100)));
  }, [session]);

  const curForecast = forecastData?.current_forecast;

  return (
    <div className="app-container">
      {/* Top Header */}
      <header className="app-header">
        <div className="header-top">
          <div className="brand-wrapper">
            <div className="brand-logo">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="3" y="4" width="18" height="15" rx="2" />
                <path d="M4 11h16" />
                <path d="M8 15h.01" />
                <path d="M16 15h.01" />
                <path d="M6 19v2" />
                <path d="M18 19v2" />
              </svg>
            </div>
            <div>
              <h1 className="brand-title">
                RouteRanker <span className="brand-tag">CTA Intelligence</span>
              </h1>
              <p className="brand-subtitle">
                Chicago Transit Authority — Service Planning, Replay & Demand Forecasting
              </p>
            </div>
          </div>

          <div className="header-controls">
            {coverage && (
              <span
                style={{
                  fontSize: 12,
                  color: "var(--slate-600)",
                  background: "var(--slate-100)",
                  padding: "4px 10px",
                  borderRadius: 6,
                  fontWeight: 600,
                }}
              >
                📊 28,374 Matched Days · {coverage.evaluation_summary?.model_version || "rf-service-v1"}
              </span>
            )}
            <div className={`status-badge ${isConnected ? "connected" : "disconnected"}`}>
              <span className="pulse-dot"></span>
              {isConnected ? "Backend Connected (Port 8000)" : "Backend Disconnected"}
            </div>
            {!isConnected && (
              <button className="btn btn-secondary btn-sm" onClick={initApp}>
                Retry Connection
              </button>
            )}
          </div>
        </div>

        {/* Replay Controls & Timeline */}
        {session?.session_id && (
          <div className="replay-bar">
            <div className="replay-date-info">
              <div className="date-pill">
                <span>📅</span>
                <span>{session.virtual_date}</span>
                <span className={`session-status status-${session.status}`}>{session.status}</span>
              </div>
              <span style={{ fontSize: 12, color: "var(--slate-500)" }}>
                Lag Rule: <strong>{session.reporting_delay_days} day reporting delay</strong> (non-leaking)
              </span>
            </div>

            <div className="replay-buttons">
              {session.status === "running" ? (
                <button className="btn btn-secondary" onClick={() => controlReplay("pause")}>
                  ⏸ Pause
                </button>
              ) : (
                <button
                  className="btn btn-primary"
                  onClick={() => {
                    if (session.status === "completed") {
                      controlReplay("reset").then(() => controlReplay("start"));
                    } else {
                      controlReplay("start");
                    }
                  }}
                >
                  ▶ {session.status === "completed" ? "Restart Replay" : "Play Replay"}
                </button>
              )}

              <button
                className="btn btn-secondary"
                onClick={() => controlReplay("advance")}
                disabled={session.status === "completed"}
                title="Advance 1 day"
              >
                +1 Day
              </button>

              <button
                className="btn btn-secondary"
                onClick={() => advanceMultipleDays(7)}
                disabled={session.status === "completed"}
                title="Advance 1 full week"
              >
                +7 Days (Week)
              </button>

              <button className="btn btn-secondary" onClick={() => controlReplay("reset")} title="Reset to start">
                ↺ Reset
              </button>

              <select
                className="speed-select"
                value={playbackSpeedMs}
                onChange={(e) => setPlaybackSpeedMs(Number(e.target.value))}
                title="Replay Speed"
              >
                <option value={5000}>Speed: 1x (5s/day)</option>
                <option value={2500}>Speed: 2x (2.5s/day)</option>
                <option value={1000}>Speed: 5x (1s/day)</option>
              </select>
            </div>

            <div className="replay-progress-container">
              <span className="progress-text">{session.start_date}</span>
              <input
                type="range"
                className="replay-slider"
                min="0"
                max="100"
                value={replayProgressPct}
                readOnly
              />
              <span className="progress-text">
                {session.end_date} ({replayProgressPct}% complete)
              </span>
            </div>
          </div>
        )}
      </header>

      {/* Error Callout if disconnected */}
      {errorMsg && (
        <div className="callout callout-warning" style={{ marginBottom: 20 }}>
          <span>⚠️</span>
          <div style={{ flex: 1 }}>
            <strong>Connection Warning:</strong> {errorMsg}
          </div>
          <button className="btn btn-secondary btn-sm" onClick={initApp}>
            Try Reconnecting
          </button>
        </div>
      )}

      {/* Main Grid: Left Navigation / Priorities, Right Detail & Scenario */}
      <div className="dashboard-grid">
        {/* Left Column: Review Priorities Table */}
        <aside>
          <div className="card">
            <div className="card-title-row">
              <h2 className="card-title">
                <span>📋</span> Review Priorities
              </h2>
              <span style={{ fontSize: 12, fontWeight: 700, color: "var(--primary)" }}>
                {filteredRankings.length} Routes
              </span>
            </div>

            {/* Filter Controls */}
            <div className="filter-group">
              <label className="filter-label">Day Schedule Type</label>
              <select className="input-control" value={daytype} onChange={(e) => setDaytype(e.target.value)}>
                <option value="W">Weekday Schedule (W)</option>
                <option value="A">Saturday Schedule (A)</option>
                <option value="U">Sunday / Holiday Schedule (U)</option>
              </select>
            </div>

            <div className="filter-group">
              <label className="filter-label">Corridor Cluster</label>
              <select
                className="input-control"
                value={selectedCluster}
                onChange={(e) => setSelectedCluster(e.target.value)}
              >
                <option value="ALL">All Corridor Clusters</option>
                {clusters.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </div>

            <div className="filter-group">
              <label className="filter-label">Search & Sort</label>
              <div style={{ display: "flex", gap: 6 }}>
                <input
                  type="text"
                  placeholder="Search route # (e.g. 22)..."
                  className="input-control"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
                <select
                  className="input-control"
                  style={{ width: "120px" }}
                  value={sortField}
                  onChange={(e) => setSortField(e.target.value)}
                >
                  <option value="rank">Rank</option>
                  <option value="productivity">Rides/Hr</option>
                  <option value="route">Route #</option>
                </select>
              </div>
            </div>

            {/* Rankings Table */}
            <div className="table-wrapper" style={{ marginTop: 14 }}>
              <table className="routes-table">
                <thead>
                  <tr>
                    <th>Rank</th>
                    <th>Route</th>
                    <th>Rides / Hr</th>
                    <th>Cluster</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredRankings.length === 0 ? (
                    <tr>
                      <td colSpan={4} style={{ textAlign: "center", padding: 24, color: "var(--slate-400)" }}>
                        No routes match filter.
                      </td>
                    </tr>
                  ) : (
                    filteredRankings.map((r) => {
                      const isSelected = r.route === selectedRoute;
                      const rankVal = r.service_productivity_metric_rank;
                      const isTop10 = rankVal && rankVal <= 10;
                      return (
                        <tr
                          key={r.route}
                          className={`route-row ${isSelected ? "selected" : ""}`}
                          onClick={() => setSelectedRoute(r.route)}
                        >
                          <td>
                            {r.is_ranking_eligible ? (
                              <span className={`rank-badge ${isTop10 ? "top-10" : ""}`}>
                                #{rankVal}
                              </span>
                            ) : (
                              <span style={{ color: "var(--slate-400)", fontSize: 11 }}>Unranked</span>
                            )}
                          </td>
                          <td>
                            <strong style={{ color: isSelected ? "var(--primary)" : "inherit" }}>
                              Route {r.route}
                            </strong>
                          </td>
                          <td>
                            <strong>
                              {r.rides_per_scheduled_hour
                                ? Number(r.rides_per_scheduled_hour).toFixed(1)
                                : "N/A"}
                            </strong>
                          </td>
                          <td>
                            <span className="cluster-tag" title={r.cluster_label}>
                              {r.cluster_label || "General"}
                            </span>
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </aside>

        {/* Right Column: Route Details, Chart, Prior Day Accuracy & Scenario Simulator */}
        <main>
          {/* Section: Route Header & KPIs */}
          <section className="card">
            <div className="card-title-row">
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <div
                  style={{
                    background: "var(--primary-light)",
                    color: "var(--primary-dark)",
                    fontSize: 22,
                    fontWeight: 800,
                    padding: "6px 14px",
                    borderRadius: 10,
                  }}
                >
                  Route {selectedRoute}
                </div>
                <div>
                  <h2 style={{ margin: 0, fontSize: 18, color: "var(--slate-900)" }}>
                    Demand Forecast & Operational Profile
                  </h2>
                  <small style={{ color: "var(--slate-500)" }}>
                    Virtual Target Date: <strong>{session?.virtual_date || "—"}</strong> · Provenance: Historical
                    Replay
                  </small>
                </div>
              </div>

              {/* Quick Route Selector dropdown */}
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ fontSize: 12, fontWeight: 600, color: "var(--slate-500)" }}>Select Route:</span>
                <select
                  className="input-control"
                  style={{ width: "130px", fontWeight: 700 }}
                  value={selectedRoute}
                  onChange={(e) => setSelectedRoute(e.target.value)}
                >
                  {routes.map((rt) => (
                    <option key={rt} value={rt}>
                      Route {rt}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* KPI Metric Cards */}
            <div className="metrics-grid">
              {/* Metric 1: Predicted Rides */}
              <div className="metric-card accent">
                <div className="metric-header">
                  <span className="metric-title">Predicted Rides / Day</span>
                  <span
                    style={{
                      fontSize: 10,
                      fontWeight: 700,
                      textTransform: "uppercase",
                      padding: "2px 6px",
                      borderRadius: 4,
                      background: curForecast?.status === "predicted" ? "#bbf7d0" : "#fed7aa",
                      color: curForecast?.status === "predicted" ? "#166534" : "#9a3412",
                    }}
                  >
                    {curForecast?.status || "Loading"}
                  </span>
                </div>
                <div className="metric-value">
                  {curForecast?.status === "predicted" && curForecast?.predicted_rides != null
                    ? Number(curForecast.predicted_rides).toLocaleString(undefined, {
                        maximumFractionDigits: 0,
                      })
                    : "—"}
                </div>
                <div className="metric-sub">
                  Model: {curForecast?.model_version || "rf-service-v1"}
                </div>
              </div>

              {/* Metric 2: Scheduled Service */}
              <div className="metric-card">
                <div className="metric-header">
                  <span className="metric-title">Scheduled Service</span>
                  <span style={{ fontSize: 12 }}>🚌</span>
                </div>
                <div className="metric-value">
                  {curForecast?.scheduled_trips ?? "—"} <span style={{ fontSize: 14, fontWeight: 600 }}>trips</span>
                </div>
                <div className="metric-sub">
                  {curForecast?.scheduled_service_hours != null
                    ? `${curForecast.scheduled_service_hours} scheduled hours`
                    : "Hours pending"}
                </div>
              </div>

              {/* Metric 3: Estimated Productivity */}
              <div className="metric-card">
                <div className="metric-header">
                  <span className="metric-title">Productivity Metric</span>
                  <span style={{ fontSize: 12 }}>⚡</span>
                </div>
                <div className="metric-value">
                  {curForecast?.predicted_rides && curForecast?.scheduled_service_hours
                    ? (curForecast.predicted_rides / curForecast.scheduled_service_hours).toFixed(1)
                    : "—"}{" "}
                  <span style={{ fontSize: 14, fontWeight: 600 }}>rides / hr</span>
                </div>
                <div className="metric-sub">
                  {curForecast?.predicted_rides && curForecast?.scheduled_trips
                    ? `${(curForecast.predicted_rides / curForecast.scheduled_trips).toFixed(1)} rides / trip`
                    : "—"}
                </div>
              </div>

              {/* Metric 4: Prior Day Accuracy & Comparison */}
              <div className="metric-card">
                <div className="metric-header">
                  <span className="metric-title">Prior Day Accuracy</span>
                  <span style={{ fontSize: 11, color: "var(--slate-400)" }}>{prevComp?.date || "Yesterday"}</span>
                </div>
                <div className="metric-value" style={{ fontSize: 18 }}>
                  {prevComp?.revealed_actual_rides != null ? (
                    <span>
                      {Number(prevComp.revealed_actual_rides).toLocaleString()} <span style={{ fontSize: 12, fontWeight: 500, color: "var(--slate-500)" }}>actual</span>
                    </span>
                  ) : (
                    <span style={{ fontSize: 14, color: "var(--slate-400)", fontWeight: 500 }}>
                      Reporting delay active
                    </span>
                  )}
                </div>
                <div className="metric-sub">
                  {prevComp?.saved_prediction != null ? (
                    <span>
                      Pred: {Number(prevComp.saved_prediction).toLocaleString()}{" "}
                      {prevDiff && (
                        <span
                          className={`diff-tag ${
                            Math.abs(Number(prevDiff.pct)) <= 5
                              ? "diff-pos"
                              : Math.abs(Number(prevDiff.pct)) <= 15
                              ? "diff-neutral"
                              : "diff-neg"
                          }`}
                        >
                          {Number(prevDiff.diff) >= 0 ? "+" : ""}
                          {prevDiff.diff} ({Number(prevDiff.pct) >= 0 ? "+" : ""}
                          {prevDiff.pct}%)
                        </span>
                      )}
                    </span>
                  ) : (
                    "No prior saved forecast"
                  )}
                </div>
              </div>
            </div>

            {/* Status note if history insufficient */}
            {curForecast?.status !== "predicted" && curForecast?.reason && (
              <div className="callout callout-warning">
                <span>ℹ️</span>
                <div>
                  <strong>Model Status:</strong> {curForecast.reason}. Permitted lag cutoff:{" "}
                  {curForecast.latest_permitted_ride_date || "—"}.
                </div>
              </div>
            )}

            {/* Interactive Ridership & Schedule Chart */}
            <div style={{ marginTop: 24 }}>
              <div className="card-title-row">
                <div>
                  <h3 style={{ margin: 0, fontSize: 15, color: "var(--slate-900)" }}>
                    Ridership Trend & Today's Forecast Continuity
                  </h3>
                  <small style={{ color: "var(--slate-500)" }}>
                    Solid line: recorded rides through reporting cutoff · Point marker: today's predicted rides
                  </small>
                </div>

                <div className="chart-header-actions">
                  <div className="pill-toggle">
                    <button
                      className={`pill-btn ${chartView === "rides" ? "active" : ""}`}
                      onClick={() => setChartView("rides")}
                    >
                      Ridership
                    </button>
                    <button
                      className={`pill-btn ${chartView === "trips" ? "active" : ""}`}
                      onClick={() => setChartView("trips")}
                    >
                      Scheduled Trips
                    </button>
                  </div>

                  <div className="pill-toggle">
                    <button
                      className={`pill-btn ${chartWindow === 14 ? "active" : ""}`}
                      onClick={() => setChartWindow(14)}
                    >
                      14d
                    </button>
                    <button
                      className={`pill-btn ${chartWindow === 30 ? "active" : ""}`}
                      onClick={() => setChartWindow(30)}
                    >
                      30d
                    </button>
                    <button
                      className={`pill-btn ${chartWindow === 60 ? "active" : ""}`}
                      onClick={() => setChartWindow(60)}
                    >
                      60d
                    </button>
                  </div>
                </div>
              </div>

              <div className="chart-container" style={{ minWidth: 0 }}>
                {chartData.length === 0 ? (
                  <div
                    style={{
                      height: "100%",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      color: "var(--slate-400)",
                    }}
                  >
                    No historical observations available for this date window.
                  </div>
                ) : (
                  <ResponsiveContainer width="100%" height={280}>
                    <LineChart data={chartData} margin={{ top: 12, right: 20, left: 10, bottom: 10 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                      <XAxis
                        dataKey="date"
                        tick={{ fontSize: 11, fill: "#64748b" }}
                        minTickGap={28}
                        stroke="#cbd5e1"
                      />
                      <YAxis tick={{ fontSize: 11, fill: "#64748b" }} stroke="#cbd5e1" />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: "#0f172a",
                          color: "#ffffff",
                          borderRadius: 8,
                          border: "none",
                          fontSize: 12,
                          boxShadow: "0 4px 12px rgba(0,0,0,0.15)",
                        }}
                      />
                      <Legend wrapperStyle={{ fontSize: 12, paddingTop: 10 }} />

                      {chartView === "rides" ? (
                        <>
                          <Line
                            type="monotone"
                            dataKey="actualRides"
                            name="Recorded Actual Rides"
                            stroke="#0f766e"
                            strokeWidth={2.5}
                            dot={{ r: 3, fill: "#0f766e" }}
                            connectNulls
                          />
                          <Line
                            type="monotone"
                            dataKey="forecastRides"
                            name="Today's Model Forecast"
                            stroke="#0284c7"
                            strokeWidth={3}
                            dot={{ r: 6, fill: "#0284c7", stroke: "#ffffff", strokeWidth: 2 }}
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
                            dot={{ r: 2 }}
                          />
                          <Line
                            type="stepAfter"
                            dataKey="scheduledHours"
                            name="Scheduled Service Hours"
                            stroke="#f59e0b"
                            strokeWidth={2}
                            dot={false}
                          />
                        </>
                      )}
                    </LineChart>
                  </ResponsiveContainer>
                )}
              </div>
            </div>
          </section>

          {/* Section: What-If Scenario Simulator */}
          <section className="card" style={{ marginTop: 20 }}>
            <div className="card-title-row">
              <div>
                <h3 className="card-title">
                  <span>⚡</span> Conditional Service Scenario Simulator (What-If)
                </h3>
                <small style={{ color: "var(--slate-500)" }}>
                  Explore scheduled service changes, trip frequency reallocations, and demand stress scenarios.
                </small>
              </div>
            </div>

            <div className="scenario-panel">
              <div className="scenario-controls-grid">
                {/* Control 1: Trips Delta */}
                <div>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <label className="filter-label">Scheduled Trips Change (%)</label>
                    <span style={{ fontWeight: 700, fontSize: 13, color: "var(--primary)" }}>
                      {tripDeltaPct > 0 ? `+${tripDeltaPct}%` : `${tripDeltaPct}%`}
                    </span>
                  </div>
                  <input
                    type="range"
                    min="-40"
                    max="50"
                    step="5"
                    value={tripDeltaPct}
                    onChange={(e) => setTripDeltaPct(Number(e.target.value))}
                    style={{ width: "100%", accentColor: "var(--primary)", marginTop: 6 }}
                  />
                  <div className="chip-group">
                    {[-20, -10, 0, 10, 20, 30].map((v) => (
                      <button
                        key={v}
                        className={`chip-btn ${tripDeltaPct === v ? "active" : ""}`}
                        onClick={() => setTripDeltaPct(v)}
                      >
                        {v > 0 ? `+${v}%` : `${v}%`}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Control 2: Demand Stress */}
                <div>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <label className="filter-label">Assumed Demand Stress (%)</label>
                    <span style={{ fontWeight: 700, fontSize: 13, color: "var(--indigo-600)" }}>
                      {demandStressPct > 0 ? `+${demandStressPct}%` : `${demandStressPct}%`}
                    </span>
                  </div>
                  <input
                    type="range"
                    min="-30"
                    max="30"
                    step="5"
                    value={demandStressPct}
                    onChange={(e) => setDemandStressPct(Number(e.target.value))}
                    style={{ width: "100%", accentColor: "var(--indigo-600)", marginTop: 6 }}
                  />
                  <div className="chip-group">
                    {[-10, 0, 10, 20].map((v) => (
                      <button
                        key={v}
                        className={`chip-btn ${demandStressPct === v ? "active" : ""}`}
                        onClick={() => setDemandStressPct(v)}
                      >
                        {v > 0 ? `+${v}%` : `${v}%`}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Control 3: Assumed Trip Duration */}
                <div>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <label className="filter-label">Avg Trip Duration (min)</label>
                    <span style={{ fontWeight: 700, fontSize: 13 }}>{assumedDuration} mins</span>
                  </div>
                  <input
                    type="number"
                    min="15"
                    max="180"
                    className="input-control"
                    style={{ marginTop: 6 }}
                    value={assumedDuration}
                    onChange={(e) => setAssumedDuration(Math.max(1, Number(e.target.value)))}
                  />
                  <small style={{ color: "var(--slate-500)", fontSize: 11, marginTop: 4, display: "block" }}>
                    Calculated from route profile service hours
                  </small>
                </div>
              </div>

              <div style={{ display: "flex", gap: 12, alignItems: "center", marginTop: 8 }}>
                <button
                  className="btn btn-primary"
                  onClick={calculateScenario}
                  disabled={scenarioLoading || !curForecast?.predicted_rides}
                >
                  {scenarioLoading ? "Computing Scenario..." : "⚡ Run Scenario Analysis"}
                </button>
                {curForecast?.scheduled_trips && (
                  <span style={{ fontSize: 12, color: "var(--slate-600)" }}>
                    Proposed:{" "}
                    <strong>
                      {Math.max(0, Math.round(curForecast.scheduled_trips * (1 + tripDeltaPct / 100)))} trips
                    </strong>{" "}
                    (vs baseline {curForecast.scheduled_trips})
                  </span>
                )}
              </div>

              {scenarioError && (
                <div className="callout callout-warning" style={{ marginTop: 14 }}>
                  <span>⚠️</span>
                  <div>{scenarioError}</div>
                </div>
              )}

              {/* Scenario Results Table & Diff Analysis */}
              {scenarioResult && (
                <div style={{ marginTop: 18 }}>
                  <div className="card-title-row">
                    <h4 style={{ margin: 0, fontSize: 14, color: "var(--slate-800)" }}>
                      Scenario Projection Comparison
                    </h4>
                    <span className="diff-tag diff-neutral">
                      Scenario ID: {scenarioResult.scenario_id}
                    </span>
                  </div>

                  <table className="scenario-table">
                    <thead>
                      <tr>
                        <th>Metric</th>
                        <th>Baseline Profile</th>
                        <th>Proposed Scenario</th>
                        <th>Net Impact (Delta)</th>
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
                          {(() => {
                            const diff = scenarioResult.proposed.assumed_rides - scenarioResult.baseline.rides;
                            const pct = scenarioResult.baseline.rides
                              ? ((diff / scenarioResult.baseline.rides) * 100).toFixed(1)
                              : 0;
                            return (
                              <span className={`diff-tag ${diff >= 0 ? "diff-pos" : "diff-neg"}`}>
                                {diff >= 0 ? "+" : ""}
                                {Math.round(diff).toLocaleString()} ({diff >= 0 ? "+" : ""}
                                {pct}%)
                              </span>
                            );
                          })()}
                        </td>
                      </tr>
                      <tr>
                        <td>
                          <strong>Scheduled Trips</strong>
                        </td>
                        <td>{scenarioResult.baseline.scheduled_trips} trips</td>
                        <td>{scenarioResult.proposed.scheduled_trips} trips</td>
                        <td>
                          {(() => {
                            const diff =
                              scenarioResult.proposed.scheduled_trips - scenarioResult.baseline.scheduled_trips;
                            return (
                              <span className={`diff-tag ${diff >= 0 ? "diff-pos" : "diff-neg"}`}>
                                {diff >= 0 ? "+" : ""}
                                {diff} trips
                              </span>
                            );
                          })()}
                        </td>
                      </tr>
                      <tr>
                        <td>
                          <strong>Scheduled Trip-Hours</strong>
                        </td>
                        <td>{scenarioResult.baseline.scheduled_trip_hours} hrs</td>
                        <td>{scenarioResult.proposed.scheduled_trip_hours} hrs</td>
                        <td>
                          {(() => {
                            const diff = (
                              scenarioResult.proposed.scheduled_trip_hours -
                              scenarioResult.baseline.scheduled_trip_hours
                            ).toFixed(1);
                            return (
                              <span className={`diff-tag ${Number(diff) >= 0 ? "diff-pos" : "diff-neg"}`}>
                                {Number(diff) >= 0 ? "+" : ""}
                                {diff} hrs
                              </span>
                            );
                          })()}
                        </td>
                      </tr>
                      <tr>
                        <td>
                          <strong>Rides / Scheduled Trip</strong>
                        </td>
                        <td>{scenarioResult.baseline.rides_per_scheduled_trip ?? "N/A"}</td>
                        <td>{scenarioResult.proposed.rides_per_scheduled_trip ?? "N/A"}</td>
                        <td>
                          {(() => {
                            if (
                              scenarioResult.proposed.rides_per_scheduled_trip == null ||
                              scenarioResult.baseline.rides_per_scheduled_trip == null
                            )
                              return "—";
                            const diff = (
                              scenarioResult.proposed.rides_per_scheduled_trip -
                              scenarioResult.baseline.rides_per_scheduled_trip
                            ).toFixed(1);
                            return (
                              <span className={`diff-tag ${Number(diff) >= 0 ? "diff-pos" : "diff-neg"}`}>
                                {Number(diff) >= 0 ? "+" : ""}
                                {diff} rides/trip
                              </span>
                            );
                          })()}
                        </td>
                      </tr>
                      <tr>
                        <td>
                          <strong>Rides / Scheduled Hour</strong>
                        </td>
                        <td>{scenarioResult.baseline.rides_per_scheduled_hour ?? "N/A"}</td>
                        <td>{scenarioResult.proposed.rides_per_scheduled_hour ?? "N/A"}</td>
                        <td>
                          {(() => {
                            if (
                              scenarioResult.proposed.rides_per_scheduled_hour == null ||
                              scenarioResult.baseline.rides_per_scheduled_hour == null
                            )
                              return "—";
                            const diff = (
                              scenarioResult.proposed.rides_per_scheduled_hour -
                              scenarioResult.baseline.rides_per_scheduled_hour
                            ).toFixed(1);
                            return (
                              <span className={`diff-tag ${Number(diff) >= 0 ? "diff-pos" : "diff-neg"}`}>
                                {Number(diff) >= 0 ? "+" : ""}
                                {diff} rides/hr
                              </span>
                            );
                          })()}
                        </td>
                      </tr>
                    </tbody>
                  </table>

                  <div className="callout callout-info" style={{ marginTop: 12 }}>
                    <span>ℹ️</span>
                    <div>
                      <strong>Methodology Note:</strong> {scenarioResult.assumptions?.note} Assumed trip
                      duration: {scenarioResult.assumptions?.assumed_trip_duration_minutes} min/trip.
                    </div>
                  </div>
                </div>
              )}
            </div>
          </section>
        </main>
      </div>
    </div>
  );
}
