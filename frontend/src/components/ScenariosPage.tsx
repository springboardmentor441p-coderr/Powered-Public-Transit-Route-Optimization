import React, { useEffect, useState } from "react";
import {
  api,
  fmtInt,
  fmtNum,
  fmtPct,
  fmtSharePct,
  formatReviewCategory,
  formatTimeBandLabel,
  RouteSummary,
  ScenarioResponse,
} from "../api";
import { PageHeader } from "./PageHeader";

interface ScenariosPageProps {
  routes: RouteSummary[];
  initialRoute: string;
  initialDayGroup: string;
  initialTimeBand: string;
}

export const ScenariosPage: React.FC<ScenariosPageProps> = ({
  routes,
  initialRoute,
  initialDayGroup,
  initialTimeBand,
}) => {
  const [route, setRoute] = useState(initialRoute);
  const [dayGroup, setDayGroup] = useState(initialDayGroup);
  const [timeBand, setTimeBand] = useState(initialTimeBand);
  const [tripChangePct, setTripChangePct] = useState<number>(10);
  const [result, setResult] = useState<ScenarioResponse | null>(null);
  const [planRows, setPlanRows] = useState<Array<Record<string, unknown>>>([]);
  const [mergeChecks, setMergeChecks] = useState<Array<Record<string, unknown>>>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setRoute(initialRoute);
    setDayGroup(initialDayGroup);
    setTimeBand(initialTimeBand);
  }, [initialRoute, initialDayGroup, initialTimeBand]);

  useEffect(() => {
    api
      .getScenariosPlan()
      .then((res) => {
        setPlanRows(res.rows);
        const mc = (res.metadata?.merge_checks as Array<Record<string, unknown>>) ?? [];
        setMergeChecks(mc);
      })
      .catch(() => {
        // handled cleanly
      });
  }, []);

  const submitScenario = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const resp = await api.runScenario({
        route,
        day_group: dayGroup,
        time_band: timeBand,
        trip_change_pct: tripChangePct,
      });
      setResult(resp);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Scenario calculation failed");
      setResult(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void submitScenario();
  }, [route, dayGroup, timeBand]);

  const sc = result?.scenario;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Service Scenario Calculator & Budget-Neutral Reallocation"
        subtitle="Test arbitrary trip adjustments (+/- %) on any route × day-group × time-band cell using observed Aug–Oct 2026 hourly distributions, alongside Step 9 budget-neutral plans and shared-corridor checks."
        period={result?.period ?? "Aug–Oct 2026 Observed Typical Days (90 days: 63 weekday + 27 weekend)"}
        source={result?.source ?? "POST /api/scenarios -> src/recommend_adjustments.py"}
      />

      {/* Explicit Constant Ridership Assumption */}
      <div className="rounded-xl border border-blue-200 bg-blue-50 p-4 text-xs text-blue-950">
        <div className="font-bold uppercase tracking-wide text-blue-900">
          Core Model Assumption: {result?.assumption ?? "riders stay the same when trips change"}
        </div>
        <p className="mt-1">
          {result?.assumption_detail ??
            "Assumes total ridership stays constant when scheduled trips change (+/-10% or +/-20%), isolating arithmetic changes in riders per trip, riders per service-hour, and hours exceeding the fixed Jan–May p75 threshold."}
        </p>
      </div>

      {/* Calculator Form & Live Result */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-5">
        <form
          onSubmit={submitScenario}
          className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm lg:col-span-2 space-y-4"
        >
          <h2 className="text-sm font-semibold text-slate-900">Configure Scenario</h2>
          <div>
            <label htmlFor="sc-route" className="block text-xs font-medium text-slate-700">
              Route
            </label>
            <select
              id="sc-route"
              value={route}
              onChange={(e) => setRoute(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs text-slate-900"
            >
              {routes.map((r) => (
                <option key={r.route} value={r.route}>
                  {r.route} — {r.route_long_name}
                </option>
              ))}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label htmlFor="sc-dg" className="block text-xs font-medium text-slate-700">
                Day Group
              </label>
              <select
                id="sc-dg"
                value={dayGroup}
                onChange={(e) => setDayGroup(e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs text-slate-900"
              >
                <option value="weekday">Weekday (63d)</option>
                <option value="weekend">Weekend (27d)</option>
              </select>
            </div>
            <div>
              <label htmlFor="sc-tb" className="block text-xs font-medium text-slate-700">
                Time Band
              </label>
              <select
                id="sc-tb"
                value={timeBand}
                onChange={(e) => setTimeBand(e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs text-slate-900"
              >
                <option value="early_morning">Early Morning</option>
                <option value="morning_peak">Morning Peak</option>
                <option value="midday">Midday</option>
                <option value="evening_peak">Evening Peak</option>
                <option value="night">Night</option>
              </select>
            </div>
          </div>
          <div>
            <div className="flex items-center justify-between text-xs">
              <label htmlFor="sc-pct" className="font-medium text-slate-700">
                Trip Change (%)
              </label>
              <span className="font-mono font-bold text-slate-900">
                {tripChangePct > 0 ? `+${tripChangePct}%` : `${tripChangePct}%`}
              </span>
            </div>
            <input
              id="sc-pct"
              type="range"
              min={-40}
              max={60}
              step={5}
              value={tripChangePct}
              onChange={(e) => setTripChangePct(Number(e.target.value))}
              className="mt-2 w-full accent-blue-600"
            />
            <div className="mt-2 flex flex-wrap gap-1.5">
              {[-20, -10, 10, 20].map((v) => (
                <button
                  key={v}
                  type="button"
                  onClick={() => setTripChangePct(v)}
                  className={`rounded-md px-2.5 py-1 text-xs font-medium ${
                    tripChangePct === v
                      ? "bg-blue-600 text-white"
                      : "bg-slate-100 text-slate-700 hover:bg-slate-200"
                  }`}
                >
                  {v > 0 ? `+${v}%` : `${v}%`}
                </button>
              ))}
            </div>
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-lg bg-slate-900 px-4 py-2 text-xs font-semibold text-white hover:bg-slate-800 disabled:opacity-50"
          >
            {loading ? "Calculating..." : "Calculate Scenario"}
          </button>
          {error ? (
            <div className="rounded-lg border border-red-200 bg-red-50 p-2.5 text-xs text-red-700">
              {error}
            </div>
          ) : null}
        </form>

        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm lg:col-span-3">
          <h2 className="mb-3 text-sm font-semibold text-slate-900">
            Simulated Arithmetic Outcome
          </h2>
          {sc ? (
            <div className="space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-slate-50 p-3 text-xs">
                <div>
                  <span className="font-bold text-slate-900">{sc.route}</span> ·{" "}
                  {sc.day_group} · {formatTimeBandLabel(sc.time_band)} (
                  {formatReviewCategory(sc.review_category)})
                </div>
                <span
                  className={`rounded px-2 py-0.5 font-semibold ${
                    sc.guardrail_status === "ok"
                      ? "bg-emerald-100 text-emerald-800"
                      : "bg-rose-100 text-rose-800"
                  }`}
                >
                  Guardrail: {sc.guardrail_status}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                <div className="rounded-lg border border-slate-100 p-3">
                  <div className="text-[11px] text-slate-500">Scheduled Trips (Window)</div>
                  <div className="mt-1 font-mono text-sm font-bold text-slate-900">
                    {fmtInt(sc.base_trips)} -&gt; {fmtInt(sc.new_trips)}
                  </div>
                  <div className="text-[11px] text-slate-500">
                    Delta: {sc.delta_trips >= 0 ? `+${fmtInt(sc.delta_trips)}` : fmtInt(sc.delta_trips)} (
                    {fmtPct(sc.effective_trip_change_pct, 1)})
                  </div>
                </div>
                <div className="rounded-lg border border-slate-100 p-3">
                  <div className="text-[11px] text-slate-500">Service Hours (Window)</div>
                  <div className="mt-1 font-mono text-sm font-bold text-slate-900">
                    {fmtNum(sc.base_service_hours, 1)} -&gt; {fmtNum(sc.new_service_hours, 1)}
                  </div>
                  <div className="text-[11px] text-slate-500">
                    {sc.delta_service_hours >= 0 ? "+" : ""}
                    {fmtNum(sc.delta_service_hours, 1)} hrs ({fmtNum(sc.delta_service_hours_per_day, 2)}/day)
                  </div>
                </div>
                <div className="rounded-lg border border-slate-100 p-3">
                  <div className="text-[11px] text-slate-500">Riders per Trip (Const. Demand)</div>
                  <div className="mt-1 font-mono text-sm font-bold text-slate-900">
                    {fmtNum(sc.base_riders_per_trip, 2)} -&gt; {fmtNum(sc.new_riders_per_trip, 2)}
                  </div>
                  <div className="text-[11px] text-slate-500">
                    Constant riders: {fmtInt(sc.constant_obs_ridership)}
                  </div>
                </div>
                <div className="rounded-lg border border-slate-100 p-3">
                  <div className="text-[11px] text-slate-500">Riders per Service-Hour</div>
                  <div className="mt-1 font-mono text-sm font-bold text-slate-900">
                    {fmtNum(sc.base_riders_per_service_hour, 1)} -&gt;{" "}
                    {fmtNum(sc.new_riders_per_service_hour, 1)}
                  </div>
                  <div className="text-[11px] text-slate-500">
                    Exclusive stops: {fmtSharePct(sc.exclusive_stop_share)}
                  </div>
                </div>
                <div className="rounded-lg border border-slate-100 p-3">
                  <div className="text-[11px] text-slate-500">Hours &gt; p75 Threshold</div>
                  <div className="mt-1 font-mono text-sm font-bold text-slate-900">
                    {fmtInt(sc.base_high_demand_hours)} -&gt; {fmtInt(sc.sim_high_demand_hours)}
                  </div>
                  <div className="text-[11px] text-slate-500">
                    Delta: {sc.high_demand_hours_delta >= 0 ? `+${sc.high_demand_hours_delta}` : sc.high_demand_hours_delta} hrs
                  </div>
                </div>
                <div className="rounded-lg border border-slate-100 p-3">
                  <div className="text-[11px] text-slate-500">% of Day-Group Budget</div>
                  <div className="mt-1 font-mono text-sm font-bold text-slate-900">
                    {fmtNum(sc.pct_of_day_group_service_hours, 3)}%
                  </div>
                  <div className="text-[11px] text-slate-500">
                    Net window: {fmtNum(sc.pct_of_window_network_service_hours, 3)}%
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="text-xs text-slate-500">Select a cell and submit to inspect outcomes.</div>
          )}
        </div>
      </div>

      {/* Budget-Neutral Reallocation Plan (Step 9) */}
      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <h3 className="mb-1 text-sm font-semibold text-slate-900">
          Budget-Neutral Reallocation Plan ({planRows.length} cells across Weekday & Weekend)
        </h3>
        <p className="mb-3 text-xs text-slate-500">
          Transfers service hours within day groups (net change &lt;= 0.0 service-hours) from lower riders/svc-hr cells to candidates with frequent high riders/trip, respecting the 60% stop-exclusivity guardrail.
        </p>
        <div className="max-h-72 overflow-auto">
          <table className="w-full text-left text-xs">
            <thead className="sticky top-0 bg-slate-50 border-b border-slate-200 text-slate-600">
              <tr>
                <th className="py-2 pr-3 font-medium">Role</th>
                <th className="py-2 pr-3 font-medium">Day Group</th>
                <th className="py-2 pr-3 font-medium">Route · Band</th>
                <th className="py-2 pr-3 text-right font-medium">Trip Change</th>
                <th className="py-2 pr-3 text-right font-medium">Svc-Hr Delta</th>
                <th className="py-2 pr-3 text-right font-medium">High-Hr Delta</th>
                <th className="py-2 font-medium">Rationale</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {planRows.map((row, idx) => (
                <tr key={idx}>
                  <td className="py-2 pr-3">
                    <span
                      className={`rounded px-2 py-0.5 font-medium ${
                        String(row.reallocation_role).includes("receiver")
                          ? "bg-emerald-50 text-emerald-700"
                          : "bg-blue-50 text-blue-700"
                      }`}
                    >
                      {String(row.reallocation_role)}
                    </span>
                  </td>
                  <td className="py-2 pr-3 font-mono">{String(row.day_group)}</td>
                  <td className="py-2 pr-3 font-medium text-slate-900">
                    {String(row.route)} · {formatTimeBandLabel(String(row.time_band))}
                  </td>
                  <td className="py-2 pr-3 text-right font-mono">
                    {fmtInt(row.scenario_trip_change_pct as number)}%
                  </td>
                  <td className="py-2 pr-3 text-right font-mono">
                    {fmtNum(row.delta_service_hours as number, 1)}
                  </td>
                  <td className="py-2 pr-3 text-right font-mono">
                    {fmtInt(row.high_demand_hours_delta as number)}
                  </td>
                  <td className="py-2 text-slate-600">{String(row.rationale)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Shared-Corridor Merge Checks (Step 8) */}
      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <h3 className="mb-1 text-sm font-semibold text-slate-900">
          Shared-Corridor Overlap Checks ({mergeChecks.length} different-route pairs)
        </h3>
        <p className="mb-3 text-xs text-slate-500">
          Applies strictly to <code>shared_corridor</code> pairs (&gt;=40% overlap); explicitly excludes <code>same_family</code> local/Select Bus variants.
        </p>
        <div className="max-h-64 overflow-auto">
          <table className="w-full text-left text-xs">
            <thead className="sticky top-0 bg-slate-50 border-b border-slate-200 text-slate-600">
              <tr>
                <th className="py-2 pr-3 font-medium">Pair</th>
                <th className="py-2 pr-3 text-right font-medium">Overlap %</th>
                <th className="py-2 pr-3 text-right font-medium">Unshared Stops</th>
                <th className="py-2 pr-3 font-medium">Assessment Verdict</th>
                <th className="py-2 font-medium">Reason</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {mergeChecks.map((m, idx) => (
                <tr key={idx}>
                  <td className="py-2 pr-3 font-semibold text-slate-900">
                    {String(m.route_1)} / {String(m.route_2)}
                  </td>
                  <td className="py-2 pr-3 text-right font-mono">
                    {fmtNum(m.overlap_share_pct as number, 1)}%
                  </td>
                  <td className="py-2 pr-3 text-right font-mono">
                    {fmtInt(m.unshared_stops_on_smaller_route as number)}
                  </td>
                  <td className="py-2 pr-3 font-mono text-[11px] text-amber-800">
                    {String(m.merge_feasibility_verdict)}
                  </td>
                  <td className="py-2 text-slate-600">{String(m.verdict_reason)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

