import React, { useEffect, useMemo, useState } from "react";
import {
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  api,
  DayMetrics,
  DayScenarioResponse,
  fmtInt,
  fmtNum,
  NOT_AVAILABLE,
  OBS_END,
  OBS_START,
  REPLAY_END,
  REPLAY_START,
  RouteSummary,
  SavedScenario,
} from "../api";

interface DayScenarioPanelProps {
  routes: RouteSummary[];
  initialRoute: string;
  initialDate?: string;
  initialSource?: "observed" | "forecast";
}

const ROWS: Array<[keyof DayMetrics, string, (v: number | null) => string]> = [
  ["boardings", "Boardings", (v) => fmtInt(v)],
  ["scheduled_departures", "Scheduled departures (Oct 18–31 only)", (v) => fmtInt(v)],
  ["trips_running", "Trips running (summed by hour)", (v) => fmtNum(v, 1)],
  ["service_hours", "Scheduled service hours", (v) => fmtNum(v, 1)],
  ["riders_per_service_hour", "Boardings per service hour", (v) => fmtNum(v, 1)],
  ["riders_per_trip", "Boardings per trip running", (v) => fmtNum(v, 1)],
  ["hours_above_p75", "Hours above the high riders-per-trip line", (v) => fmtInt(v)],
  ["max_hour_riders_per_trip", "Busiest hour, boardings per trip", (v) => fmtNum(v, 1)],
];

export const DayScenarioPanel: React.FC<DayScenarioPanelProps> = ({
  routes,
  initialRoute,
  initialDate = "2026-10-20",
  initialSource = "observed",
}) => {
  const [route, setRoute] = useState(initialRoute);
  const [date, setDate] = useState(initialDate);
  const [source, setSource] = useState<"observed" | "forecast">(initialSource);
  const [tripPct, setTripPct] = useState(-10);
  const [multiplier, setMultiplier] = useState(1.0);
  const [cap, setCap] = useState(true);
  const [label, setLabel] = useState("");
  const [res, setRes] = useState<DayScenarioResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<SavedScenario[]>([]);
  const [savedMsg, setSavedMsg] = useState<string | null>(null);

  useEffect(() => setRoute(initialRoute), [initialRoute]);
  useEffect(() => setDate(initialDate), [initialDate]);
  useEffect(() => setSource(initialSource), [initialSource]);

  const refreshSaved = () =>
    api
      .getSavedScenarios()
      .then((r) => setSaved(r.rows))
      .catch(() => setSaved([]));
  useEffect(() => {
    refreshSaved();
  }, []);

  const run = (save: boolean) => {
    setError(null);
    api
      .runDayScenario({
        route,
        date,
        demand_source: source,
        trip_change_pct: tripPct,
        demand_multiplier: multiplier,
        apply_guardrail_cap: cap,
        save,
        label: label || undefined,
      })
      .then((r) => {
        setRes(r);
        if (save && r.scenario_id) {
          setSavedMsg(`Saved as ${r.scenario_id}`);
          refreshSaved();
        }
      })
      .catch((e) => {
        setRes(null);
        setError(e instanceof Error ? e.message : "Scenario failed.");
      });
  };

  useEffect(() => {
    setSavedMsg(null);
    const t = setTimeout(() => run(false), 250);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [route, date, source, tripPct, multiplier, cap]);

  const minDate = source === "forecast" ? REPLAY_START : OBS_START;
  const maxDate = source === "forecast" ? REPLAY_END : OBS_END;

  const hourly = useMemo(
    () =>
      (res?.hourly ?? []).map((h) => ({
        hour: `${String(h.hour).padStart(2, "0")}:00`,
        base: h.baseline_riders_per_trip,
        scen: h.scenario_riders_per_trip,
        line: h.threshold_p75,
      })),
    [res]
  );

  const fieldCls = "rounded-md border border-slate-300 bg-white px-2 py-1 text-xs text-slate-900";

  return (
    <section className="rounded-xl border border-amber-200 bg-white p-5 shadow-sm" data-testid="day-scenario-panel">
      <h2 className="text-base font-bold text-slate-900">Single-day scenario</h2>
      <p className="text-xs text-slate-600">
        Pick a route and a real day as the baseline, then change trips and, if you like, push demand up or down to test
        the result. Riders do not react to the trip change here.
      </p>

      <div className="mt-4 flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-0.5 text-[11px] font-semibold text-slate-500">
          Route
          <select aria-label="Scenario route" value={route} onChange={(e) => setRoute(e.target.value)} className={fieldCls}>
            {routes.map((r) => (
              <option key={r.route} value={r.route}>
                {r.route} · {r.route_long_name}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-0.5 text-[11px] font-semibold text-slate-500">
          Demand source
          <select
            aria-label="Demand source"
            value={source}
            onChange={(e) => {
              const v = e.target.value as "observed" | "forecast";
              setSource(v);
              if (v === "forecast" && (date < REPLAY_START || date > REPLAY_END)) setDate("2026-10-20");
            }}
            className={fieldCls}
          >
            <option value="observed">Published boardings (Aug–Oct)</option>
            <option value="forecast">Predicted boardings (Oct 18–31)</option>
          </select>
        </label>
        <label className="flex flex-col gap-0.5 text-[11px] font-semibold text-slate-500">
          Baseline date
          <input
            type="date"
            aria-label="Baseline date"
            min={minDate}
            max={maxDate}
            value={date}
            onChange={(e) => e.target.value && setDate(e.target.value)}
            className={fieldCls}
          />
        </label>
        <label className="flex flex-col gap-0.5 text-[11px] font-semibold text-slate-500">
          Trip change: {tripPct > 0 ? "+" : ""}
          {tripPct}%
          <input
            type="range"
            aria-label="Trip change percent"
            min={-50}
            max={50}
            step={5}
            value={tripPct}
            onChange={(e) => setTripPct(Number(e.target.value))}
            className="w-40"
          />
        </label>
        <label className="flex flex-col gap-0.5 text-[11px] font-semibold text-slate-500">
          Demand stress: ×{multiplier.toFixed(2)}
          <input
            type="range"
            aria-label="Demand multiplier"
            min={0.5}
            max={1.5}
            step={0.05}
            value={multiplier}
            onChange={(e) => setMultiplier(Number(e.target.value))}
            className="w-40"
          />
        </label>
        <label className="flex items-center gap-1.5 text-[11px] font-semibold text-slate-600">
          <input type="checkbox" checked={cap} onChange={(e) => setCap(e.target.checked)} />
          Apply -10% coverage cap
        </label>
      </div>

      {error ? <div className="mt-3 rounded-md bg-red-50 p-3 text-xs text-red-800">{error}</div> : null}

      {res ? (
        <div className="mt-4 grid gap-4 lg:grid-cols-5">
          <div className="lg:col-span-3">
            <div className="overflow-x-auto rounded-lg border border-slate-200">
              <table className="min-w-full text-left text-xs" data-testid="day-scenario-table">
                <thead className="bg-slate-50 text-[11px] uppercase text-slate-500">
                  <tr>
                    <th className="px-2 py-1.5">Measure</th>
                    <th className="px-2 py-1.5">Baseline</th>
                    <th className="px-2 py-1.5">Demand stress only</th>
                    <th className="px-2 py-1.5 text-amber-700">Scenario</th>
                    <th className="px-2 py-1.5">Change</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {ROWS.map(([k, lbl, f]) => (
                    <tr key={k}>
                      <td className="px-2 py-1.5 text-slate-600">{lbl}</td>
                      <td className="px-2 py-1.5">{f(res.result.baseline[k] as number | null)}</td>
                      <td className="px-2 py-1.5">{f(res.result.stress_only[k] as number | null)}</td>
                      <td className="px-2 py-1.5 font-semibold text-amber-800">{f(res.result.scenario[k] as number | null)}</td>
                      <td className="px-2 py-1.5 text-slate-600">{fmtChange(res.result.baseline[k] as number | null, res.result.scenario[k] as number | null, f)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mt-2 text-[11px] text-slate-500">
              Baseline: {res.demand_label} for {res.inputs.route} on {res.inputs.date} ({res.inputs.day_type}).{" "}
              {res.baseline_version.demand}.
            </p>
            {res.result.warnings.length ? (
              <ul className="mt-2 space-y-1 rounded-md bg-amber-50 p-2 text-[11px] text-amber-900">
                {res.result.warnings.map((w) => (
                  <li key={w}>• {w}</li>
                ))}
              </ul>
            ) : null}
            <div className="mt-3 h-52">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={hourly} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="hour" tick={{ fontSize: 10 }} interval={2} />
                  <YAxis tick={{ fontSize: 10 }} />
                  <Tooltip formatter={(v: number) => (v === null ? NOT_AVAILABLE : fmtNum(v, 1))} />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                  <Line name="Baseline boardings per trip" dataKey="base" stroke="#0f172a" strokeWidth={2} dot={false} />
                  <Line name="Scenario boardings per trip" dataKey="scen" stroke="#d97706" strokeWidth={2} dot={false} />
                  <Line name="High riders-per-trip line" dataKey="line" stroke="#94a3b8" strokeDasharray="5 4" dot={false} />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="space-y-3 text-xs lg:col-span-2">
            <div className="rounded-lg border border-slate-200 p-3">
              <div className="font-semibold text-slate-900">What changed</div>
              <ul className="mt-1 list-disc pl-4 text-slate-700">
                {res.changed_parameters.map((c) => (
                  <li key={c}>{c}</li>
                ))}
              </ul>
              <div className="mt-3 font-semibold text-slate-900">Scenario assumptions</div>
              <ul className="mt-1 list-disc pl-4 text-slate-600">
                {res.assumptions.map((a) => (
                  <li key={a}>{a}</li>
                ))}
              </ul>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <input
                aria-label="Scenario name"
                placeholder="Name (optional)"
                value={label}
                maxLength={80}
                onChange={(e) => setLabel(e.target.value)}
                className={`${fieldCls} flex-1`}
              />
              <button
                type="button"
                onClick={() => run(true)}
                className="rounded-lg bg-amber-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-amber-700"
              >
                Save scenario
              </button>
            </div>
            {savedMsg ? <p className="text-[11px] text-emerald-700">{savedMsg}</p> : null}
          </div>
        </div>
      ) : null}

      <div className="mt-5 border-t border-slate-100 pt-4">
        <h3 className="text-sm font-bold text-slate-900">Saved scenarios</h3>
        {saved.length === 0 ? (
          <p className="mt-1 text-xs text-slate-500">None saved yet.</p>
        ) : (
          <div className="mt-2 max-h-64 overflow-auto">
            <table className="min-w-full text-left text-xs" data-testid="saved-scenarios">
              <thead className="sticky top-0 bg-slate-50 text-[11px] uppercase text-slate-500">
                <tr>
                  <th className="px-2 py-1">Saved (UTC)</th>
                  <th className="px-2 py-1">Name</th>
                  <th className="px-2 py-1">Route · date</th>
                  <th className="px-2 py-1">Demand</th>
                  <th className="px-2 py-1">Trips</th>
                  <th className="px-2 py-1">Stress</th>
                  <th className="px-2 py-1">Boardings per trip</th>
                  <th className="px-2 py-1">Hours above line</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {saved.map((s) => (
                  <tr key={s.scenario_id}>
                    <td className="px-2 py-1 text-slate-500">{s.created_at.replace("T", " ").replace("+00:00", "")}</td>
                    <td className="px-2 py-1">{s.label ?? s.scenario_id}</td>
                    <td className="px-2 py-1 font-semibold">
                      {s.inputs.route} · {s.inputs.date}
                    </td>
                    <td className="px-2 py-1">{s.inputs.demand_source === "forecast" ? "Predicted" : "Published"}</td>
                    <td className="px-2 py-1">
                      {s.inputs.trip_change_pct_applied > 0 ? "+" : ""}
                      {s.inputs.trip_change_pct_applied}%
                    </td>
                    <td className="px-2 py-1">×{s.inputs.demand_multiplier.toFixed(2)}</td>
                    <td className="px-2 py-1">
                      {fmtNum(s.result.baseline.riders_per_trip, 1)} → {fmtNum(s.result.scenario.riders_per_trip, 1)}
                    </td>
                    <td className="px-2 py-1">
                      {s.result.baseline.hours_above_p75} → {s.result.scenario.hours_above_p75}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  );
};

function fmtChange(base: number | null, next: number | null, f: (v: number | null) => string): string {
  if (base === null || next === null || base === undefined || next === undefined) return NOT_AVAILABLE;
  const d = next - base;
  const sign = d > 0 ? "+" : "";
  const pct = base !== 0 ? ` (${sign}${((d / base) * 100).toFixed(1)}%)` : "";
  return `${sign}${f(d)}${pct}`;
}
