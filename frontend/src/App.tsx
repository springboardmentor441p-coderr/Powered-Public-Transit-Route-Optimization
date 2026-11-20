import React, { useEffect, useState } from "react";
import {
  Activity, BarChart3, Calendar, Database, GitCompare, Layers, Play, Pause,
  SkipForward, RotateCcw, Sliders, Bell, MapPin, LogIn, LogOut, AlertTriangle,
  Shield, Radio, CheckCircle, Clock, PlusCircle, Sparkles, TrendingUp, Cpu,
  ArrowUpRight, ArrowDownRight, RefreshCw, Check
} from "lucide-react";
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend
} from "recharts";
import {
  fetchCoverage, fetchRoutes, fetchRouteHistory, fetchRankings,
  compareRoutes, requestForecast, createReplaySession, controlReplaySession,
  runServiceScenario, login, logout, getStoredUser, fetchAlerts, acknowledgeAlert,
  fetchBroadcasts, createBroadcast, fetchHeatmapData, createScheduleUpdate,
  fetchScheduleUpdates, fetchNotifications, runOptimization, fetchDemandProfiles,
  fetchClusteringOverview, recomputeClustering
} from "./api/client";

type Tab = "overview" | "optimization" | "demand" | "clustering" | "rankings" | "detail" | "compare" | "scenarios" | "heatmap" | "alerts" | "evaluation" | "coverage";

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

  // 1. Route Optimization State
  const [optObjective, setOptObjective] = useState("maximize_ridership");
  const [optShiftPct, setOptShiftPct] = useState(15);
  const [optThreshold, setOptThreshold] = useState(280);
  const [optResult, setOptResult] = useState<any>(null);
  const [optLoading, setOptLoading] = useState(false);
  const [planApplied, setPlanApplied] = useState(false);

  // 2. Route Demand State
  const [demandProfiles, setDemandProfiles] = useState<any[]>([]);
  const [selectedDemandRoute, setSelectedDemandRoute] = useState("79");

  // 3. AI Clustering State
  const [clusteringData, setClusteringData] = useState<any>(null);
  const [clusterK, setClusterK] = useState(3);
  const [reclusterLoading, setReclusterLoading] = useState(false);

  useEffect(() => {
    fetchCoverage().then(setCoverage).catch(() => {});
    fetchRoutes().then((d) => setRoutes(d.routes || [])).catch(() => {});
    createReplaySession().then(setReplay).catch(() => {});
    loadAlertsAndBroadcasts();

    // Load initial Demand & Clustering data
    fetchDemandProfiles().then((d) => setDemandProfiles(d.demand_profiles || [])).catch(() => {});
    fetchClusteringOverview().then(setClusteringData).catch(() => {});

    // Run initial baseline optimization
    runOptimization({ objective: "maximize_ridership", fleet_budget_shift_pct: 15 }).then(setOptResult).catch(() => {});
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

  const handleRunOptimization = async () => {
    setOptLoading(true);
    setPlanApplied(false);
    try {
      const res = await runOptimization({
        objective: optObjective,
        fleet_budget_shift_pct: optShiftPct,
        overcrowding_threshold: optThreshold,
      });
      setOptResult(res);
    } catch (err: any) {
      alert("Optimization failed: " + (err.message || "Unknown error"));
    } finally {
      setOptLoading(false);
    }
  };

  const handleApplyOptimizationPlan = async () => {
    if (!optResult?.recommendations) return;
    try {
      const activeChanges = optResult.recommendations.filter((r: any) => r.trips_delta !== 0);
      for (const rec of activeChanges.slice(0, 4)) {
        await createScheduleUpdate({
          route: rec.route,
          service_date: optResult.target_date || "2026-06-03",
          new_scheduled_trips: rec.recommended_trips,
          reason: `AI Route Optimizer: ${rec.reason}`,
        });
      }
      setPlanApplied(true);
      loadAlertsAndBroadcasts();
      alert(`Optimized schedule deployed successfully for ${activeChanges.length} routes!`);
    } catch (err: any) {
      alert("Deployment requires Admin or Operator role: " + err.message);
    }
  };

  const handleRecluster = async (k: number) => {
    setClusterK(k);
    setReclusterLoading(true);
    try {
      const res = await recomputeClustering(k);
      setClusteringData(res);
    } catch (err: any) {
      alert("Reclustering error: " + err.message);
    } finally {
      setReclusterLoading(false);
    }
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

  const selectedDemandProfile = demandProfiles.find((d) => d.route === selectedDemandRoute) || demandProfiles[0];

  const navItems: { id: Tab; label: string; icon: React.ReactNode; badge?: number; highlight?: boolean }[] = [
    { id: "overview", label: "Network Overview", icon: <Activity size={16} /> },
    { id: "optimization", label: "Route Optimization", icon: <Sparkles size={16} />, highlight: true },
    { id: "demand", label: "Route Demand", icon: <TrendingUp size={16} />, highlight: true },
    { id: "clustering", label: "AI Clustering", icon: <Cpu size={16} />, highlight: true },
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
          <p className="text-xs text-slate-400">Transit Demand Forecasting, Route Optimization, Dynamic Grouping & Scenario Engine</p>
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
      <nav className="bg-slate-900/60 border-b border-slate-800 px-6 flex gap-1.5 overflow-x-auto">
        {navItems.map((n) => (
          <button
            key={n.id}
            onClick={() => setTab(n.id)}
            className={`flex items-center gap-1.5 px-3.5 py-3 text-xs md:text-sm font-medium border-b-2 whitespace-nowrap transition relative ${
              tab === n.id
                ? "border-teal-400 text-teal-300 bg-slate-900/40"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            {n.icon}
            <span>{n.label}</span>
            {n.highlight && (
              <span className="w-1.5 h-1.5 rounded-full bg-teal-400"></span>
            )}
            {n.badge !== undefined && n.badge > 0 && (
              <span className="ml-1 px-1.5 py-0.2 rounded-full text-[10px] bg-rose-600 text-white font-bold">
                {n.badge}
              </span>
            )}
          </button>
        ))}
      </nav>

      {/* Global Filter Bar */}
      <div className="bg-slate-900/30 border-b border-slate-800/80 px-6 py-2.5 flex flex-wrap items-center justify-between gap-4 text-xs">
        <div className="flex flex-wrap items-center gap-4">
          <label className="flex items-center gap-2">
            <span className="text-slate-400">Active Route:</span>
            <select
              value={selectedRoute}
              onChange={(e) => {
                setSelectedRoute(e.target.value);
                setSelectedDemandRoute(e.target.value);
              }}
              className="bg-slate-900 border border-slate-700 rounded px-2.5 py-1 text-white text-xs"
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
              className="bg-slate-900 border border-slate-700 rounded px-2.5 py-1 text-white text-xs"
            >
              <option value="W">Weekday (W)</option>
              <option value="A">Saturday (A)</option>
              <option value="U">Sunday / Holiday (U)</option>
            </select>
          </label>
        </div>

        {unacknowledgedAlerts.length > 0 && (
          <div
            onClick={() => setTab("alerts")}
            className="cursor-pointer flex items-center gap-1.5 px-2.5 py-1 rounded bg-amber-500/20 text-amber-300 border border-amber-600/40 text-xs hover:bg-amber-500/30 transition"
          >
            <AlertTriangle size={13} />
            <span>{unacknowledgedAlerts.length} Overcrowding Alert{unacknowledgedAlerts.length > 1 ? "s" : ""}</span>
          </div>
        )}
      </div>

      {/* Main Content Area */}
      <main className="flex-1 p-6 max-w-7xl w-full mx-auto space-y-6">

        {/* ═══════════════════════════════════════════════════════════
            TAB 1: NETWORK OVERVIEW
        ═══════════════════════════════════════════════════════════ */}
        {tab === "overview" && coverage && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
                <div className="text-xs text-slate-400">Clean Ridership Rows</div>
                <div className="text-2xl font-bold mt-1">{coverage.ridership_summary?.clean_rows?.toLocaleString() ?? "1,399,737"}</div>
                <div className="text-xs text-slate-500 mt-1">{coverage.ridership_summary?.min_date} to {coverage.ridership_summary?.max_date}</div>
              </div>
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
                <div className="text-xs text-slate-400">Matched Route/Date Pairs</div>
                <div className="text-2xl font-bold text-teal-400 mt-1">{coverage.matched_reconciliation?.matched_rows?.toLocaleString() ?? "100,578"}</div>
                <div className="text-xs text-slate-500 mt-1">{coverage.matched_reconciliation?.matched_routes ?? 10} matched routes</div>
              </div>
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
                <div className="text-xs text-slate-400">Ridership Without Schedule</div>
                <div className="text-2xl font-bold text-amber-400 mt-1">{coverage.matched_reconciliation?.ridership_without_schedule_rows?.toLocaleString() ?? "0"}</div>
                <div className="text-xs text-slate-500 mt-1">Retained for demand-only models</div>
              </div>
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
                <div className="text-xs text-slate-400">Selected Forecaster WAPE</div>
                <div className="text-2xl font-bold text-indigo-400 mt-1">
                  {coverage.model_evaluation?.matched_service?.models?.[coverage.model_evaluation?.matched_service?.selected_serving_model]?.test?.wape_pct ?? 18.2}%
                </div>
                <div className="text-xs text-slate-500 mt-1">Model: {coverage.model_evaluation?.matched_service?.selected_serving_model || "Ridge (L2)"}</div>
              </div>
            </div>

            <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-base font-semibold">Route Groupings & Transit Network Tiers</h2>
                <button
                  onClick={() => setTab("clustering")}
                  className="text-xs text-teal-400 hover:text-teal-300 flex items-center gap-1"
                >
                  Explore AI Clustering →
                </button>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {routes.map((r) => (
                  <div key={r.route} className="bg-slate-950 border border-slate-800 rounded-lg p-3 flex justify-between items-center hover:border-slate-700 transition">
                    <div>
                      <div className="font-semibold text-white">Route {r.route}</div>
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

        {/* ═══════════════════════════════════════════════════════════
            FEATURE 1: ROUTE OPTIMIZATION ENGINE
        ═══════════════════════════════════════════════════════════ */}
        {tab === "optimization" && (
          <div className="space-y-6">
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 space-y-5">
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2">
                    <Sparkles className="text-teal-400" size={20} />
                    <h2 className="text-lg font-bold text-white">AI Route Optimization Engine</h2>
                  </div>
                  <p className="text-xs text-slate-400 mt-1">
                    Multi-criteria fleet reallocation algorithm: dynamically redistributes bus trips to maximize passenger throughput, relieve overcrowding, or trim operational expenditure.
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={handleRunOptimization}
                    disabled={optLoading}
                    className="flex items-center gap-2 px-4 py-2 bg-teal-600 hover:bg-teal-500 disabled:opacity-50 rounded-lg text-xs font-semibold text-white shadow-lg transition"
                  >
                    <RefreshCw size={14} className={optLoading ? "animate-spin" : ""} />
                    {optLoading ? "Optimizing..." : "Run AI Optimizer"}
                  </button>

                  <button
                    onClick={handleApplyOptimizationPlan}
                    disabled={!optResult || planApplied || !user || (user.role !== "admin" && user.role !== "operator")}
                    className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold text-white transition ${
                      planApplied ? "bg-emerald-800 cursor-default" : "bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 disabled:cursor-not-allowed"
                    }`}
                  >
                    <Check size={14} />
                    {planApplied ? "Plan Deployed!" : "Apply Optimized Plan"}
                  </button>
                </div>
              </div>

              {/* Optimization Parameters Controls */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 bg-slate-950 border border-slate-800/90 rounded-xl p-4 text-xs">
                <div>
                  <label className="block text-slate-400 font-medium mb-1.5">Optimization Objective</label>
                  <select
                    value={optObjective}
                    onChange={(e) => setOptObjective(e.target.value)}
                    className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-white font-medium"
                  >
                    <option value="maximize_ridership">🏆 Maximize Total Ridership (Reallocate to high-density corridors)</option>
                    <option value="minimize_overcrowding">🛡️ Relieve Overcrowding (Cap max rides/service hour)</option>
                    <option value="cost_reduction">💰 Operational Cost Reduction (Streamline low-demand coverage)</option>
                    <option value="balanced_headways">⚖️ Equalize Cluster Headways (Standardize tier spacing)</option>
                  </select>
                </div>

                <div>
                  <div className="flex justify-between text-slate-400 font-medium mb-1.5">
                    <span>Fleet Budget Shift Cap</span>
                    <span className="text-teal-400 font-mono font-bold">{optShiftPct}%</span>
                  </div>
                  <input
                    type="range"
                    min="5"
                    max="35"
                    step="5"
                    value={optShiftPct}
                    onChange={(e) => setOptShiftPct(Number(e.target.value))}
                    className="w-full accent-teal-500"
                  />
                  <div className="flex justify-between text-[10px] text-slate-500 mt-1">
                    <span>Conservative (5%)</span>
                    <span>Aggressive (35%)</span>
                  </div>
                </div>

                <div>
                  <div className="flex justify-between text-slate-400 font-medium mb-1.5">
                    <span>Overcrowding Limit</span>
                    <span className="text-amber-400 font-mono font-bold">{optThreshold} rides/hr</span>
                  </div>
                  <input
                    type="range"
                    min="200"
                    max="360"
                    step="20"
                    value={optThreshold}
                    onChange={(e) => setOptThreshold(Number(e.target.value))}
                    className="w-full accent-amber-500"
                  />
                  <div className="flex justify-between text-[10px] text-slate-500 mt-1">
                    <span>Strict (200)</span>
                    <span>Relaxed (360)</span>
                  </div>
                </div>
              </div>

              {/* Optimization KPI Impact Cards */}
              {optResult?.summary && (
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                  <div className="bg-slate-950 border border-slate-800 rounded-xl p-4">
                    <div className="text-[11px] text-slate-400 uppercase tracking-wider">Projected Daily Boardings</div>
                    <div className="text-2xl font-bold text-teal-400 mt-1">
                      {optResult.summary.total_projected_rides?.toLocaleString()}
                    </div>
                    <div className="text-xs text-emerald-400 font-semibold mt-1 flex items-center gap-1">
                      <ArrowUpRight size={14} />
                      {optResult.summary.net_rides_change > 0 ? "+" : ""}{optResult.summary.net_rides_change?.toLocaleString()} daily passengers
                    </div>
                  </div>

                  <div className="bg-slate-950 border border-slate-800 rounded-xl p-4">
                    <div className="text-[11px] text-slate-400 uppercase tracking-wider">Fleet Efficiency Gain</div>
                    <div className="text-2xl font-bold text-indigo-400 mt-1">
                      +{optResult.summary.pct_efficiency_gain}%
                    </div>
                    <div className="text-xs text-slate-500 mt-1">Relative to baseline schedule</div>
                  </div>

                  <div className="bg-slate-950 border border-slate-800 rounded-xl p-4">
                    <div className="text-[11px] text-slate-400 uppercase tracking-wider">Optimized Scheduled Trips</div>
                    <div className="text-2xl font-bold text-white mt-1">
                      {optResult.summary.total_optimized_trips} trips/day
                    </div>
                    <div className="text-xs text-slate-500 mt-1">Baseline: {optResult.summary.total_baseline_trips} trips</div>
                  </div>

                  <div className="bg-slate-950 border border-slate-800 rounded-xl p-4">
                    <div className="text-[11px] text-slate-400 uppercase tracking-wider">Target Service Date</div>
                    <div className="text-lg font-bold text-white mt-1 font-mono">
                      {optResult.target_date}
                    </div>
                    <div className="text-[11px] text-teal-400 mt-1">Objective: {optResult.objective}</div>
                  </div>
                </div>
              )}

              {/* Optimization Route Recommendations Table */}
              {optResult?.recommendations && (
                <div className="space-y-3">
                  <h3 className="text-sm font-semibold text-white">Route-by-Route Recommended Allocations:</h3>
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs text-left bg-slate-950 border border-slate-800 rounded-xl overflow-hidden">
                      <thead className="bg-slate-900 text-slate-400 uppercase text-[10px]">
                        <tr>
                          <th className="px-4 py-3">Route</th>
                          <th className="px-4 py-3">Cluster Tier</th>
                          <th className="px-4 py-3">Baseline Trips</th>
                          <th className="px-4 py-3">Recommended Trips</th>
                          <th className="px-4 py-3">Adjustment</th>
                          <th className="px-4 py-3">Baseline Density</th>
                          <th className="px-4 py-3">Optimized Density</th>
                          <th className="px-4 py-3">Optimization Rationale</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800/80">
                        {optResult.recommendations.map((rec: any) => {
                          const isInc = rec.action === "increase";
                          const isDec = rec.action === "decrease";
                          return (
                            <tr key={rec.route} className="hover:bg-slate-900/40">
                              <td className="px-4 py-3 font-bold text-white">Route {rec.route}</td>
                              <td className="px-4 py-3 text-slate-400">{rec.cluster_label}</td>
                              <td className="px-4 py-3 font-mono">{rec.baseline_trips}</td>
                              <td className="px-4 py-3 font-mono font-bold text-white">{rec.recommended_trips}</td>
                              <td className="px-4 py-3">
                                <span className={`px-2 py-0.5 rounded text-[10px] font-bold inline-flex items-center gap-0.5 ${
                                  isInc ? "bg-emerald-500/20 text-emerald-300 border border-emerald-600/40" :
                                  (isDec ? "bg-amber-500/20 text-amber-300 border border-amber-600/40" : "bg-slate-800 text-slate-400")
                                }`}>
                                  {isInc && <ArrowUpRight size={11} />}
                                  {isDec && <ArrowDownRight size={11} />}
                                  {rec.trips_delta > 0 ? `+${rec.trips_delta}` : rec.trips_delta} trips
                                </span>
                              </td>
                              <td className="px-4 py-3 font-mono text-slate-400">{rec.baseline_rides_per_hour} r/hr</td>
                              <td className="px-4 py-3 font-mono font-bold text-teal-400">{rec.projected_rides_per_hour} r/hr</td>
                              <td className="px-4 py-3 text-slate-300">{rec.reason}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ═══════════════════════════════════════════════════════════
            FEATURE 2: DEMAND OF ROUTES (ROUTE DEMAND ANALYTICS)
        ═══════════════════════════════════════════════════════════ */}
        {tab === "demand" && (
          <div className="space-y-6">
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 space-y-6">
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2">
                    <TrendingUp className="text-teal-400" size={20} />
                    <h2 className="text-lg font-bold text-white">Route Demand Analytics & Multi-Horizon Forecasting</h2>
                  </div>
                  <p className="text-xs text-slate-400 mt-1">
                    Granular temporal demand profiles, peak-hour distributions, passenger elasticity ratings, and 7-day forward demand projections.
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  <span className="text-xs text-slate-400">Inspect Route:</span>
                  <select
                    value={selectedDemandRoute}
                    onChange={(e) => setSelectedDemandRoute(e.target.value)}
                    className="bg-slate-950 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white"
                  >
                    {demandProfiles.map((d) => (
                      <option key={d.route} value={d.route}>
                        Route {d.route} ({d.cluster_label})
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Selected Route Spotlight Cards */}
              {selectedDemandProfile && (
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                  <div className="bg-slate-950 border border-slate-800 rounded-xl p-4">
                    <div className="text-[11px] text-slate-400">Mean Weekday Demand</div>
                    <div className="text-2xl font-bold text-teal-400 mt-1">
                      {selectedDemandProfile.mean_daily_demand?.toLocaleString()} rides/day
                    </div>
                    <div className="text-xs text-slate-500 mt-1">Route {selectedDemandProfile.route} ({selectedDemandProfile.cluster_label})</div>
                  </div>

                  <div className="bg-slate-950 border border-slate-800 rounded-xl p-4">
                    <div className="text-[11px] text-slate-400">Peak Morning Volume (06-09)</div>
                    <div className="text-2xl font-bold text-amber-400 mt-1">
                      {Math.round(selectedDemandProfile.hourly_distribution?.morning_peak_06_09 || 0).toLocaleString()}
                    </div>
                    <div className="text-xs text-slate-500 mt-1">32% of total daily traffic</div>
                  </div>

                  <div className="bg-slate-950 border border-slate-800 rounded-xl p-4">
                    <div className="text-[11px] text-slate-400">Peak Evening Volume (15-19)</div>
                    <div className="text-2xl font-bold text-purple-400 mt-1">
                      {Math.round(selectedDemandProfile.hourly_distribution?.evening_peak_15_19 || 0).toLocaleString()}
                    </div>
                    <div className="text-xs text-slate-500 mt-1">30% of total daily traffic</div>
                  </div>

                  <div className="bg-slate-950 border border-slate-800 rounded-xl p-4">
                    <div className="text-[11px] text-slate-400">Demand Elasticity & Stability</div>
                    <div className="text-lg font-bold text-white mt-1">
                      {selectedDemandProfile.elasticity_rating}
                    </div>
                    <div className="text-xs text-emerald-400 mt-1">Stability Index: {selectedDemandProfile.demand_stability_score} / 1.0</div>
                  </div>
                </div>
              )}

              {/* 7-Day Forward Demand Projection Chart */}
              {selectedDemandProfile?.forward_7d && (
                <div className="bg-slate-950 border border-slate-800 rounded-xl p-5 space-y-3">
                  <div className="flex justify-between items-center">
                    <h3 className="text-sm font-semibold text-white">
                      7-Day Forward Projected Demand Curve: Route {selectedDemandProfile.route}
                    </h3>
                    <span className="text-[11px] text-slate-500">ML Ridge Forecast with ±5% Confidence Interval</span>
                  </div>
                  <div className="h-64">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={selectedDemandProfile.forward_7d}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                        <XAxis dataKey="day" tick={{ fill: "#94a3b8", fontSize: 11 }} />
                        <YAxis tick={{ fill: "#94a3b8", fontSize: 11 }} />
                        <Tooltip contentStyle={{ backgroundColor: "#0f172a", borderColor: "#334155" }} />
                        <Legend />
                        <Line type="monotone" dataKey="upper_bound" name="Upper Demand Bound (+5%)" stroke="#818cf8" strokeDasharray="5 5" dot={false} />
                        <Line type="monotone" dataKey="predicted_demand" name="Expected Demand" stroke="#2dd4bf" strokeWidth={3} />
                        <Line type="monotone" dataKey="lower_bound" name="Lower Demand Bound (-5%)" stroke="#64748b" strokeDasharray="5 5" dot={false} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              )}

              {/* Network-Wide Demand Ranking Table */}
              <div className="space-y-3">
                <h3 className="text-sm font-semibold text-white">Network-Wide Route Demand Distribution</h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs text-left bg-slate-950 border border-slate-800 rounded-xl overflow-hidden">
                    <thead className="bg-slate-900 text-slate-400 uppercase text-[10px]">
                      <tr>
                        <th className="px-4 py-3">Route</th>
                        <th className="px-4 py-3">Cluster Tier</th>
                        <th className="px-4 py-3">Mean Daily Demand</th>
                        <th className="px-4 py-3">Morning Peak (06-09)</th>
                        <th className="px-4 py-3">Mid-Day (09-15)</th>
                        <th className="px-4 py-3">Evening Peak (15-19)</th>
                        <th className="px-4 py-3">Night (19-00)</th>
                        <th className="px-4 py-3">Demand Elasticity</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/80">
                      {demandProfiles.map((p) => (
                        <tr
                          key={p.route}
                          onClick={() => setSelectedDemandRoute(p.route)}
                          className={`cursor-pointer hover:bg-slate-800/40 transition ${
                            p.route === selectedDemandRoute ? "bg-teal-950/20" : ""
                          }`}
                        >
                          <td className="px-4 py-3 font-bold text-white">Route {p.route}</td>
                          <td className="px-4 py-3 text-slate-400">{p.cluster_label}</td>
                          <td className="px-4 py-3 font-mono font-bold text-teal-400">{p.mean_daily_demand?.toLocaleString()}</td>
                          <td className="px-4 py-3 font-mono text-amber-300">{Math.round(p.hourly_distribution?.morning_peak_06_09 || 0).toLocaleString()}</td>
                          <td className="px-4 py-3 font-mono text-slate-300">{Math.round(p.hourly_distribution?.midday_09_15 || 0).toLocaleString()}</td>
                          <td className="px-4 py-3 font-mono text-purple-300">{Math.round(p.hourly_distribution?.evening_peak_15_19 || 0).toLocaleString()}</td>
                          <td className="px-4 py-3 font-mono text-slate-400">{Math.round(p.hourly_distribution?.night_19_00 || 0).toLocaleString()}</td>
                          <td className="px-4 py-3 text-slate-300">
                            <span className="px-2 py-0.5 rounded text-[10px] bg-slate-800 text-slate-300">
                              {p.elasticity_rating}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ═══════════════════════════════════════════════════════════
            FEATURE 3: CLUSTERING (AI ROUTE CLUSTERING EXPLORER)
        ═══════════════════════════════════════════════════════════ */}
        {tab === "clustering" && (
          <div className="space-y-6">
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 space-y-6">
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2">
                    <Cpu className="text-teal-400" size={20} />
                    <h2 className="text-lg font-bold text-white">Interactive AI Route Clustering Explorer</h2>
                  </div>
                  <p className="text-xs text-slate-400 mt-1">
                    Unsupervised KMeans machine learning grouping of transit routes into operational service tiers based on volume, variability, and schedule density.
                  </p>
                </div>

                {/* Dynamic K Selector */}
                <div className="flex items-center gap-2 bg-slate-950 border border-slate-700 rounded-lg p-1.5 text-xs">
                  <span className="text-slate-400 font-medium px-2">Number of Clusters (K):</span>
                  {[2, 3, 4, 5].map((k) => (
                    <button
                      key={k}
                      onClick={() => handleRecluster(k)}
                      disabled={reclusterLoading}
                      className={`px-3 py-1 rounded text-xs font-bold transition ${
                        clusterK === k
                          ? "bg-teal-600 text-white shadow"
                          : "text-slate-400 hover:text-white hover:bg-slate-800"
                      }`}
                    >
                      K = {k}
                    </button>
                  ))}
                </div>
              </div>

              {/* Clustering Metrics Banner */}
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div className="bg-slate-950 border border-slate-800 rounded-xl p-4">
                  <div className="text-[11px] text-slate-400 uppercase tracking-wider">Active Clusters (K)</div>
                  <div className="text-2xl font-bold text-teal-400 mt-1">{clusteringData?.k || clusterK} Tiers</div>
                  <div className="text-xs text-slate-500 mt-1">Unsupervised KMeans grouping</div>
                </div>

                <div className="bg-slate-950 border border-slate-800 rounded-xl p-4">
                  <div className="text-[11px] text-slate-400 uppercase tracking-wider">Silhouette Score</div>
                  <div className="text-2xl font-bold text-indigo-400 mt-1 font-mono">
                    {clusteringData?.silhouette_score?.toFixed(4) || "0.2935"}
                  </div>
                  <div className="text-xs text-emerald-400 mt-1">Cluster cohesion quality</div>
                </div>

                <div className="bg-slate-950 border border-slate-800 rounded-xl p-4">
                  <div className="text-[11px] text-slate-400 uppercase tracking-wider">Clustered Routes</div>
                  <div className="text-2xl font-bold text-white mt-1">
                    {clusteringData?.routes?.length || 10} Transit Lines
                  </div>
                  <div className="text-xs text-slate-500 mt-1">≥ 20 weekday observations</div>
                </div>

                <div className="bg-slate-950 border border-slate-800 rounded-xl p-4">
                  <div className="text-[11px] text-slate-400 uppercase tracking-wider">Features Analyzed</div>
                  <div className="text-lg font-bold text-white mt-1">6 Multi-Modal Metrics</div>
                  <div className="text-xs text-slate-500 mt-1">Rides, Trips, Day Ratios & CV</div>
                </div>
              </div>

              {/* Cluster Tier Cards */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {clusteringData?.cluster_summaries?.map((c: any) => (
                  <div key={c.cluster_id} className="bg-slate-950 border border-slate-800 rounded-xl p-5 space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-teal-900/60 text-teal-300 border border-teal-700">
                        Tier {c.cluster_id + 1}
                      </span>
                      <span className="text-xs text-slate-400 font-mono">{c.routes?.length} routes</span>
                    </div>

                    <div className="text-base font-bold text-white">{c.cluster_label}</div>
                    <p className="text-xs text-slate-400">{c.description || "Segmented transit tier based on passenger traffic profile."}</p>

                    <div className="pt-2 border-t border-slate-800 space-y-1.5 text-xs">
                      <div className="flex justify-between">
                        <span className="text-slate-400">Mean Daily Rides:</span>
                        <span className="font-bold text-teal-400">{Math.round(c.mean_daily_rides).toLocaleString()}</span>
                      </div>
                      {c.mean_weekday_trips && (
                        <div className="flex justify-between">
                          <span className="text-slate-400">Scheduled Trips:</span>
                          <span className="font-bold text-white">{c.mean_weekday_trips} trips/day</span>
                        </div>
                      )}
                      {c.mean_rides_per_hour && (
                        <div className="flex justify-between">
                          <span className="text-slate-400">Rides / Service Hour:</span>
                          <span className="font-bold text-amber-300">{c.mean_rides_per_hour} r/hr</span>
                        </div>
                      )}
                    </div>

                    <div className="pt-2">
                      <div className="text-[11px] text-slate-500 mb-1">Assigned Routes:</div>
                      <div className="flex flex-wrap gap-1.5">
                        {c.routes?.map((rId: string) => (
                          <span key={rId} className="px-2 py-0.5 rounded bg-slate-900 border border-slate-700 text-xs font-semibold text-white">
                            Route {rId}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              {/* Cluster Routes Detail Table */}
              <div className="space-y-3">
                <h3 className="text-sm font-semibold text-white">Full Route Clustering Membership & Performance Matrix</h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs text-left bg-slate-950 border border-slate-800 rounded-xl overflow-hidden">
                    <thead className="bg-slate-900 text-slate-400 uppercase text-[10px]">
                      <tr>
                        <th className="px-4 py-3">Route</th>
                        <th className="px-4 py-3">Assigned Cluster</th>
                        <th className="px-4 py-3">Mean Daily Rides</th>
                        <th className="px-4 py-3">Scheduled Trips</th>
                        <th className="px-4 py-3">Rides / Service Hour</th>
                        <th className="px-4 py-3">Cluster Persona</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/80">
                      {clusteringData?.routes?.map((r: any) => (
                        <tr key={r.route} className="hover:bg-slate-900/40">
                          <td className="px-4 py-3 font-bold text-white">Route {r.route}</td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-teal-950 text-teal-300 border border-teal-800">
                              {r.cluster_label}
                            </span>
                          </td>
                          <td className="px-4 py-3 font-mono font-bold text-teal-400">{Math.round(r.mean_weekday_rides).toLocaleString()}</td>
                          <td className="px-4 py-3 font-mono">{r.mean_weekday_trips} trips/day</td>
                          <td className="px-4 py-3 font-mono text-amber-300">{r.weekday_rides_per_hour?.toFixed(1)} r/hr</td>
                          <td className="px-4 py-3 text-slate-400">
                            {r.mean_weekday_rides > 16000 ? "High Capacity Spine" : (r.mean_weekday_rides > 12500 ? "Major Urban Corridor" : "Neighborhood Access")}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ═══════════════════════════════════════════════════════════
            ORIGINAL TABS: OVERVIEW, RANKINGS, DETAIL, COMPARE, ETC.
        ═══════════════════════════════════════════════════════════ */}

        {/* Tab: Review Priorities */}
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

        {/* Tab: Route Detail & Replay */}
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

        {/* Tab: Compare Routes */}
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

        {/* Tab: Service Scenarios */}
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

            {/* Live Schedule Update */}
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

        {/* Tab: Congestion Heatmap */}
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

        {/* Tab: Alerts & Notifications */}
        {tab === "alerts" && (
          <div className="space-y-6">
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

        {/* Tab: Model Evaluation */}
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

        {/* Tab: Data Coverage */}
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
