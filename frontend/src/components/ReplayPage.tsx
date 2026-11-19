import React, { useEffect, useMemo, useState } from "react";
import {
  Bar,
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
  fmtInt,
  fmtNum,
  fmtPct,
  NOT_AVAILABLE,
  REPLAY_END,
  REPLAY_START,
  ReplayForecastRecord,
  ReplayScores,
  ReplayState,
} from "../api";
import { PageHeader } from "./PageHeader";

const C_ACTUAL = "#0f172a";
const C_PRED = "#2563eb";
const C_BASE = "#94a3b8";

interface ReplayPageProps {
  state: ReplayState | null;
  busy: boolean;
  error: string | null;
  route: string;
  onControl: (body: { action: string; speed_seconds?: number; start_date?: string; delay_days?: number }) => void;
  onCompare: () => void;
  onScenario: (date: string) => void;
}

const statusText: Record<string, string> = {
  normal: "Normal",
  normal_fewer_lags: "Normal, fewer past weeks available",
  unavailable_no_scheduled_trips: "Not available (no scheduled trips)",
};

const ScoreCard: React.FC<{ title: string; scores: ReplayScores }> = ({ title, scores }) => (
  <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
    <div className="text-xs font-semibold text-slate-500">{title}</div>
    {scores.revealed_days === 0 ? (
      <p className="mt-2 text-sm text-slate-600">
        No days revealed yet. Scores appear once recorded boardings for a forecast day are allowed.
      </p>
    ) : (
      <div className="mt-2 grid grid-cols-2 gap-3">
        <div>
          <div className="text-2xl font-bold text-blue-700">{fmtPct(scores.model_wape_pct, 2)}</div>
          <div className="text-[11px] text-slate-500">Model error (WAPE)</div>
        </div>
        <div>
          <div className="text-2xl font-bold text-slate-500">{fmtPct(scores.baseline_wape_pct, 2)}</div>
          <div className="text-[11px] text-slate-500">4-week average error (WAPE)</div>
        </div>
        <div className="col-span-2 text-[11px] text-slate-500">
          {scores.revealed_days} revealed day(s), {fmtInt(scores.scored_hours)} route-hours scored. Lower is better.
        </div>
      </div>
    )}
  </div>
);

export const ReplayPage: React.FC<ReplayPageProps> = ({ state, busy, error, route, onControl, onCompare, onScenario }) => {
  const [startDate, setStartDate] = useState(REPLAY_START);
  const [delay, setDelay] = useState(1);
  const [records, setRecords] = useState<ReplayForecastRecord[]>([]);

  useEffect(() => {
    if (state) {
      setStartDate(state.session.start_date);
      setDelay(state.session.delay_days);
    }
    // only when the session changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state?.session.session_id]);

  const sid = state?.session.session_id;
  const vdate = state?.virtual_date;
  useEffect(() => {
    if (!sid || !vdate) return;
    let cancelled = false;
    api
      .getReplayForecasts(sid, route, vdate)
      .then((r) => !cancelled && setRecords(r.rows))
      .catch(() => !cancelled && setRecords([]));
    return () => {
      cancelled = true;
    };
  }, [sid, vdate, route]);

  const networkSeries = useMemo(
    () =>
      (state?.network_daily ?? []).map((d) => ({
        date: d.date.slice(5),
        forecast: d.forecast_boardings,
        baseline: d.baseline_boardings,
        actual: d.actual_boardings,
      })),
    [state]
  );

  const rd = state?.route_detail;
  const routeSeries = useMemo(
    () =>
      (rd?.daily ?? []).map((d) => ({
        date: d.date.slice(5),
        forecast: d.forecast_boardings,
        baseline: d.baseline_boardings,
        actual: d.actual_boardings,
      })),
    [rd]
  );
  const todayHourly = useMemo(
    () =>
      (rd?.current_day_hourly ?? []).map((h) => ({
        hour: `${String(h.hour).padStart(2, "0")}:00`,
        predicted: h.pred_boardings,
        trips: h.trips_running,
      })),
    [rd]
  );
  const lastHourly = useMemo(
    () =>
      (rd?.last_revealed_hourly ?? []).map((h) => ({
        hour: `${String(h.hour).padStart(2, "0")}:00`,
        predicted: h.pred_boardings,
        actual: h.actual_ridership,
        baseline: h.baseline_boardings,
      })),
    [rd]
  );

  const todayTotal = (rd?.current_day_hourly ?? []).reduce((a, h) => a + h.pred_boardings, 0);
  const todayDepartures = (rd?.current_day_hourly ?? []).reduce((a, h) => a + (h.trips_starting ?? 0), 0);
  const pol = state?.information_policy;
  const btn =
    "rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-800 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-50";

  return (
    <div className="space-y-6">
      <PageHeader
        title="Historical Replay"
        subtitle="A virtual clock steps through 18–31 October 2026. Each morning the frozen model forecasts the day using only boardings the delay rule allows. Recorded boardings appear only after the delay has passed, then the forecast is scored."
        period={`${REPLAY_START} to ${REPLAY_END} (unseen operational check; Aug–Sep test set is not replayed)`}
        source={state?.source ?? "models/final_forecaster.joblib · app_data/october_hourly_forecast_vs_actual.parquet"}
      />

      {error ? (
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">{error}</div>
      ) : null}

      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="text-sm font-bold text-slate-900">Clock controls</h2>
        <div className="mt-3 flex flex-wrap items-end gap-3">
          <div className="flex gap-2">
            {state?.session.status === "playing" ? (
              <button type="button" className={btn} disabled={busy} onClick={() => onControl({ action: "pause" })}>
                Pause
              </button>
            ) : (
              <button
                type="button"
                className={btn}
                disabled={busy || !state || state.completed}
                onClick={() => onControl({ action: "start" })}
              >
                Start
              </button>
            )}
            <button
              type="button"
              className={btn}
              disabled={busy || !state || state.completed}
              onClick={() => onControl({ action: "advance" })}
            >
              Advance one day
            </button>
          </div>
          <label className="flex flex-col gap-0.5 text-[11px] font-semibold text-slate-500">
            Speed
            <select
              aria-label="Replay speed"
              value={state?.session.speed_seconds ?? 5}
              onChange={(e) => onControl({ action: "speed", speed_seconds: Number(e.target.value) })}
              className="rounded-md border border-slate-300 px-2 py-1 text-xs text-slate-900"
            >
              {[2, 5, 10, 30].map((s) => (
                <option key={s} value={s}>
                  1 day every {s} s
                </option>
              ))}
            </select>
          </label>
          <span className="mx-1 h-8 w-px bg-slate-200" />
          <label className="flex flex-col gap-0.5 text-[11px] font-semibold text-slate-500">
            Start date
            <input
              type="date"
              aria-label="Replay start date"
              min={REPLAY_START}
              max={REPLAY_END}
              value={startDate}
              onChange={(e) => e.target.value && setStartDate(e.target.value)}
              className="rounded-md border border-slate-300 px-2 py-1 text-xs text-slate-900"
            />
          </label>
          <label className="flex flex-col gap-0.5 text-[11px] font-semibold text-slate-500">
            Reporting delay
            <select
              aria-label="Reporting delay"
              value={delay}
              onChange={(e) => setDelay(Number(e.target.value))}
              className="rounded-md border border-slate-300 px-2 py-1 text-xs text-slate-900"
            >
              {(state?.allowed_delays ?? [1, 7, 14, 21]).map((d) => (
                <option key={d} value={d}>
                  {d} day{d > 1 ? "s" : ""}
                  {d === 1 ? " (demo assumption)" : d === 21 ? " (close to the real ~19 days)" : ""}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            className="rounded-lg bg-slate-900 px-3 py-1.5 text-xs font-semibold text-white hover:bg-slate-800 disabled:opacity-50"
            disabled={busy || !state}
            onClick={() => onControl({ action: "reset", start_date: startDate, delay_days: delay })}
          >
            Reset with these settings
          </button>
        </div>
        <p className="mt-2 text-[11px] text-slate-500">
          Reset opens a new session. The old session and its saved forecasts are kept. Refreshing the page picks up the
          same session.
        </p>
      </section>

      {state && pol ? (
        <section className="grid gap-4 lg:grid-cols-3">
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm lg:col-span-1">
            <h2 className="text-sm font-bold text-slate-900">Information rule for this session</h2>
            <dl className="mt-3 space-y-2 text-xs">
              {[
                ["Virtual date", state.virtual_date],
                ["Status", state.session.status_label ?? state.session.status],
                ["Forecast issued", pol.issue_time],
                ["Forecast covers", pol.horizon],
                ["Reporting delay", `${pol.delay_days} day(s)`],
                ["Latest boardings the model may use", pol.latest_ridership_date_used],
                ["Recorded boardings shown through", pol.latest_revealed_date],
                ["Schedule", pol.schedule_snapshot],
                ["Model", pol.model_version],
                ["Session", state.session.session_id],
                ["Saved forecast rows", fmtInt(state.forecast_record_count)],
              ].map(([k, v]) => (
                <div key={k} className="grid grid-cols-2 gap-2">
                  <dt className="text-slate-500">{k}</dt>
                  <dd className="font-medium text-slate-900">{v}</dd>
                </div>
              ))}
            </dl>
            <p className="mt-3 rounded-md bg-amber-50 p-2 text-[11px] leading-snug text-amber-900">{pol.note}</p>
          </div>

          <div className="space-y-4 lg:col-span-2">
            <div className="grid gap-4 sm:grid-cols-2">
              <ScoreCard title="Whole network, revealed days" scores={state.network_scores} />
              {rd ? <ScoreCard title={`${route}, revealed days`} scores={rd.scores} /> : null}
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <h2 className="text-sm font-bold text-slate-900">Network boardings per day: forecast vs recorded</h2>
              <p className="text-[11px] text-slate-500">
                Totals over the scheduled route-hours the model forecast. Recorded values stay blank until revealed.
              </p>
              <div className="mt-2 h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart data={networkSeries} margin={{ top: 8, right: 12, left: 4, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                    <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => `${Math.round(v / 1000)}k`} />
                    <Tooltip formatter={(v: number) => (v === null || v === undefined ? NOT_AVAILABLE : fmtInt(v))} />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                    <Line name="Predicted boardings (experimental)" dataKey="forecast" stroke={C_PRED} strokeWidth={2} dot={{ r: 3 }} />
                    <Line name="4-week average" dataKey="baseline" stroke={C_BASE} strokeDasharray="5 4" dot={false} />
                    <Line name="Published boardings" dataKey="actual" stroke={C_ACTUAL} strokeWidth={2} dot={{ r: 3 }} connectNulls={false} />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
        </section>
      ) : (
        <div className="rounded-xl border border-slate-200 bg-white p-8 text-center text-sm text-slate-500">
          Starting a replay session...
        </div>
      )}

      {rd ? (
        <section className="grid gap-4 lg:grid-cols-2">
          <div className="rounded-xl border border-blue-200 bg-white p-4 shadow-sm" data-testid="forecast-card">
            <div className="flex items-start justify-between gap-2">
              <div>
                <h2 className="text-sm font-bold text-slate-900">
                  Forecast for {route} on {rd.current_day}
                </h2>
                <p className="text-[11px] text-slate-500">
                  Predicted boardings (experimental) · issued {pol?.issue_time}
                </p>
              </div>
              <div className="text-right">
                <div className="text-xl font-bold text-blue-700">{fmtInt(todayTotal)}</div>
                <div className="text-[11px] text-slate-500">boardings · {fmtInt(todayDepartures)} scheduled departures</div>
              </div>
            </div>
            {todayHourly.length === 0 ? (
              <p className="mt-4 text-sm text-slate-500">Not available: no scheduled trips for this route on this day.</p>
            ) : (
              <div className="mt-2 h-56">
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart data={todayHourly} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis dataKey="hour" tick={{ fontSize: 10 }} interval={2} />
                    <YAxis yAxisId="b" tick={{ fontSize: 10 }} />
                    <YAxis yAxisId="t" orientation="right" tick={{ fontSize: 10 }} />
                    <Tooltip formatter={(v: number) => fmtNum(v, 1)} />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                    <Bar yAxisId="t" name="Scheduled trips running" dataKey="trips" fill="#cbd5e1" />
                    <Line yAxisId="b" name="Predicted boardings" dataKey="predicted" stroke={C_PRED} strokeWidth={2} dot={false} />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <h2 className="text-sm font-bold text-slate-900">
              Latest revealed day for {route}: {rd.last_revealed_date ?? NOT_AVAILABLE}
            </h2>
            <p className="text-[11px] text-slate-500">The saved forecast next to what was recorded once the delay passed.</p>
            {lastHourly.length === 0 ? (
              <p className="mt-4 text-sm text-slate-500">
                Nothing revealed yet. With a {pol?.delay_days}-day delay, the first day is revealed on{" "}
                {state ? addDays(state.session.start_date, pol?.delay_days ?? 1) : NOT_AVAILABLE}.
              </p>
            ) : (
              <div className="mt-2 h-56">
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart data={lastHourly} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis dataKey="hour" tick={{ fontSize: 10 }} interval={2} />
                    <YAxis tick={{ fontSize: 10 }} />
                    <Tooltip formatter={(v: number) => fmtNum(v, 1)} />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                    <Line name="Published boardings" dataKey="actual" stroke={C_ACTUAL} strokeWidth={2} dot={false} />
                    <Line name="Predicted boardings" dataKey="predicted" stroke={C_PRED} strokeWidth={2} dot={false} />
                    <Line name="4-week average" dataKey="baseline" stroke={C_BASE} strokeDasharray="5 4" dot={false} />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm lg:col-span-2">
            <h2 className="text-sm font-bold text-slate-900">{route} daily totals in this replay</h2>
            <div className="mt-2 h-52">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={routeSeries} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip formatter={(v: number) => (v === null || v === undefined ? NOT_AVAILABLE : fmtInt(v))} />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                  <Line name="Predicted boardings (experimental)" dataKey="forecast" stroke={C_PRED} strokeWidth={2} dot={{ r: 3 }} />
                  <Line name="4-week average" dataKey="baseline" stroke={C_BASE} strokeDasharray="5 4" dot={false} />
                  <Line name="Published boardings" dataKey="actual" stroke={C_ACTUAL} strokeWidth={2} dot={{ r: 3 }} />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm lg:col-span-2">
            <h2 className="text-sm font-bold text-slate-900">Saved forecast records for {route} on {rd.current_day}</h2>
            <p className="text-[11px] text-slate-500">
              Each row was written once when the clock reached this day. It is never changed afterwards.
            </p>
            <div className="mt-2 max-h-72 overflow-auto">
              <table className="min-w-full text-left text-xs">
                <thead className="sticky top-0 bg-slate-50 text-[11px] uppercase text-slate-500">
                  <tr>
                    <th className="px-2 py-1.5">Hour</th>
                    <th className="px-2 py-1.5">Predicted boardings</th>
                    <th className="px-2 py-1.5">Trips running</th>
                    <th className="px-2 py-1.5">Past weeks used</th>
                    <th className="px-2 py-1.5">Latest boardings date used</th>
                    <th className="px-2 py-1.5">Issued</th>
                    <th className="px-2 py-1.5">Saved (real time, UTC)</th>
                    <th className="px-2 py-1.5">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {records.map((r) => (
                    <tr key={`${r.target_date}-${r.hour}`}>
                      <td className="px-2 py-1">{String(r.hour).padStart(2, "0")}:00</td>
                      <td className="px-2 py-1 font-semibold text-blue-700">{fmtNum(r.pred_boardings, 1)}</td>
                      <td className="px-2 py-1">{fmtNum(r.trips_running, 0)}</td>
                      <td className="px-2 py-1">{r.lags_available_count} of 4</td>
                      <td className="px-2 py-1">{r.latest_ridership_date_used}</td>
                      <td className="px-2 py-1">{r.issued_at}</td>
                      <td className="px-2 py-1 text-slate-500">{r.saved_at_wall.replace("T", " ").replace("+00:00", "")}</td>
                      <td className="px-2 py-1">{statusText[r.status] ?? r.status}</td>
                    </tr>
                  ))}
                  {records.length === 0 ? (
                    <tr>
                      <td colSpan={8} className="px-2 py-3 text-slate-500">
                        No saved forecast rows for this route and day.
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
          </div>
        </section>
      ) : null}

      <div className="flex flex-wrap gap-2">
        <button type="button" onClick={onCompare} className={btn}>
          Compare {route} with other routes
        </button>
        <button
          type="button"
          disabled={!state}
          onClick={() => state && onScenario(state.virtual_date)}
          className={btn}
        >
          Create a service scenario for {route}
        </button>
      </div>
    </div>
  );
};

function addDays(d: string, n: number): string {
  const dt = new Date(`${d}T00:00:00Z`);
  dt.setUTCDate(dt.getUTCDate() + n);
  return dt.toISOString().slice(0, 10);
}
