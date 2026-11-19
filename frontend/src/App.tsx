import React, { useEffect, useState } from "react";
import {
  Activity, BarChart3, Calendar, Database, GitCompare, Layers, Play, Pause, SkipForward, RotateCcw, Sliders
} from "lucide-react";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend
} from "recharts";
import {
  fetchCoverage, fetchRoutes, fetchRouteHistory, fetchRankings,
  compareRoutes, requestForecast, createReplaySession, controlReplaySession, runServiceScenario
} from "./api/client";

type Tab = "overview" | "rankings" | "detail" | "compare" | "scenarios" | "evaluation" | "coverage";

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

  useEffect(() => {
    fetchCoverage().then(setCoverage);
    fetchRoutes().then((d) => setRoutes(d.routes || []));
    createReplaySession().then(setReplay);
  }, []);

  useEffect(() => {
    fetchRankings(daytype).then((d) => setRankings(d.rankings || []));
  }, [daytype]);

  useEffect(() => {
    if (!replay) return;
    const vDate = new Date(replay.current_virtual_date);
    vDate.setDate(vDate.getDate() - 1);
    const cutoff = vDate.toISOString().slice(0, 10);

    fetchRouteHistory(selectedRoute, cutoff).then(setHistoryData);
    requestForecast(selectedRoute, replay.current_virtual_date, replay.current_virtual_date).then(setForecast);
  }, [selectedRoute, replay]);

  useEffect(() => {
    compareRoutes(selectedRoute, compareRouteB, daytype).then(setComparison);
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

  const navItems: { id: Tab; label: string; icon: React.ReactNode }[] = [
    { id: "overview", label: "Network Overview", icon: <Activity size={16} /> },
    { id: "rankings", label: "Review Priorities", icon: <BarChart3 size={16} /> },
    { id: "detail", label: "Route Detail & Replay", icon: <Calendar size={16} /> },
    { id: "compare", label: "Compare Routes", icon: <GitCompare size={16} /> },
    { id: "scenarios", label: "Service Scenarios", icon: <Sliders size={16} /> },
    { id: "evaluation", label: "Model Evaluation", icon: <Layers size={16} /> },
    { id: "coverage", label: "Data & Coverage", icon: <Database size={16} /> },
  ];

  return (
    <div className="min-h-screen flex flex-col">
      <header className="bg-slate-900 border-b border-slate-800 px-6 py-4 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-teal-400">RouteRanker</h1>
          <p className="text-xs text-slate-400">Transit Demand Forecasting, Route Grouping & Conditional Scenario Engine</p>
        </div>

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
      </header>

      <nav className="bg-slate-900/60 border-b border-slate-800 px-6 flex gap-2 overflow-x-auto">
        {navItems.map((n) => (
          <button
            key={n.id}
            onClick={() => setTab(n.id)}
            className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition ${
              tab === n.id ? "border-teal-400 text-teal-300" : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            {n.icon}
            {n.label}
          </button>
        ))}
      </nav>

      <div className="bg-slate-900/30 border-b border-slate-800/80 px-6 py-3 flex flex-wrap items-center gap-4 text-sm">
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

      <main className="flex-1 p-6 max-w-7xl w-full mx-auto space-y-6">
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
                  {coverage.model_evaluation.matched_service.models[coverage.model_evaluation.matched_service.selected_serving_model].test.wape_pct}%
                </div>
                <div className="text-xs text-slate-500 mt-1">Model: {coverage.model_evaluation.matched_service.selected_serving_model}</div>
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
                    <LineChart data={historyData.history.slice(-60)}>
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

        {tab === "scenarios" && (
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
                  className="bg-slate-950 border border-slate-700 rounded px-3 py-1.5 text-sm w-44"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-1">Assumed Demand Multiplier (1.0 = fixed)</label>
                <input
                  type="number"
                  step="0.05"
                  value={demandMult}
                  onChange={(e) => setDemandMult(Number(e.target.value))}
                  className="bg-slate-950 border border-slate-700 rounded px-3 py-1.5 text-sm w-44"
                />
              </div>
              <button onClick={handleRunScenario} className="px-4 py-1.5 bg-teal-600 hover:bg-teal-500 rounded text-sm font-medium text-white">
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
                  <strong>Assumptions & Interpretation Limits:</strong> Mean trip duration = {scenarioOut.assumptions.assumed_mean_duration_minutes} mins. {scenarioOut.assumptions.note}
                </div>
              </div>
            )}
          </div>
        )}

        {tab === "evaluation" && coverage && (
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4">
            <h2 className="text-base font-semibold">Chronological Model Evaluation vs. Seasonal Baselines</h2>
            <p className="text-xs text-slate-400">Policy: {coverage.model_evaluation.missing_history_policy}</p>
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
                  <td className="px-4 py-2">{coverage.model_evaluation.matched_service.baselines.last_week_d7.test.rows}</td>
                  <td className="px-4 py-2">{coverage.model_evaluation.matched_service.baselines.last_week_d7.test.mae}</td>
                  <td className="px-4 py-2">{coverage.model_evaluation.matched_service.baselines.last_week_d7.test.rmse}</td>
                  <td className="px-4 py-2">{coverage.model_evaluation.matched_service.baselines.last_week_d7.test.wape_pct}%</td>
                </tr>
                <tr>
                  <td className="px-4 py-2">Seasonal 4-Week Mean Baseline</td>
                  <td className="px-4 py-2">{coverage.model_evaluation.matched_service.baselines.seasonal_4w_mean.test.rows}</td>
                  <td className="px-4 py-2">{coverage.model_evaluation.matched_service.baselines.seasonal_4w_mean.test.mae}</td>
                  <td className="px-4 py-2">{coverage.model_evaluation.matched_service.baselines.seasonal_4w_mean.test.rmse}</td>
                  <td className="px-4 py-2">{coverage.model_evaluation.matched_service.baselines.seasonal_4w_mean.test.wape_pct}%</td>
                </tr>
                {Object.entries(coverage.model_evaluation.matched_service.models).map(([name, info]: [string, any]) => (
                  <tr key={name} className={name === coverage.model_evaluation.matched_service.selected_serving_model ? "bg-teal-950/30" : ""}>
                    <td className="px-4 py-2 font-semibold">{name} {name === coverage.model_evaluation.matched_service.selected_serving_model ? "(Selected)" : ""}</td>
                    <td className="px-4 py-2">{info.test.rows}</td>
                    <td className="px-4 py-2">{info.test.mae}</td>
                    <td className="px-4 py-2">{info.test.rmse}</td>
                    <td className="px-4 py-2 text-teal-400 font-semibold">{info.test.wape_pct}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

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
                  {coverage.sources.map((s: any, idx: number) => (
                    <tr key={idx}>
                      <td className="px-3 py-2">{s.dataset_id}</td>
                      <td className="px-3 py-2">{s.snapshot_id}</td>
                      <td className="px-3 py-2">{s.catalog_retrieved_date}</td>
                      <td className="px-3 py-2">{s.byte_size.toLocaleString()}</td>
                      <td className="px-3 py-2 text-slate-400">{s.sha256}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
