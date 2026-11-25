import { useEffect, useState } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { apiClient } from "../api/client";
import {
  EmptyState,
  ErrorState,
  LoadingState,
  MethodNote,
  SectionCard,
  formatInt,
  formatNum,
} from "../components/ui";
import type { RidershipTimeseriesResponse, RouteSummaryItem } from "../types/api";

export function RidershipPage({ initialRouteId }: { initialRouteId?: string | null }) {
  const [routes, setRoutes] = useState<RouteSummaryItem[]>([]);
  const [routeId, setRouteId] = useState<string>(initialRouteId ?? "151");
  const [granularity, setGranularity] = useState<"monthly" | "daily">("monthly");
  const [startDate, setStartDate] = useState<string>("2025-01-01");
  const [endDate, setEndDate] = useState<string>("2026-08-31");
  const [daytype, setDaytype] = useState<string>("");
  const [data, setData] = useState<RidershipTimeseriesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (initialRouteId) setRouteId(initialRouteId);
  }, [initialRouteId]);

  useEffect(() => {
    const controller = new AbortController();
    apiClient
      .getRoutes({ limit: 150, offset: 0 }, controller.signal)
      .then((res) => setRoutes(res.data))
      .catch(() => {});
    return () => controller.abort();
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    apiClient
      .getRidershipTimeseries(
        routeId,
        {
          granularity,
          start_date: startDate || undefined,
          end_date: endDate || undefined,
          daytype: granularity === "daily" && daytype ? daytype : undefined,
          limit: 150,
          offset: 0,
        },
        controller.signal
      )
      .then(setData)
      .catch((err: unknown) => {
        if (err instanceof DOMException && err.name === "AbortError") return;
        setError(err instanceof Error ? err.message : "Failed to load ridership time series.");
      })
      .finally(() => setLoading(false));

    return () => controller.abort();
  }, [routeId, granularity, startDate, endDate, daytype]);

  const chartSeries =
    data?.data.map((obs) => ({
      period: obs.period,
      value: granularity === "monthly" ? obs.total_rides : obs.rides,
    })) ?? [];

  return (
    <div className="space-y-6">
      <MethodNote title="Metric Scope & Occupancy Boundary" tone="warning">
        Daily route ridership represents total CTA system boardings per route-day from{" "}
        <code>analytical.daily_ridership</code>. It does <strong>not</strong> measure simultaneous onboard passenger
        occupancy or stop-level crowding, and missing calendar dates are never fabricated.
      </MethodNote>

      <SectionCard
        title="Historical Ridership Filters"
        subtitle="Query DuckDB daily or monthly bus ridership (2024-01-01 to 2026-08-31)"
      >
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <div>
            <label htmlFor="ridership-route" className="mb-1 block text-xs text-slate-400">
              Route
            </label>
            <select
              id="ridership-route"
              value={routeId}
              onChange={(e) => setRouteId(e.target.value)}
              className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs text-slate-100"
            >
              {routes.length === 0 ? (
                <option value={routeId}>{routeId}</option>
              ) : (
                routes.map((r) => (
                  <option key={r.route_id} value={r.route_id}>
                    {r.route_id} — {r.route_long_name} ({r.is_rail ? "Rail" : "Bus"})
                  </option>
                ))
              )}
            </select>
          </div>

          <div>
            <label htmlFor="ridership-granularity" className="mb-1 block text-xs text-slate-400">
              Granularity
            </label>
            <select
              id="ridership-granularity"
              value={granularity}
              onChange={(e) => setGranularity(e.target.value as "monthly" | "daily")}
              className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs text-slate-100"
            >
              <option value="monthly">Monthly</option>
              <option value="daily">Daily (max 366d span)</option>
            </select>
          </div>

          <div>
            <label htmlFor="ridership-start" className="mb-1 block text-xs text-slate-400">
              Start Date
            </label>
            <input
              id="ridership-start"
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs text-slate-100"
            />
          </div>

          <div>
            <label htmlFor="ridership-end" className="mb-1 block text-xs text-slate-400">
              End Date
            </label>
            <input
              id="ridership-end"
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs text-slate-100"
            />
          </div>

          <div>
            <label htmlFor="ridership-daytype" className="mb-1 block text-xs text-slate-400">
              Daytype (Daily only)
            </label>
            <select
              id="ridership-daytype"
              value={daytype}
              disabled={granularity === "monthly"}
              onChange={(e) => setDaytype(e.target.value)}
              className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs text-slate-100 disabled:opacity-40"
            >
              <option value="">All</option>
              <option value="W">Weekday (W)</option>
              <option value="A">Saturday (A)</option>
              <option value="U">Sunday/Holiday (U)</option>
            </select>
          </div>
        </div>
      </SectionCard>

      {loading ? (
        <LoadingState label="Querying DuckDB ridership history..." />
      ) : error ? (
        <ErrorState message={error} />
      ) : !data ? (
        <EmptyState />
      ) : !data.ridership_available ? (
        <EmptyState
          title={`Ridership Unavailable for Route ${data.route_id}`}
          description={data.unavailable_reason ?? "Bus-only ridership table does not include rail lines."}
        />
      ) : data.data.length === 0 ? (
        <EmptyState
          title="No ridership observations in selected window"
          description="Try widening the date range (valid historical window: 2024-01-01 to 2026-08-31)."
        />
      ) : (
        <SectionCard
          title={`Route ${data.route_id} — ${data.route_long_name}`}
          subtitle={`${data.total_observations} ${granularity} observations • Actual range: ${data.actual_date_range?.start_date ?? "N/A"} to ${data.actual_date_range?.end_date ?? "N/A"}`}
        >
          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartSeries} margin={{ top: 8, right: 16, left: 10, bottom: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="period" stroke="#94a3b8" fontSize={11} />
                <YAxis stroke="#94a3b8" fontSize={12} />
                <Tooltip
                  contentStyle={{ backgroundColor: "#0f172a", borderColor: "#334155", color: "#f8fafc" }}
                />
                <Line
                  type="monotone"
                  dataKey="value"
                  name={granularity === "monthly" ? "Total Monthly Rides" : "Daily Rides"}
                  stroke="#38bdf8"
                  strokeWidth={2}
                  dot={{ r: 2 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="mt-5 max-h-64 overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-slate-800 text-slate-400">
                <tr>
                  <th className="py-2 pr-3">Period</th>
                  {granularity === "monthly" ? (
                    <>
                      <th className="py-2 pr-3 text-right">Total Rides</th>
                      <th className="py-2 pr-3 text-right">Days</th>
                      <th className="py-2 text-right">Weekday Avg</th>
                    </>
                  ) : (
                    <>
                      <th className="py-2 pr-3">Daytype</th>
                      <th className="py-2 text-right">Rides (0 preserved)</th>
                    </>
                  )}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/70">
                {data.data.slice(0, 30).map((obs) => (
                  <tr key={`${obs.period}-${obs.daytype ?? "m"}`}>
                    <td className="py-2 pr-3 font-mono text-slate-200">{obs.period}</td>
                    {granularity === "monthly" ? (
                      <>
                        <td className="py-2 pr-3 text-right text-slate-100">{formatInt(obs.total_rides)}</td>
                        <td className="py-2 pr-3 text-right text-slate-300">{formatInt(obs.observation_days)}</td>
                        <td className="py-2 text-right text-slate-300">{formatNum(obs.weekday_avg_rides, 1)}</td>
                      </>
                    ) : (
                      <>
                        <td className="py-2 pr-3 text-slate-300">{obs.daytype ?? "N/A"}</td>
                        <td className="py-2 text-right font-semibold text-slate-100">
                          {obs.rides === 0 ? "0" : formatInt(obs.rides)}
                        </td>
                      </>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </SectionCard>
      )}
    </div>
  );
}
