import React, { useEffect, useMemo, useState } from "react";
import { MapContainer, Polyline, TileLayer, CircleMarker, Tooltip as LeafletTooltip } from "react-leaflet";
import {
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  LineChart,
  Bar,
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
  fmtSharePct,
  formatDbscanLabel,
  formatReviewCategory,
  formatTimeBandLabel,
  RouteDetailData,
  RouteForecastData,
  RouteSummary,
} from "../api";
import { PageHeader } from "./PageHeader";

interface RouteDetailPageProps {
  routes: RouteSummary[];
  selectedRoute: string;
  onSelectRoute: (route: string) => void;
  onOpenScenario: (route: string, dayGroup: string, timeBand: string) => void;
}

export const RouteDetailPage: React.FC<RouteDetailPageProps> = ({
  routes,
  selectedRoute,
  onSelectRoute,
  onOpenScenario,
}) => {
  const [detail, setDetail] = useState<RouteDetailData | null>(null);
  const [forecast, setForecast] = useState<RouteForecastData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dayType, setDayType] = useState<string>("Typical Weekday");
  const [forecastMode, setForecastMode] = useState<"daily" | "hourly">("daily");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    Promise.all([
      api.getRouteDetail(selectedRoute),
      api.getRouteForecast(selectedRoute),
    ])
      .then(([d, f]) => {
        if (!cancelled) {
          setDetail(d);
          setForecast(f);
        }
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load route");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedRoute]);

  const hourlyData = useMemo(() => {
    if (!detail) return [];
    const rows = detail.hourly_patterns.filter(
      (r) => r.period === "jan_sep_typical" && r.day_type === dayType
    );
    const byHr = new Map(rows.map((r) => [r.hour, r]));
    return Array.from({ length: 24 }, (_, h) => {
      const r = byHr.get(h);
      return {
        hour: `${String(h).padStart(2, "0")}:00`,
        mean_ridership: r ? r.mean_ridership : null,
        mean_trips: r ? r.mean_trips_running : null,
        mean_rpt: r ? r.mean_riders_per_trip : null,
      };
    });
  }, [detail, dayType]);

  const hourlyForecastSeries = useMemo(() => {
    if (!forecast) return [];
    return forecast.october_hourly.map((r) => ({
      ts: `${String(r.date).slice(5)} ${String(r.hour).padStart(2, "0")}h`,
      actual: r.actual_ridership as number | null,
      pred_hgb: r.pred_ridership as number | null,
      baseline_4wk: r.lag_mean_available as number | null,
    }));
  }, [forecast]);

  const prof = detail?.profile;
  const geom = detail?.geometry;
  const mapCenter: [number, number] = geom?.center ?? [40.7831, -73.9712];

  const primaryTest = forecast?.test_summary?.primary as Record<string, unknown> | null | undefined;
  const valHgb = forecast?.validation_summary?.hgb as Record<string, unknown> | null | undefined;
  const octSum = forecast?.october_summary as Record<string, unknown> | null | undefined;

  return (
    <div className="space-y-6">
      <PageHeader
        title={`Route Profile & Forecast Diagnostics: ${selectedRoute}`}
        subtitle={
          prof
            ? `${prof.route_long_name} — ${prof.service_type} | ${prof.group_label ?? "not available"}`
            : "Loading route profile..."
        }
        period={
          detail?.period ??
          "Jan–Sep 2026 Typical Ridership, Spring 2026-04-09 GTFS & Oct 18–31 Operational Check"
        }
        source={
          detail?.source ?? "app_data/routes_summary.csv, route_hourly_pattern.csv & forecasts"
        }
        rightSlot={
          <div className="flex items-center gap-2">
            <label htmlFor="route-select" className="text-xs font-medium text-slate-600">
              Select Route:
            </label>
            <select
              id="route-select"
              value={selectedRoute}
              onChange={(e) => onSelectRoute(e.target.value)}
              className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-semibold text-slate-900"
            >
              {routes.map((r) => (
                <option key={r.route} value={r.route}>
                  {r.route} — {r.route_long_name}
                </option>
              ))}
            </select>
          </div>
        }
      />

      {error ? (
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      ) : null}

      {loading && !detail ? (
        <div className="rounded-xl border border-slate-200 bg-white p-8 text-center text-sm text-slate-500">
          Loading {selectedRoute} details...
        </div>
      ) : null}

      {prof ? (
        <>
          {/* Route Profile Metrics */}
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
            <div className="rounded-xl border border-slate-200 bg-white p-3.5 shadow-sm">
              <div className="text-[11px] font-medium uppercase text-slate-500">
                Avg Weekday Riders
              </div>
              <div className="mt-1 text-lg font-bold text-slate-900">
                {fmtInt(prof.avg_daily_riders)}
              </div>
              <div className="text-[11px] text-slate-500">
                CV: {fmtNum(prof.demand_variability, 3)}
              </div>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-3.5 shadow-sm">
              <div className="text-[11px] font-medium uppercase text-slate-500">
                Weekday / Sat / Sun Trips
              </div>
              <div className="mt-1 text-lg font-bold text-slate-900">
                {fmtInt(prof.trips_per_weekday)} / {fmtInt(prof.trips_per_saturday)} /{" "}
                {fmtInt(prof.trips_per_sunday)}
              </div>
              <div className="text-[11px] text-slate-500">
                Peak gap: {prof.morning_peak_avg_gap_min === null ? "not available" : `${fmtNum(prof.morning_peak_avg_gap_min)} min`}
              </div>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-3.5 shadow-sm">
              <div className="text-[11px] font-medium uppercase text-slate-500">
                Length & Stops
              </div>
              <div className="mt-1 text-lg font-bold text-slate-900">
                {fmtNum(prof.route_length_km, 2)} km
              </div>
              <div className="text-[11px] text-slate-500">
                {fmtInt(prof.stop_count)} stops ({fmtSharePct(prof.exclusive_stop_share)} exclusive)
              </div>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-3.5 shadow-sm">
              <div className="text-[11px] font-medium uppercase text-slate-500">
                Peak Riders / Trip & Speed
              </div>
              <div className="mt-1 text-lg font-bold text-slate-900">
                {fmtNum(prof.peak_riders_per_trip, 1)} rpt
              </div>
              <div className="text-[11px] text-slate-500">
                Speed: {fmtNum(prof.avg_scheduled_speed_kmh, 1)} km/h
              </div>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-3.5 shadow-sm">
              <div className="text-[11px] font-medium uppercase text-slate-500">
                Fixed p75 Thresholds (Wk / Sat / Sun)
              </div>
              <div className="mt-1 text-base font-bold text-slate-900">
                {fmtNum(prof.p75_weekday, 1)} / {fmtNum(prof.p75_saturday, 1)} /{" "}
                {fmtNum(prof.p75_sunday, 1)}
              </div>
              <div className="text-[11px] text-slate-500">Fixed Jan–May riders/trip</div>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-3.5 shadow-sm">
              <div className="text-[11px] font-medium uppercase text-slate-500">
                Service Span & Group
              </div>
              <div className="mt-1 text-sm font-bold text-slate-900">
                {prof.first_departure ?? "not available"} – {prof.last_departure ?? "not available"}
              </div>
              <div className="text-[11px] text-slate-500">
                {prof.is_outlier_removed_before_kmeans
                  ? "Outlier route (M35)"
                  : `Group ${fmtInt(prof.group_id)} | ${formatDbscanLabel(prof.dbscan_eps180_label)}`}
              </div>
            </div>
          </div>

          {/* Hourly Profile + Corridor Map */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm lg:col-span-2">
              <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                <div>
                  <h2 className="text-sm font-semibold text-slate-900">
                    Hourly Ridership vs Scheduled Trips ({dayType})
                  </h2>
                  <p className="text-xs text-slate-500">
                    Mean hourly riders and scheduled trips running across Jan–Sep 2026 typical normal days.
                  </p>
                </div>
                <div className="flex gap-1.5">
                  {["Typical Weekday", "Typical Saturday", "Typical Sunday"].map((dt) => (
                    <button
                      key={dt}
                      type="button"
                      onClick={() => setDayType(dt)}
                      className={`rounded-lg px-2.5 py-1 text-xs font-medium ${
                        dayType === dt
                          ? "bg-blue-600 text-white"
                          : "bg-slate-100 text-slate-700 hover:bg-slate-200"
                      }`}
                    >
                      {dt.replace("Typical ", "")}
                    </button>
                  ))}
                </div>
              </div>
              <div className="h-72 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart data={hourlyData} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis dataKey="hour" tick={{ fontSize: 10 }} interval={2} />
                    <YAxis yAxisId="left" tick={{ fontSize: 11 }} />
                    <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 11 }} />
                    <Tooltip
                      formatter={(val: unknown, name: string) => [
                        val === null || val === undefined ? "not available" : fmtNum(Number(val), 1),
                        name,
                      ]}
                    />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    <Bar
                      yAxisId="right"
                      dataKey="mean_trips"
                      name="Scheduled Trips / Hr"
                      fill="#cbd5e1"
                      radius={[3, 3, 0, 0]}
                      isAnimationActive={false}
                    />
                    <Line
                      yAxisId="left"
                      type="monotone"
                      dataKey="mean_ridership"
                      name="Mean Ridership / Hr"
                      stroke="#1d4ed8"
                      strokeWidth={2.4}
                      dot={false}
                      connectNulls={false}
                      isAnimationActive={false}
                    />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <h2 className="mb-1 text-sm font-semibold text-slate-900">
                GTFS Route Corridor ({selectedRoute})
              </h2>
              <p className="mb-3 text-xs text-slate-500">
                Spring 2026-04-09 GTFS shapes and sampled stops.
              </p>
              <div className="h-72 w-full overflow-hidden rounded-lg border border-slate-200">
                <MapContainer
                  key={selectedRoute}
                  center={mapCenter}
                  zoom={12}
                  style={{ height: "100%", width: "100%" }}
                >
                  <TileLayer
                    attribution="&copy; OpenStreetMap"
                    url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                  />
                  {geom?.polylines.map((pl, idx) => (
                    <Polyline
                      key={`${selectedRoute}-${pl.direction_id}`}
                      positions={pl.coords}
                      pathOptions={{
                        color: idx === 0 ? "#1d4ed8" : "#059669",
                        weight: 4,
                        opacity: 0.85,
                      }}
                    />
                  ))}
                  {geom?.sample_stops.map((st) => (
                    <CircleMarker
                      key={st.stop_id}
                      center={[st.lat, st.lon]}
                      radius={4}
                      pathOptions={{ color: "#0f172a", fillColor: "#ffffff", fillOpacity: 1, weight: 1.5 }}
                    >
                      <LeafletTooltip>{st.stop_name}</LeafletTooltip>
                    </CircleMarker>
                  ))}
                </MapContainer>
              </div>
            </div>
          </div>

          {/* Forecast vs Actual Section */}
          {forecast ? (
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <h2 className="text-base font-semibold text-slate-900">
                    Forecast vs Actual Performance ({selectedRoute})
                  </h2>
                  <p className="text-xs text-slate-500">{forecast.note}</p>
                </div>
                <div className="flex gap-1.5">
                  <button
                    type="button"
                    onClick={() => setForecastMode("daily")}
                    className={`rounded-lg px-2.5 py-1 text-xs font-medium ${
                      forecastMode === "daily"
                        ? "bg-blue-600 text-white"
                        : "bg-slate-100 text-slate-700"
                    }`}
                  >
                    October Daily Totals (14d)
                  </button>
                  <button
                    type="button"
                    onClick={() => setForecastMode("hourly")}
                    className={`rounded-lg px-2.5 py-1 text-xs font-medium ${
                      forecastMode === "hourly"
                        ? "bg-blue-600 text-white"
                        : "bg-slate-100 text-slate-700"
                    }`}
                  >
                    October Hourly Series
                  </button>
                </div>
              </div>

              <div className="mb-4 grid grid-cols-1 gap-3 md:grid-cols-3">
                <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs">
                  <div className="font-semibold text-slate-800">Validation (Jun–Jul)</div>
                  <div className="mt-1">
                    HGB WAPE:{" "}
                    <span className="font-bold text-slate-900">
                      {fmtPct(valHgb?.wape_pct as number | null, 2)}
                    </span>{" "}
                    | Bias: {fmtNum(valHgb?.bias_pred_minus_actual as number | null, 2)} r/hr
                  </div>
                </div>
                <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs">
                  <div className="font-semibold text-slate-800">
                    Official Logged Test (Aug–Sep)
                  </div>
                  <div className="mt-1">
                    HGB WAPE:{" "}
                    <span className="font-bold text-slate-900">
                      {fmtPct(primaryTest?.wape_hgb_pct as number | null, 2)}
                    </span>{" "}
                    vs 4-Wk Avg:{" "}
                    <span className="font-bold">
                      {fmtPct(primaryTest?.wape_4wk_pct as number | null, 2)}
                    </span>
                  </div>
                </div>
                <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs">
                  <div className="font-semibold text-slate-800">
                    October Operational Check (Oct 18–31)
                  </div>
                  <div className="mt-1">
                    Frozen HGB WAPE:{" "}
                    <span className="font-bold text-slate-900">
                      {fmtPct(octSum?.wape_pct_frozen_cut as number | null, 2)}
                    </span>{" "}
                    vs 4-Wk Avg:{" "}
                    <span className="font-bold">
                      {fmtPct(octSum?.wape_4wk_cut as number | null, 2)}
                    </span>
                  </div>
                </div>
              </div>

              <div className="h-72 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  {forecastMode === "daily" ? (
                    <LineChart data={forecast.october_daily}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                      <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                      <YAxis tick={{ fontSize: 11 }} />
                      <Tooltip
                        formatter={(val: unknown) => fmtNum(val as number | null, 0)}
                      />
                      <Legend wrapperStyle={{ fontSize: 12 }} />
                      <Line
                        type="monotone"
                        dataKey="actual_ridership"
                        name="Observed Ridership"
                        stroke="#0f172a"
                        strokeWidth={2.4}
                        isAnimationActive={false}
                      />
                      <Line
                        type="monotone"
                        dataKey="pred_ridership"
                        name="Frozen Step 5 HGB Forecast"
                        stroke="#2563eb"
                        strokeWidth={2}
                        isAnimationActive={false}
                      />
                      <Line
                        type="monotone"
                        dataKey="baseline_4wk_ridership"
                        name="4-Week Average Baseline"
                        stroke="#d97706"
                        strokeDasharray="4 4"
                        strokeWidth={1.8}
                        isAnimationActive={false}
                      />
                    </LineChart>
                  ) : (
                    <LineChart data={hourlyForecastSeries}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                      <XAxis dataKey="ts" tick={{ fontSize: 10 }} minTickGap={24} />
                      <YAxis tick={{ fontSize: 11 }} />
                      <Tooltip
                        formatter={(val: unknown) => fmtNum(val as number | null, 0)}
                      />
                      <Legend wrapperStyle={{ fontSize: 12 }} />
                      <Line
                        type="monotone"
                        dataKey="actual"
                        name="Actual"
                        stroke="#0f172a"
                        strokeWidth={2}
                        dot={false}
                        isAnimationActive={false}
                      />
                      <Line
                        type="monotone"
                        dataKey="pred_hgb"
                        name="Frozen HGB Forecast"
                        stroke="#2563eb"
                        strokeWidth={1.8}
                        dot={false}
                        isAnimationActive={false}
                      />
                      <Line
                        type="monotone"
                        dataKey="baseline_4wk"
                        name="4-Wk Avg Baseline"
                        stroke="#d97706"
                        strokeDasharray="3 3"
                        strokeWidth={1.5}
                        dot={false}
                        isAnimationActive={false}
                      />
                    </LineChart>
                  )}
                </ResponsiveContainer>
              </div>
            </div>
          ) : null}

          {/* Overlap Partners & Review Cells */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <h3 className="mb-3 text-sm font-semibold text-slate-900">
                Top Stop Overlap Partners ({detail?.overlaps.length ?? 0} pairs)
              </h3>
              {detail?.overlaps.length ? (
                <div className="max-h-72 overflow-y-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="border-b border-slate-200 text-slate-500">
                      <tr>
                        <th className="py-2 pr-2 font-medium">Partner</th>
                        <th className="py-2 pr-2 font-medium">Category</th>
                        <th className="py-2 pr-2 text-right font-medium">Shared Stops</th>
                        <th className="py-2 text-right font-medium">Overlap Share</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {detail.overlaps.slice(0, 12).map((o) => (
                        <tr key={o.partner_route}>
                          <td className="py-2 pr-2">
                            <button
                              type="button"
                              onClick={() => onSelectRoute(o.partner_route)}
                              className="font-semibold text-blue-700 hover:underline"
                            >
                              {o.partner_route}
                            </button>
                          </td>
                          <td className="py-2 pr-2">
                            <span
                              className={`rounded px-2 py-0.5 font-medium ${
                                o.overlap_category === "same_family"
                                  ? "bg-indigo-50 text-indigo-700"
                                  : "bg-amber-50 text-amber-800"
                              }`}
                            >
                              {o.overlap_category}
                            </span>
                          </td>
                          <td className="py-2 pr-2 text-right font-mono">
                            {o.shared_stops_count} / {o.smaller_route_stops}
                          </td>
                          <td className="py-2 text-right font-mono">
                            {fmtSharePct(o.overlap_share)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="text-xs text-slate-500">
                  No shared stops with other Manhattan routes (100% exclusive stops).
                </div>
              )}
            </div>

            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <h3 className="mb-3 text-sm font-semibold text-slate-900">
                Aug–Oct 2026 Review Cells ({detail?.review_cells.length ?? 0})
              </h3>
              <div className="max-h-72 overflow-y-auto">
                <table className="w-full text-left text-xs">
                  <thead className="border-b border-slate-200 text-slate-500">
                    <tr>
                      <th className="py-2 pr-2 font-medium">Day / Time Band</th>
                      <th className="py-2 pr-2 text-right font-medium">Riders/Svc-Hr</th>
                      <th className="py-2 pr-2 text-right font-medium">High Hr %</th>
                      <th className="py-2 pr-2 font-medium">Category</th>
                      <th className="py-2 font-medium">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {detail?.review_cells.map((c) => (
                      <tr key={`${c.day_group}-${c.time_band}`}>
                        <td className="py-2 pr-2">
                          <div className="font-medium text-slate-900">
                            {c.day_group} · {formatTimeBandLabel(c.time_band)}
                          </div>
                          <div className="text-[11px] text-slate-500">{c.days_count} days</div>
                        </td>
                        <td className="py-2 pr-2 text-right font-mono">
                          {fmtNum(c.obs_riders_per_service_hour, 1)}
                        </td>
                        <td className="py-2 pr-2 text-right font-mono">
                          {fmtPct(c.high_demand_freq_pct, 1)}
                        </td>
                        <td className="py-2 pr-2">{formatReviewCategory(c.review_category)}</td>
                        <td className="py-2">
                          <button
                            type="button"
                            onClick={() => onOpenScenario(c.route, c.day_group, c.time_band)}
                            className="rounded bg-blue-50 px-2 py-1 text-[11px] font-medium text-blue-700 hover:bg-blue-100"
                          >
                            Test Scenario
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
};

