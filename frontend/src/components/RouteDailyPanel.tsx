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
import { api, fmtInt, fmtNum, fmtSharePct, HistoryQuery, NOT_AVAILABLE, RouteDailyData } from "../api";

interface RouteDailyPanelProps {
  route: string;
  query: HistoryQuery;
  geometryVersion?: string | null;
}

export const RouteDailyPanel: React.FC<RouteDailyPanelProps> = ({ route, query, geometryVersion }) => {
  const [data, setData] = useState<RouteDailyData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    api
      .getRouteDaily(route, query)
      .then((d) => !cancelled && setData(d))
      .catch((e) => !cancelled && setError(e instanceof Error ? e.message : "Could not load daily history."));
    return () => {
      cancelled = true;
    };
  }, [route, query.start, query.end, query.dayType, query.replayId, query.revealedThrough]);

  const series = useMemo(
    () =>
      (data?.rows ?? []).map((r) => ({
        date: r.date.slice(5),
        boardings: r.boardings,
        service_hours: r.service_hours,
        rpsh: r.riders_per_service_hour,
      })),
    [data]
  );
  const s = data?.summary;

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm" data-testid="route-daily-panel">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-base font-bold text-slate-900">Daily history for {route}</h2>
          <p className="text-xs text-slate-600">
            {data?.period ?? `${query.start} to ${query.end}`} · Published boardings · Scheduled service
          </p>
        </div>
        <p className="max-w-md text-[11px] text-slate-500">
          Route shape shown on the map comes from GTFS {geometryVersion ?? NOT_AVAILABLE}. Service counts for each day come
          from the timetable that was in force on that day.
        </p>
      </div>

      {error ? <div className="mt-3 rounded-md bg-red-50 p-3 text-xs text-red-800">{error}</div> : null}

      {s ? (
        <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-5">
          {[
            ["Observed days", fmtInt(s.observed_days)],
            ["Average daily boardings", fmtInt(s.mean_daily_boardings)],
            ["Boardings per service hour", fmtNum(s.riders_per_service_hour, 1)],
            ["Boardings per trip running", fmtNum(s.riders_per_trip, 1)],
            ["Hours above its high line", fmtSharePct(s.share_hours_above_p75, 0)],
          ].map(([k, v]) => (
            <div key={k} className="rounded-lg bg-slate-50 p-3">
              <div className="text-lg font-bold text-slate-900">{v}</div>
              <div className="text-[11px] text-slate-500">{k}</div>
            </div>
          ))}
        </div>
      ) : data ? (
        <p className="mt-4 text-sm text-slate-500">Not available: no recorded hours for this route in the chosen period.</p>
      ) : null}

      {series.length ? (
        <div className="mt-4 h-64">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={series} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="date" tick={{ fontSize: 10 }} minTickGap={14} />
              <YAxis yAxisId="b" tick={{ fontSize: 10 }} />
              <YAxis yAxisId="r" orientation="right" tick={{ fontSize: 10 }} />
              <Tooltip formatter={(v: number, name: string) => (name.includes("per") ? fmtNum(v, 1) : fmtInt(v))} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Bar yAxisId="b" name="Published boardings" dataKey="boardings" fill="#0f172a" />
              <Line yAxisId="r" name="Boardings per scheduled service hour" dataKey="rpsh" stroke="#64748b" strokeWidth={2} dot={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      ) : null}

      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-slate-500">
        {data?.excluded_dates.length ? (
          <span>
            Left out: {data.excluded_dates.map((d) => `${d.date} (${d.reason.split(" (")[0]})`).join(", ")}. These are gaps,
            not zero boardings.
          </span>
        ) : null}
        {data?.replay ? (
          <span className="text-amber-800">Replay mode: boardings after {data.replay.latest_revealed_date} are hidden.</span>
        ) : null}
      </div>
    </section>
  );
};
