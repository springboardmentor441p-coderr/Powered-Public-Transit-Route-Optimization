import React, { useEffect, useState } from "react";
import {
  Activity, BarChart3, Calendar, Database, GitCompare, Layers, Play, Pause,
  SkipForward, RotateCcw, Sliders, Bell, MapPin, LogIn, LogOut, AlertTriangle,
  Shield, Radio, CheckCircle, Clock, PlusCircle
} from "lucide-react";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend
} from "recharts";
import {
  fetchCoverage, fetchRoutes, fetchRouteHistory, fetchRankings,
  compareRoutes, requestForecast, createReplaySession, controlReplaySession,
  runServiceScenario, login, logout, getStoredUser, fetchAlerts, acknowledgeAlert,
  fetchBroadcasts, createBroadcast, fetchHeatmapData, createScheduleUpdate,
  fetchScheduleUpdates, fetchNotifications
} from "./api/client";

type Tab = "overview" | "rankings" | "detail" | "compare" | "scenarios" | "heatmap" | "alerts" | "evaluation" | "coverage";

export default function App() {
  const [tab, setTab] = useState<Tab>("overview");
  const [coverage, setCoverage] = useState<any>(null);
  const [routes, setRoutes] = useState<any[]>([]);
  const [selectedRoute, setSelectedRoute] = useState("22");
  const [compareRouteB, setCompareRouteB] = useState("8");
  const [daytype, setDaytype] = useState("W");
  const [rankings, setRankings] = useState<any[]>([]);
  const [historyData, setHistoryData] = useState<any>(null);
  const [comparison, setComparison] = useState<any>(null);

  const [replay, setReplay] = useState<any>(null);
  const [forecast, setForecast] = useState<any>(null);

  const [proposedTrips, setProposedTrips] = useState(108);
  const [demandMult, setDemandMult] = useState(1.0);
  const [scenarioOut, setScenarioOut] = useState<any>(null);

  // Auth state
  const [user, setUser] = useState<any>(getStoredUser());
  const [showLoginModal, setShowLoginModal] = useState(false);
  const [loginUsername, setLoginUsername] = useState("");
  const [loginPassword, setLoginPassword] = useState("");
  const [loginError, setLoginError] = useState("");

  // Alerts & Notifications state
  const [alerts, setAlerts] = useState<any[]>([]);
  const [broadcasts, setBroadcasts] = useState<any[]>([]);
  const [heatmap, setHeatmap] = useState<any>(null);
  const [scheduleUpdates, setScheduleUpdates] = useState<any[]>([]);
  const [notifications, setNotifications] = useState<any[]>([]);

  // Emergency broadcast form state
  const [bcTitle, setBcTitle] = useState("");
  const [bcMessage, setBcMessage] = useState("");
  const [bcSeverity, setBcSeverity] = useState("warning");
  const [bcRoute, setBcRoute] = useState("79");

  // Schedule update form state
  const [schedTrips, setSchedTrips] = useState(120);
  const [schedReason, setSchedReason] = useState("Peak demand adjustment");

  useEffect(() => {
    fetchCoverage().then(setCoverage).catch(() => {});
    fetchRoutes().then((d) => setRoutes(d.routes || [])).catch(() => {});
    createReplaySession().then(setReplay).catch(() => {});
    loadAlertsAndBroadcasts();
  }, []);

  const loadAlertsAndBroadcasts = () => {
    fetchAlerts().then((d) => setAlerts(d.alerts || [])).catch(() => {});
    fetchBroadcasts().then((d) => setBroadcasts(d.broadcasts || [])).catch(() => {});
    fetchNotifications().then((d) => setNotifications(d.notifications || [])).catch(() => {});
    fetchScheduleUpdates().then((d) => setScheduleUpdates(d.updates || [])).catch(() => {});
  };

  useEffect(() => {
    fetchRankings(daytype).then((d) => setRankings(d.rankings || [])).catch(() => {});
    fetchHeatmapData(daytype).then(setHeatmap).catch(() => {});
  }, [daytype]);

  useEffect(() => {
    if (!replay) return;
    const vDate = new Date(replay.current_virtual_date);
    vDate.setDate(vDate.getDate() - 1);
    const cutoff = vDate.toISOString().slice(0, 10);

    fetchRouteHistory(selectedRoute, cutoff).then(setHistoryData).catch(() => {});
    requestForecast(selectedRoute, replay.current_virtual_date, replay.current_virtual_date).then(setForecast).catch(() => {});
  }, [selectedRoute, replay]);

  useEffect(() => {
    compareRoutes(selectedRoute, compareRouteB, daytype).then(setComparison).catch(() => {});
  }, [selectedRoute, compareRouteB, daytype]);

  useEffect(() => {
    if (!replay || replay.status !== "running") return;
    const timer = setInterval(() => {
      controlReplaySession(replay.session_id, "advance").then(setReplay);
    }, (replay.speed_seconds || 5) * 1000);
    return () => clearInterval(timer);
  }, [replay]);

  const handleReplayAction = async (action: "start" | "pause" | "advance" | "reset") => {
    if (!replay) return;
    const updated = await controlReplaySession(replay.session_id, action);
    setReplay(updated);
  };

  const handleRunScenario = async () => {
    const res = await runServiceScenario({
      route: selectedRoute,
      service_date: "2026-06-03",
      proposed_trips: proposedTrips,
      demand_multiplier: demandMult,
    });
    setScenarioOut(res);
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoginError("");
    try {
      const data = await login(loginUsername, loginPassword);
      setUser(data.user);
      setShowLoginModal(false);
      setLoginUsername("");
      setLoginPassword("");
    } catch {
      setLoginError("Invalid username or password");
    }
  };

  const handleQuickLogin = async (u: string, p: string) => {
    setLoginError("");
    try {
      const data = await login(u, p);
      setUser(data.user);
      setShowLoginModal(false);
    } catch {
      setLoginError("Login failed");
    }
  };

  const handleLogout = () => {
    logout();
    setUser(null);
  };

  const handleAcknowledgeAlert = async (id: string) => {
    await acknowledgeAlert(id);
    loadAlertsAndBroadcasts();
  };

  const handleCreateBroadcast = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!bcTitle || !bcMessage) return;
    try {
      await createBroadcast({
        title: bcTitle,
        message: bcMessage,
        severity: bcSeverity,
        affected_routes: [bcRoute],
      });
      setBcTitle("");
      setBcMessage("");
      loadAlertsAndBroadcasts();
    } catch (err: any) {
      alert(err.message || "Failed to broadcast");
    }
  };

  const handleApplyScheduleUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await createScheduleUpdate({
        route: selectedRoute,
        service_date: "2026-06-03",
        new_scheduled_trips: schedTrips,
        reason: schedReason,
      });
      loadAlertsAndBroadcasts();
      alert(`Schedule update applied for Route ${selectedRoute}!`);
    } catch (err: any) {
      alert(err.message || "Failed to update schedule (Admin or Operator role required)");
    }
  };

  const activeBroadcasts = broadcasts.filter((b) => b.active);
  const unacknowledgedAlerts = alerts.filter((a) => !a.acknowledged);

  const navItems: { id: Tab; label: string; icon: React.ReactNode; badge?: number }[] = [
    { id: "overview", label: "Network Overview", icon: <Activity size={16} /> },
    { id: "rankings", label: "Review Priorities", icon: <BarChart3 size={16} /> },
    { id: "detail", label: "Route Detail & Replay", icon: <Calendar size={16} /> },
    { id: "compare", label: "Compare Routes", icon: <GitCompare size={16} /> },
    { id: "scenarios", label: "Service Scenarios", icon: <Sliders size={16} /> },
    { id: "heatmap", label: "Congestion Heatmap", icon: <MapPin size={16} /> },
    { id: "alerts", label: "Alerts & Notifications", icon: <Bell size={16} />, badge: unacknowledgedAlerts.length },
    { id: "evaluation", label: "Model Evaluation", icon: <Layers size={16} /> },
    { id: "coverage", label: "Data & Coverage", icon: <Database size={16} /> },
  ];

  return (
    <div className="min-h-screen flex flex-col bg-slate-950 text-slate-100">
      {/* Active Emergency Broadcast Ticker */}
      {activeBroadcasts.length > 0 && (
        <div className="bg-rose-950 border-b border-rose-800 px-6 py-2 flex items-center justify-between text-xs text-rose-200">
          <div className="flex items-center gap-2">
            <Radio size={14} className="animate-pulse text-rose-400" />
            <span className="font-bold uppercase tracking-wider text-rose-300">Emergency Alert:</span>
            <span>{activeBroadcasts[0].title} — {activeBroadcasts[0].message}</span>
            <span className="text-rose-400">(Routes: {activeBroadcasts[0].affected_routes.join(", ")})</span>
          </div>
          <span className="text-rose-400 font-mono">{activeBroadcasts[0].created_at?.slice(11, 16)} UTC</span>
        </div>
      )}

      {/* Main Header */}
      <header className="bg-slate-900 border-b border-slate-800 px-6 py-4 flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold text-teal-400">RouteRanker</h1>
            <span className="px-1.5 py-0.5 rounded text-[10px] bg-teal-900/60 text-teal-300 border border-teal-700">v4.0 Complete</span>
          </div>
          <p className="text-xs text-slate-400">Transit Demand Forecasting, Route Grouping & Conditional Scenario Engine</p>
        </div>

        <div className="flex items-center gap-3">
          {/* Historical Replay Clock */}
          {replay && (
            <div className="flex items-center gap-3 bg-slate-950 border border-slate-700 rounded-lg px-4 py-2 text-xs">
              <span className="px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 font-semibold">Historical Replay</span>
              <div>
                <span className="text-slate-400">Virtual Date: </span>
                <span className="font-mono font-bold text-white">{replay.current_virtual_date}</span>
              </div>
              <span className="text-slate-500">| Assumption: D-1 rides available</span>
              <div className="flex items-center gap-1 ml-2">
                {replay.status !== "running" ? (
                  <button onClick={() => handleReplayAction("start")} className="p-1.5 bg-teal-600 hover:bg-teal-500 rounded text-white" title="Start">
                    <Play size={14} />
                  </button>
                ) : (
                  <button onClick={() => handleReplayAction("pause")} className="p-1.5 bg-amber-600 hover:bg-amber-500 rounded text-white" title="Pause">
                    <Pause size={14} />
                  </button>
                )}
                <button onClick={() => handleReplayAction("advance")} className="p-1.5 bg-slate-800 hover:bg-slate-700 rounded" title="Advance 1 Day">
                  <SkipForward size={14} />
                </button>
                <button onClick={() => handleReplayAction("reset")} className="p-1.5 bg-slate-800 hover:bg-slate-700 rounded" title="Reset">
                  <RotateCcw size={14} />
                </button>
              </div>
            </div>
          )}

          {/* User Auth Section */}
          {user ? (
            <div className="flex items-center gap-2 bg-slate-950 border border-slate-700 rounded-lg px-3 py-1.5 text-xs">
              <Shield size={14} className={user.role === "admin" ? "text-purple-400" : (user.role === "operator" ? "text-teal-400" : "text-slate-400")} />
              <div>
                <div className="font-semibold text-white">{user.name}</div>
                <div className="text-[10px] text-slate-400 capitalize">{user.role}</div>
              </div>
              <button onClick={handleLogout} className="ml-2 text-slate-400 hover:text-rose-400 p-1" title="Sign Out">
                <LogOut size={14} />
              </button>
            </div>
          ) : (
            <button
              onClick={() => setShowLoginModal(true)}
              className="flex items-center gap-1.5 px-3 py-2 bg-teal-600 hover:bg-teal-500 rounded-lg text-xs font-medium text-white transition"
            >
              <LogIn size={14} />
              Sign In
            </button>
          )}
        </div>
      </header>

      {/* Navigation Tabs */}
      <nav className="bg-slate-900/60 border-b border-slate-800 px-6 flex gap-2 overflow-x-auto">
        {navItems.map((n) => (
          <button
            key={n.id}
            onClick={() => setTab(n.id)}
            className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition relative ${
              tab === n.id ? "border-teal-400 text-teal-300" : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            {n.icon}
            {n.label}
            {n.badge !== undefined && n.badge > 0 && (
              <span className="ml-1 px-1.5 py-0.2 rounded-full text-[10px] bg-rose-600 text-white font-bold">
                {n.badge}
              </span>
            )}
          </button>
        ))}
      </nav>

      {/* Filter Toolbar */}
      <div className="bg-slate-900/30 border-b border-slate-800/80 px-6 py-3 flex flex-wrap items-center justify-between gap-4 text-sm">
        <div className="flex flex-wrap items-center gap-4">
          <label className="flex items-center gap-2">
            <span className="text-slate-400">Route:</span>
            <select
              value={selectedRoute}
              onChange={(e) => setSelectedRoute(e.target.value)}
              className="bg-slate-900 border border-slate-700 rounded px-2.5 py-1 text-white"
            >
              {routes.map((r) => (
                <option key={r.route} value={r.route}>
                  Route {r.route} ({r.cluster_label})
                </option>
              ))}
            </select>
          </label>

          <label className="flex items-center gap-2">
            <span className="text-slate-400">Day Type:</span>
            <select
              value={daytype}
              onChange={(e) => setDaytype(e.target.value)}
              className="bg-slate-900 border border-slate-700 rounded px-2.5 py-1 text-white"
            >
              <option value="W">Weekday (W)</option>
              <option value="A">Saturday (A)</option>
              <option value="U">Sunday / Holiday (U)</option>
            </select>
          </label>
        </div>

        {/* Overcrowding indicator pill */}
        {unacknowledgedAlerts.length > 0 && (
          <div
            onClick={() => setTab("alerts")}
            className="cursor-pointer flex items-center gap-1.5 px-2.5 py-1 rounded bg-amber-500/20 text-amber-300 border border-amber-600/40 text-xs hover:bg-amber-500/30 transition"
          >
            <AlertTriangle size={13} />
            <span>{unacknowledgedAlerts.length} Active Overcrowding Alert{unacknowledgedAlerts.length > 1 ? "s" : ""}</span>
          </div>
        )}
      </div>

      {/* Main Content Area */}
      <main className="flex-1 p-6 max-w-7xl w-full mx-auto space-y-6">
        {/* Tab 1: Network Overview */}
        {tab === "overview" && coverage && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
                <div className="text-xs text-slate-400">Clean Ridership Rows</div>
                <div className="text-2xl font-bold mt-1">{coverage.ridership_summary.clean_rows.toLocaleString()}</div>
                <div className="text-xs text-slate-500 mt-1">{coverage.ridership_summary.min_date} to {coverage.ridership_summary.max_date}</div>
              </div>
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
                <div className="text-xs text-slate-400">Matched Route/Date Pairs</div>
                <div className="text-2xl font-bold text-teal-400 mt-1">{coverage.matched_reconciliation.matched_rows.toLocaleString()}</div>
                <div className="text-xs text-slate-500 mt-1">{coverage.matched_reconciliation.matched_routes} matched routes</div>
              </div>
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
                <div className="text-xs text-slate-400">Ridership Without Schedule</div>
                <div className="text-2xl font-bold text-amber-400 mt-1">{coverage.matched_reconciliation.ridership_without_schedule_rows}</div>
                <div className="text-xs text-slate-500 mt-1">Retained for demand-only models</div>
              </div>
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
                <div className="text-xs text-slate-400">Selected Forecaster WAPE</div>
                <div className="text-2xl font-bold text-indigo-400 mt-1">
                  {coverage.model_evaluation?.matched_service?.models?.[coverage.model_evaluation?.matched_service?.selected_serving_model]?.test?.wape_pct}%
                </div>
                <div className="text-xs text-slate-500 mt-1">Model: {coverage.model_evaluation?.matched_service?.selected_serving_model}</div>
              </div>
            </div>

            <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
              <h2 className="text-base font-semibold mb-3">Route Groupings (Pre-Test KMeans Tiers)</h2>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {routes.map((r) => (
                  <div key={r.route} className="bg-slate-950 border border-slate-800 rounded-lg p-3 flex justify-between items-center">
                    <div>
                      <div className="font-semibold">Route {r.route}</div>
                      <div className="text-xs text-slate-400">{r.cluster_label}</div>
                    </div>
                    <div className="text-right text-xs text-slate-400">
                      {r.has_gtfs_schedule ? `${r.served_stop_count} stops (${Math.round((r.exclusive_stop_fraction || 0) * 100)}% excl.)` : "No GTFS schedule"}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Tab 2: Review Priorities */}
        {tab === "rankings" && (
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
            <h2 className="text-base font-semibold mb-1">Review Priorities — Rides per Scheduled Service Hour ({daytype})</h2>
            <p className="text-xs text-slate-400 mb-4">Requires &gt;= 20 matched service days. Ineligible routes remain unranked with visible reasons.</p>
            <div className="overflow-x-auto">
              <table className="w-full text-sm text-left">
                <thead className="text-xs uppercase bg-slate-950 text-slate-400">
                  <tr>
                    <th className="px-4 py-3">Rank</th>
                    <th className="px-4 py-3">Route</th>
                    <th className="px-4 py-3">Observed Days</th>
                    <th className="px-4 py-3">Mean Daily Rides</th>
                    <th className="px-4 py-3">Rides / Trip</th>
                    <th className="px-4 py-3">Rides / Service Hour</th>
                    <th className="px-4 py-3">Eligibility Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800">
                  {rankings.map((row) => (
                    <tr key={row.route} className="hover:bg-slate-800/40">
                      <td className="px-4 py-3 font-mono">{row.service_productivity_metric_rank ?? "—"}</td>
                      <td className="px-4 py-3 font-semibold">Route {row.route}</td>
                      <td className="px-4 py-3">{row.observed_dates}</td>
                      <td className="px-4 py-3">{Math.round(row.mean_daily_rides).toLocaleString()}</td>
                      <td className="px-4 py-3">{row.rides_per_scheduled_trip?.toFixed(2) ?? "N/A"}</td>
                      <td className="px-4 py-3 text-teal-400 font-semibold">{row.rides_per_scheduled_hour?.toFixed(2) ?? "N/A"}</td>
                      <td className="px-4 py-3 text-xs text-slate-400">{row.eligibility_reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Tab 3: Route Detail & Replay */}
        {tab === "detail" && (
          <div className="space-y-6">
            {forecast && (
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 grid grid-cols-1 md:grid-cols-4 gap-4">
                <div>
                  <div className="text-xs text-slate-400">Target Forecast Date</div>
                  <div className="text-lg font-bold">{forecast.target_date}</div>
                  <div className="text-xs text-amber-400 mt-1">Status: {forecast.forecast_status}</div>
                </div>
                <div>
                  <div className="text-xs text-slate-400">Predicted Daily Rides</div>
                  <div className="text-2xl font-bold text-teal-400">
                    {forecast.predicted_rides !== null ? `${forecast.predicted_rides.toLocaleString()} rides/day` : "Unavailable"}
                  </div>
                  <div className="text-xs text-slate-500 mt-1">{forecast.model_used || forecast.reason}</div>
                </div>
                <div>
                  <div className="text-xs text-slate-400">Latest Permitted Ride History</div>
                  <div className="text-lg font-mono">{forecast.latest_available_ride_date}</div>
                  <div className="text-xs text-slate-500 mt-1">No future target leakage</div>
                </div>
                <div>
                  <div className="text-xs text-slate-400">Schedule Provenance</div>
                  <div className="text-sm font-mono">{forecast.schedule_snapshot || "Demand-only fallback"}</div>
                </div>
              </div>
            )}

            {historyData && (
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
                <h3 className="text-base font-semibold mb-1">Observed Rides History (Cutoff: {historyData.cutoff_date})</h3>
                <p className="text-xs text-slate-400 mb-4">Only observations revealed up to the virtual replay cutoff are displayed.</p>
                <div className="h-72">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={historyData.history?.slice(-60) || []}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                      <XAxis dataKey="date" tick={{ fill: "#94a3b8", fontSize: 11 }} />
                      <YAxis tick={{ fill: "#94a3b8", fontSize: 11 }} />
                      <Tooltip contentStyle={{ backgroundColor: "#0f172a", borderColor: "#334155" }} />
                      <Legend />
                      <Line type="monotone" dataKey="rides" name="Recorded Rides/Day" stroke="#2dd4bf" strokeWidth={2} dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Tab 4: Compare Routes */}
        {tab === "compare" && comparison && (
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4">
            <div className="flex items-center gap-4">
              <h2 className="text-base font-semibold">Side-by-Side Route Comparison ({daytype})</h2>
              <select
                value={compareRouteB}
                onChange={(e) => setCompareRouteB(e.target.value)}
                className="bg-slate-950 border border-slate-700 rounded px-2.5 py-1 text-sm"
              >
                {routes.map((r) => (
                  <option key={r.route} value={r.route}>Compare with Route {r.route}</option>
                ))}
              </select>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {[comparison.route_a_profile?.[0], comparison.route_b_profile?.[0]].map((p, i) =>
                p ? (
                  <div key={i} className="bg-slate-950 border border-slate-800 rounded-lg p-4 space-y-2">
                    <div className="text-lg font-bold text-teal-400">Route {p.route}</div>
                    <div className="text-sm">Mean Daily Rides: <span className="font-semibold">{Math.round(p.mean_daily_rides).toLocaleString()}</span></div>
                    <div className="text-sm">Rides / Scheduled Trip: <span className="font-semibold">{p.rides_per_scheduled_trip?.toFixed(2)}</span></div>
                    <div className="text-sm">Rides / Scheduled Hour: <span className="font-semibold">{p.rides_per_scheduled_hour?.toFixed(2)}</span></div>
                  </div>
                ) : (
                  <div key={i} className="bg-slate-950 border border-slate-800 rounded-lg p-4 text-slate-400">No matched profile for selected day type.</div>
                )
              )}
            </div>
            <div className="bg-slate-950 border border-slate-800 rounded-lg p-4 text-sm">
              <div className="font-semibold mb-1">Corridor Stop Overlap</div>
              {comparison.stop_overlap?.length ? (
                <p>
                  Shared Stops: <strong>{comparison.stop_overlap[0].shared_stop_count}</strong> | Jaccard Overlap:{" "}
                  <strong>{(comparison.stop_overlap[0].jaccard_stop_overlap * 100).toFixed(1)}%</strong> | Smaller-Route Coverage:{" "}
                  <strong>{(comparison.stop_overlap[0].smaller_route_stop_overlap * 100).toFixed(1)}%</strong>
                </p>
              ) : (
                <p className="text-slate-400">Zero shared physical stop IDs between these routes.</p>
              )}
            </div>
          </div>
        )}

        {/* Tab 5: Service Scenarios & Dynamic Schedule Updates */}
        {tab === "scenarios" && (
          <div className="space-y-6">
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-5">
              <div>
                <h2 className="text-base font-semibold">Conditional Service Scenario Calculator</h2>
                <p className="text-xs text-slate-400">Adjust planned daily trips or test hypothetical demand stress while keeping duration & causal assumptions explicit.</p>
              </div>
              <div className="flex flex-wrap items-end gap-4">
                <div>
                  <label className="block text-xs text-slate-400 mb-1">Proposed Scheduled Trips / Day</label>
                  <input
                    type="number"
                    value={proposedTrips}
                    onChange={(e) => setProposedTrips(Number(e.target.value))}
                    className="bg-slate-950 border border-slate-700 rounded px-3 py-1.5 text-sm w-44 text-white"
                  />
                </div>
                <div>
                  <label className="block text-xs text-slate-400 mb-1">Assumed Demand Multiplier (1.0 = fixed)</label>
                  <input
                    type="number"
                    step="0.05"
                    value={demandMult}
                    onChange={(e) => setDemandMult(Number(e.target.value))}
                    className="bg-slate-950 border border-slate-700 rounded px-3 py-1.5 text-sm w-44 text-white"
                  />
                </div>
                <button onClick={handleRunScenario} className="px-4 py-1.5 bg-teal-600 hover:bg-teal-500 rounded text-sm font-medium text-white transition">
                  Calculate Scenario
                </button>
              </div>

              {scenarioOut && (
                <div className="space-y-4">
                  <table className="w-full text-sm text-left bg-slate-950 border border-slate-800 rounded-lg overflow-hidden">
                    <thead className="text-xs uppercase bg-slate-900 text-slate-400">
                      <tr>
                        <th className="px-4 py-2">Indicator</th>
                        <th className="px-4 py-2">Baseline (2026-06-03)</th>
                        <th className="px-4 py-2">Scenario Output</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800">
                      <tr>
                        <td className="px-4 py-2">Daily Rides</td>
                        <td className="px-4 py-2">{scenarioOut.baseline.rides.toLocaleString()}</td>
                        <td className="px-4 py-2 text-teal-400 font-semibold">{scenarioOut.scenario.rides.toLocaleString()}</td>
                      </tr>
                      <tr>
                        <td className="px-4 py-2">Scheduled Trips / Day</td>
                        <td className="px-4 py-2">{scenarioOut.baseline.scheduled_trips}</td>
                        <td className="px-4 py-2">{scenarioOut.scenario.scheduled_trips} ({scenarioOut.deltas.trips_pct_change > 0 ? "+" : ""}{scenarioOut.deltas.trips_pct_change}%)</td>
                      </tr>
                      <tr>
                        <td className="px-4 py-2">Scheduled Service Hours</td>
                        <td className="px-4 py-2">{scenarioOut.baseline.scheduled_service_hours ?? "N/A"}</td>
                        <td className="px-4 py-2">{scenarioOut.scenario.scheduled_service_hours}</td>
                      </tr>
                      <tr>
                        <td className="px-4 py-2">Rides per Scheduled Trip</td>
                        <td className="px-4 py-2">{scenarioOut.baseline.rides_per_scheduled_trip}</td>
                        <td className="px-4 py-2 font-semibold">{scenarioOut.scenario.rides_per_scheduled_trip}</td>
                      </tr>
                      <tr>
                        <td className="px-4 py-2">Rides per Scheduled Hour</td>
                        <td className="px-4 py-2">{scenarioOut.baseline.rides_per_scheduled_hour ?? "N/A"}</td>
                        <td className="px-4 py-2 font-semibold">{scenarioOut.scenario.rides_per_scheduled_hour}</td>
                      </tr>
                    </tbody>
                  </table>
                  <div className="text-xs text-amber-300/90 bg-amber-950/30 border border-amber-800/50 rounded-lg p-3">
                    <strong>Assumptions:</strong> Mean trip duration = {scenarioOut.assumptions?.assumed_mean_duration_minutes} mins. {scenarioOut.assumptions?.note}
                  </div>
                </div>
              )}
            </div>

            {/* Dynamic Schedule Update (Milestone 2 & 3) */}
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-base font-semibold">Apply Live Schedule Modification</h3>
                  <p className="text-xs text-slate-400">Push updated service frequency directly into the operational database. (Requires Operator or Admin role)</p>
                </div>
                {user && (user.role === "admin" || user.role === "operator") ? (
                  <span className="px-2 py-0.5 rounded text-[10px] bg-emerald-950 text-emerald-300 border border-emerald-700">Authorized: {user.role}</span>
                ) : (
                  <span className="px-2 py-0.5 rounded text-[10px] bg-slate-800 text-slate-400">Read-Only (Sign in as Operator to update)</span>
                )}
              </div>

              <form onSubmit={handleApplyScheduleUpdate} className="flex flex-wrap items-end gap-3 text-sm">
                <div>
                  <label className="block text-xs text-slate-400 mb-1">Target Route</label>
                  <input
                    type="text"
                    disabled
                    value={`Route ${selectedRoute}`}
                    className="bg-slate-950 border border-slate-700 rounded px-3 py-1.5 text-xs text-slate-400 w-32"
                  />
                </div>
                <div>
                  <label className="block text-xs text-slate-400 mb-1">New Daily Trips</label>
                  <input
                    type="number"
                    value={schedTrips}
                    onChange={(e) => setSchedTrips(Number(e.target.value))}
                    className="bg-slate-950 border border-slate-700 rounded px-3 py-1.5 text-xs text-white w-32"
                  />
                </div>
                <div className="flex-1 min-w-[200px]">
                  <label className="block text-xs text-slate-400 mb-1">Reason for Modification</label>
                  <input
                    type="text"
                    value={schedReason}
                    onChange={(e) => setSchedReason(e.target.value)}
                    placeholder="e.g., Summer rush peak frequency adjustment"
                    className="w-full bg-slate-950 border border-slate-700 rounded px-3 py-1.5 text-xs text-white"
                  />
                </div>
                <button
                  type="submit"
                  disabled={!user || (user.role !== "admin" && user.role !== "operator")}
                  className="px-4 py-1.5 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed rounded text-xs font-medium text-white transition flex items-center gap-1.5"
                >
                  <PlusCircle size={14} />
                  Apply Schedule Change
                </button>
              </form>

              {scheduleUpdates.length > 0 && (
                <div className="mt-4">
                  <div className="text-xs font-semibold text-slate-400 mb-2">Applied Schedule Updates Log ({scheduleUpdates.length}):</div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs text-left bg-slate-950 border border-slate-800 rounded">
                      <thead className="bg-slate-900 text-slate-400">
                        <tr>
                          <th className="px-3 py-2">Update ID</th>
                          <th className="px-3 py-2">Route</th>
                          <th className="px-3 py-2">Service Date</th>
                          <th className="px-3 py-2">New Trips</th>
                          <th className="px-3 py-2">Reason</th>
                          <th className="px-3 py-2">Author</th>
                          <th className="px-3 py-2">Status</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800">
                        {scheduleUpdates.map((u) => (
                          <tr key={u.update_id}>
                            <td className="px-3 py-2 font-mono text-slate-400">{u.update_id}</td>
                            <td className="px-3 py-2 font-semibold">Route {u.route}</td>
                            <td className="px-3 py-2">{u.service_date}</td>
                            <td className="px-3 py-2 text-emerald-400 font-bold">{u.new_scheduled_trips}</td>
                            <td className="px-3 py-2">{u.reason}</td>
                            <td className="px-3 py-2 font-mono text-slate-400">{u.created_by}</td>
                            <td className="px-3 py-2 text-emerald-400 font-semibold">{u.status}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Tab 6: Congestion Heatmap (Milestone 2 & 3) */}
        {tab === "heatmap" && (
          <div className="space-y-6">
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
              <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
                <div>
                  <h2 className="text-base font-semibold">Corridor Congestion & Passenger Density Heatmap ({daytype})</h2>
                  <p className="text-xs text-slate-400">Spatial passenger intensity calculated from rides per scheduled service hour.</p>
                </div>
                {heatmap && (
                  <div className="flex items-center gap-3 text-xs">
                    <span className="flex items-center gap-1 text-rose-400">
                      <span className="w-2.5 h-2.5 rounded-full bg-rose-500"></span>
                      Critical ({heatmap.summary.critical_routes} routes)
                    </span>
                    <span className="flex items-center gap-1 text-amber-400">
                      <span className="w-2.5 h-2.5 rounded-full bg-amber-500"></span>
                      High ({heatmap.summary.high_routes} routes)
                    </span>
                    <span className="flex items-center gap-1 text-teal-400">
                      <span className="w-2.5 h-2.5 rounded-full bg-teal-500"></span>
                      Moderate/Normal
                    </span>
                  </div>
                )}
              </div>

              {/* Congestion Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {rankings.map((r) => {
                  const intensity = r.rides_per_scheduled_hour || 0;
                  const isCritical = intensity > 280;
                  const isHigh = intensity > 200 && intensity <= 280;
                  const colorClass = isCritical
                    ? "border-rose-700 bg-rose-950/20 text-rose-300"
                    : (isHigh ? "border-amber-700 bg-amber-950/20 text-amber-300" : "border-slate-800 bg-slate-950 text-slate-300");

                  return (
                    <div key={r.route} className={`border rounded-xl p-4 space-y-3 transition ${colorClass}`}>
                      <div className="flex items-center justify-between">
                        <div className="text-base font-bold text-white">Route {r.route}</div>
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
                          isCritical ? "bg-rose-500/20 text-rose-300 border border-rose-600" :
                          (isHigh ? "bg-amber-500/20 text-amber-300 border border-amber-600" : "bg-teal-500/20 text-teal-300 border border-teal-600")
                        }`}>
                          {isCritical ? "Critical Congestion" : (isHigh ? "High Volume" : "Moderate Load")}
                        </span>
                      </div>

                      {/* Visual Progress Bar */}
                      <div>
                        <div className="flex justify-between text-xs text-slate-400 mb-1">
                          <span>Congestion Index</span>
                          <span className="font-mono font-bold text-white">{intensity.toFixed(1)} rides/hr</span>
                        </div>
                        <div className="w-full h-2 bg-slate-800 rounded-full overflow-hidden">
                          <div
                            className={`h-full ${isCritical ? "bg-rose-500" : (isHigh ? "bg-amber-500" : "bg-teal-500")}`}
                            style={{ width: `${Math.min(100, (intensity / 350) * 100)}%` }}
                          ></div>
                        </div>
                      </div>

                      <div className="grid grid-cols-2 gap-2 text-xs text-slate-400 pt-1 border-t border-slate-800/80">
                        <div>Daily Volume: <span className="text-white font-semibold">{Math.round(r.mean_daily_rides).toLocaleString()}</span></div>
                        <div>Rides / Trip: <span className="text-white font-semibold">{r.rides_per_scheduled_trip?.toFixed(1)}</span></div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}

        {/* Tab 7: Alerts, Notifications & Emergency Announcements (Milestone 3) */}
        {tab === "alerts" && (
          <div className="space-y-6">
            {/* Active Overcrowding Alerts */}
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-base font-semibold">Active Overcrowding & Capacity Alerts</h2>
                  <p className="text-xs text-slate-400">Automated threshold triggers evaluated against scheduled passenger density.</p>
                </div>
                <span className="px-2.5 py-1 rounded bg-slate-800 text-xs text-slate-300 font-mono">
                  {unacknowledgedAlerts.length} Active / {alerts.length} Total
                </span>
              </div>

              <div className="space-y-3">
                {alerts.length === 0 ? (
                  <div className="text-xs text-slate-400 p-4 text-center bg-slate-950 rounded-lg">No active capacity alerts. All routes within safe operational thresholds.</div>
                ) : (
                  alerts.map((a) => (
                    <div
                      key={a.alert_id}
                      className={`p-4 rounded-xl border flex flex-wrap items-center justify-between gap-3 ${
                        a.severity === "critical"
                          ? "bg-rose-950/30 border-rose-800/60 text-rose-200"
                          : "bg-amber-950/30 border-amber-800/60 text-amber-200"
                      } ${a.acknowledged ? "opacity-50" : ""}`}
                    >
                      <div className="flex items-center gap-3">
                        <AlertTriangle size={20} className={a.severity === "critical" ? "text-rose-400" : "text-amber-400"} />
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-bold text-white">Route {a.route}</span>
                            <span className="px-1.5 py-0.2 rounded text-[10px] uppercase font-bold tracking-wider bg-rose-500/20 text-rose-300">
                              {a.severity}
                            </span>
                            <span className="text-xs text-slate-400 font-mono">[{a.metric}: {a.metric_value}]</span>
                          </div>
                          <div className="text-xs mt-0.5">{a.message}</div>
                          <div className="text-[10px] text-slate-500 mt-1 flex items-center gap-2">
                            <Clock size={10} />
                            <span>Triggered: {a.triggered_at}</span>
                            <span>• Day Type: {a.daytype}</span>
                          </div>
                        </div>
                      </div>

                      <div>
                        {a.acknowledged ? (
                          <span className="flex items-center gap-1 text-xs text-emerald-400 font-medium">
                            <CheckCircle size={14} /> Acknowledged
                          </span>
                        ) : (
                          <button
                            onClick={() => handleAcknowledgeAlert(a.alert_id)}
                            className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-xs font-medium text-white rounded transition"
                          >
                            Acknowledge
                          </button>
                        )}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* Emergency Broadcast System */}
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-base font-semibold">Emergency Broadcast & Delay Announcements</h3>
                  <p className="text-xs text-slate-400">Broadcast immediate transit delays, signal failures, or emergency notices to all system dashboards.</p>
                </div>
                {user && (user.role === "admin" || user.role === "operator") && (
                  <span className="px-2 py-0.5 rounded text-[10px] bg-purple-950 text-purple-300 border border-purple-700">Operator Access Active</span>
                )}
              </div>

              {/* Form */}
              <form onSubmit={handleCreateBroadcast} className="bg-slate-950 border border-slate-800 rounded-lg p-4 space-y-3">
                <div className="text-xs font-semibold text-slate-300">Create New Public Announcement</div>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  <div>
                    <label className="block text-[11px] text-slate-400 mb-1">Announcement Title</label>
                    <input
                      type="text"
                      placeholder="e.g., Heavy Corridor Delay"
                      value={bcTitle}
                      onChange={(e) => setBcTitle(e.target.value)}
                      className="w-full bg-slate-900 border border-slate-700 rounded px-3 py-1.5 text-xs text-white"
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] text-slate-400 mb-1">Severity Level</label>
                    <select
                      value={bcSeverity}
                      onChange={(e) => setBcSeverity(e.target.value)}
                      className="w-full bg-slate-900 border border-slate-700 rounded px-3 py-1.5 text-xs text-white"
                    >
                      <option value="warning">Warning</option>
                      <option value="critical">Critical</option>
                      <option value="emergency">Emergency</option>
                      <option value="info">Informational</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-[11px] text-slate-400 mb-1">Affected Route</label>
                    <select
                      value={bcRoute}
                      onChange={(e) => setBcRoute(e.target.value)}
                      className="w-full bg-slate-900 border border-slate-700 rounded px-3 py-1.5 text-xs text-white"
                    >
                      {routes.map((r) => (
                        <option key={r.route} value={r.route}>Route {r.route}</option>
                      ))}
                    </select>
                  </div>
                </div>

                <div>
                  <label className="block text-[11px] text-slate-400 mb-1">Detailed Message</label>
                  <input
                    type="text"
                    placeholder="e.g., Signal disruption near 79th/Dan Ryan. Expect 15-20 min delays. Shuttles dispatched."
                    value={bcMessage}
                    onChange={(e) => setBcMessage(e.target.value)}
                    className="w-full bg-slate-900 border border-slate-700 rounded px-3 py-1.5 text-xs text-white"
                  />
                </div>

                <div className="flex justify-end">
                  <button
                    type="submit"
                    disabled={!user || (user.role !== "admin" && user.role !== "operator")}
                    className="px-4 py-1.5 bg-rose-600 hover:bg-rose-500 disabled:opacity-40 disabled:cursor-not-allowed rounded text-xs font-medium text-white transition flex items-center gap-1.5"
                  >
                    <Radio size={14} />
                    Broadcast Announcement
                  </button>
                </div>
              </form>

              {/* Active Broadcasts List */}
              <div className="space-y-2">
                <div className="text-xs font-semibold text-slate-400">Published Broadcasts ({broadcasts.length}):</div>
                {broadcasts.map((b) => (
                  <div key={b.broadcast_id} className="bg-slate-950 border border-slate-800 rounded-lg p-3 flex items-center justify-between text-xs">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-white">{b.title}</span>
                        <span className="px-1.5 py-0.2 rounded text-[10px] bg-rose-900 text-rose-300 font-bold uppercase">{b.severity}</span>
                        <span className="text-slate-500">Routes: {b.affected_routes.join(", ")}</span>
                      </div>
                      <div className="text-slate-400 mt-1">{b.message}</div>
                    </div>
                    <div className="text-right">
                      <span className={`px-2 py-0.5 rounded text-[10px] ${b.active ? "bg-emerald-950 text-emerald-300 border border-emerald-800" : "bg-slate-800 text-slate-500"}`}>
                        {b.active ? "Active Banner" : "Inactive"}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Notification Activity Log */}
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-3">
              <h3 className="text-base font-semibold">System Notification Audit Log</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-xs text-left bg-slate-950 border border-slate-800 rounded">
                  <thead className="bg-slate-900 text-slate-400">
                    <tr>
                      <th className="px-3 py-2">Event Type</th>
                      <th className="px-3 py-2">Details</th>
                      <th className="px-3 py-2">Timestamp</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800 font-mono">
                    {notifications.slice(0, 10).map((n, i) => (
                      <tr key={i}>
                        <td className="px-3 py-2 text-teal-400">{n.type}</td>
                        <td className="px-3 py-2 text-slate-300">{n.title || n.alert_id || n.route || "—"}</td>
                        <td className="px-3 py-2 text-slate-500">{n.timestamp}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* Tab 8: Model Evaluation */}
        {tab === "evaluation" && coverage && (
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4">
            <h2 className="text-base font-semibold">Chronological Model Evaluation vs. Seasonal Baselines</h2>
            <p className="text-xs text-slate-400">Policy: {coverage.model_evaluation?.missing_history_policy}</p>
            <table className="w-full text-sm text-left bg-slate-950 border border-slate-800">
              <thead className="text-xs uppercase bg-slate-900 text-slate-400">
                <tr>
                  <th className="px-4 py-2">Method (Service-Aware Set)</th>
                  <th className="px-4 py-2">Test Rows</th>
                  <th className="px-4 py-2">Test MAE</th>
                  <th className="px-4 py-2">Test RMSE</th>
                  <th className="px-4 py-2">Test WAPE</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                <tr>
                  <td className="px-4 py-2">Last-Week Baseline (D-7)</td>
                  <td className="px-4 py-2">{coverage.model_evaluation?.matched_service?.baselines?.last_week_d7?.test?.rows}</td>
                  <td className="px-4 py-2">{coverage.model_evaluation?.matched_service?.baselines?.last_week_d7?.test?.mae}</td>
                  <td className="px-4 py-2">{coverage.model_evaluation?.matched_service?.baselines?.last_week_d7?.test?.rmse}</td>
                  <td className="px-4 py-2">{coverage.model_evaluation?.matched_service?.baselines?.last_week_d7?.test?.wape_pct}%</td>
                </tr>
                <tr>
                  <td className="px-4 py-2">Seasonal 4-Week Mean Baseline</td>
                  <td className="px-4 py-2">{coverage.model_evaluation?.matched_service?.baselines?.seasonal_4w_mean?.test?.rows}</td>
                  <td className="px-4 py-2">{coverage.model_evaluation?.matched_service?.baselines?.seasonal_4w_mean?.test?.mae}</td>
                  <td className="px-4 py-2">{coverage.model_evaluation?.matched_service?.baselines?.seasonal_4w_mean?.test?.rmse}</td>
                  <td className="px-4 py-2">{coverage.model_evaluation?.matched_service?.baselines?.seasonal_4w_mean?.test?.wape_pct}%</td>
                </tr>
                {coverage.model_evaluation?.matched_service?.models && Object.entries(coverage.model_evaluation.matched_service.models).map(([name, info]: [string, any]) => (
                  <tr key={name} className={name === coverage.model_evaluation.matched_service.selected_serving_model ? "bg-teal-950/30" : ""}>
                    <td className="px-4 py-2 font-semibold">{name} {name === coverage.model_evaluation.matched_service.selected_serving_model ? "(Selected)" : ""}</td>
                    <td className="px-4 py-2">{info.test?.rows}</td>
                    <td className="px-4 py-2">{info.test?.mae}</td>
                    <td className="px-4 py-2">{info.test?.rmse}</td>
                    <td className="px-4 py-2 text-teal-400 font-semibold">{info.test?.wape_pct}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Tab 9: Data Coverage */}
        {tab === "coverage" && coverage && (
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4">
            <h2 className="text-base font-semibold">Source Provenance & SHA-256 Registry</h2>
            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left bg-slate-950 border border-slate-800">
                <thead className="uppercase bg-slate-900 text-slate-400">
                  <tr>
                    <th className="px-3 py-2">Dataset ID</th>
                    <th className="px-3 py-2">Snapshot ID</th>
                    <th className="px-3 py-2">Retrieved</th>
                    <th className="px-3 py-2">Bytes</th>
                    <th className="px-3 py-2">SHA-256 Fingerprint</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800 font-mono">
                  {coverage.sources?.map((s: any, idx: number) => (
                    <tr key={idx}>
                      <td className="px-3 py-2">{s.dataset_id}</td>
                      <td className="px-3 py-2">{s.snapshot_id}</td>
                      <td className="px-3 py-2">{s.catalog_retrieved_date}</td>
                      <td className="px-3 py-2">{s.byte_size?.toLocaleString()}</td>
                      <td className="px-3 py-2 text-slate-400">{s.sha256}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </main>

      {/* Login Modal */}
      {showLoginModal && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-sm w-full p-6 space-y-5 shadow-2xl">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Shield className="text-teal-400" size={20} />
                <h3 className="text-base font-bold text-white">RouteRanker Portal</h3>
              </div>
              <button onClick={() => setShowLoginModal(false)} className="text-slate-400 hover:text-white text-lg">×</button>
            </div>

            <p className="text-xs text-slate-400">Sign in with Role-Based Access to manage schedules, view alerts, and broadcast emergency notices.</p>

            {loginError && (
              <div className="p-2 rounded bg-rose-950/50 border border-rose-800 text-rose-300 text-xs">
                {loginError}
              </div>
            )}

            <form onSubmit={handleLogin} className="space-y-3">
              <div>
                <label className="block text-xs text-slate-400 mb-1">Username</label>
                <input
                  type="text"
                  required
                  value={loginUsername}
                  onChange={(e) => setLoginUsername(e.target.value)}
                  placeholder="admin, operator, or viewer"
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-1">Password</label>
                <input
                  type="password"
                  required
                  value={loginPassword}
                  onChange={(e) => setLoginPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white"
                />
              </div>
              <button
                type="submit"
                className="w-full py-2 bg-teal-600 hover:bg-teal-500 rounded-lg text-sm font-semibold text-white transition mt-2"
              >
                Sign In
              </button>
            </form>

            <div className="pt-3 border-t border-slate-800 text-center">
              <div className="text-[11px] text-slate-500 mb-2">Quick Demo Sign-In:</div>
              <div className="flex gap-2">
                <button
                  onClick={() => handleQuickLogin("admin", "admin123")}
                  className="flex-1 py-1 rounded bg-slate-800 hover:bg-slate-700 text-[11px] text-purple-300 border border-purple-800/40"
                >
                  Admin
                </button>
                <button
                  onClick={() => handleQuickLogin("operator", "operator123")}
                  className="flex-1 py-1 rounded bg-slate-800 hover:bg-slate-700 text-[11px] text-teal-300 border border-teal-800/40"
                >
                  Operator
                </button>
                <button
                  onClick={() => handleQuickLogin("viewer", "viewer123")}
                  className="flex-1 py-1 rounded bg-slate-800 hover:bg-slate-700 text-[11px] text-slate-300 border border-slate-700"
                >
                  Viewer
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
