import React, { useEffect, useMemo, useState } from "react";
import { MapContainer, Polyline, TileLayer, Tooltip as LeafletTooltip } from "react-leaflet";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  api,
  CompareData,
  fmtInt,
  fmtNum,
  fmtSharePct,
  formatTimeBandLabel,
  HistoryQuery,
  NOT_AVAILABLE,
  RouteSummary,
} from "../api";
import { PageHeader } from "./PageHeader";

const ROUTE_COLORS = ["#2563eb", "#d97706", "#059669", "#7c3aed"];
const BAND_ORDER = ["early_morning", "morning_peak", "midday", "evening_peak", "night"];

interface ComparePageProps {
  routes: RouteSummary[];
  primaryRoute: string;
  query: HistoryQuery;
  onSelectRoute: (route: string) => void;
}

export const ComparePage: React.FC<ComparePageProps> = ({ routes, primaryRoute, query, onSelectRoute }) => {
  const [picked, setPicked] = useState<string[]>(() => {
    const partner = primaryRoute === "M15" ? "M15+" : "M15";
    return [primaryRoute, partner];
  });
  const [data, setData] = useState<CompareData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setPicked((prev) => (prev.includes(primaryRoute) ? prev : [primaryRoute, ...prev.filter((r) => r !== primaryRoute)].slice(0, 4)));
  }, [primaryRoute]);

  useEffect(() => {
    if (picked.length < 2) {
      setData(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    api
      .compareRoutes(picked, query)
      .then((d) => !cancelled && setData(d))
      .catch((e) => !cancelled && setError(e instanceof Error ? e.message : "Could not load the comparison."))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [picked, query.start, query.end, query.dayType, query.replayId, query.revealedThrough]);

  const colorOf = (r: string) => ROUTE_COLORS[picked.indexOf(r) % ROUTE_COLORS.length];

  const bandRows = useMemo(() => {
    if (!data) return [];
    return BAND_ORDER.map((tb) => {
      const row: Record<string, string | number | null> = { band: formatTimeBandLabel(tb).split(" (")[0] };
      data.routes.forEach((r) => {
        const b = r.time_bands.find((x) => x.time_band === tb);
        row[r.route] = b?.riders_per_service_hour ?? null;
      });
      return row;
    });
  }, [data]);

  const hourlyRows = useMemo(() => {
    if (!data) return [];
    return Array.from({ length: 24 }, (_, h) => {
      const row: Record<string, string | number | null> = { hour: `${String(h).padStart(2, "0")}:00` };
      data.routes.forEach((r) => {
        row[r.route] = r.hourly.find((x) => x.hour === h)?.mean_boardings ?? null;
      });
      return row;
    });
  }, [data]);

  const dailyRows = useMemo(() => {
    if (!data) return [];
    const dates = new Set<string>();
    data.routes.forEach((r) => r.daily.forEach((d) => dates.add(d.date)));
    return Array.from(dates)
      .sort()
      .map((d) => {
        const row: Record<string, string | number | null> = { date: d.slice(5) };
        data.routes.forEach((r) => {
          row[r.route] = r.daily.find((x) => x.date === d)?.boardings ?? null;
        });
        return row;
      });
  }, [data]);

  const metricRows: Array<[string, (r: CompareData["routes"][number]) => string]> = [
    ["Name", (r) => String(r.profile?.route_long_name ?? NOT_AVAILABLE)],
    ["Service type", (r) => String(r.profile?.service_type ?? NOT_AVAILABLE)],
    ["Route group", (r) => String(r.profile?.group_label ?? NOT_AVAILABLE).split(":")[0]],
    ["Length (km)", (r) => fmtNum(r.profile?.route_length_km as number | null, 1)],
    ["Stops", (r) => fmtInt(r.profile?.stop_count as number | null)],
    ["Stops served by no other route", (r) => fmtSharePct(r.profile?.exclusive_stop_share as number | null, 0)],
    ["Scheduled trips per weekday", (r) => fmtInt(r.profile?.trips_per_weekday as number | null)],
    ["Observed days in period", (r) => fmtInt(r.metrics?.observed_days)],
    ["Average daily boardings", (r) => fmtInt(r.metrics?.mean_daily_boardings)],
    ["Boardings per scheduled service hour", (r) => fmtNum(r.metrics?.riders_per_service_hour, 1)],
    ["Boardings per trip running", (r) => fmtNum(r.metrics?.riders_per_trip, 1)],
    ["Hours above its high riders-per-trip line", (r) => fmtSharePct(r.metrics?.share_hours_above_p75, 0)],
  ];

  const available = routes.filter((r) => !picked.includes(r.route));

  return (
    <div className="space-y-6">
      <PageHeader
        title="Compare Routes"
        subtitle="Put two to four routes side by side for the same dates and day type. Every value is a ratio of sums over the same recorded hours."
        period={data?.period ?? `${query.start} to ${query.end}`}
        source={data?.source ?? "app_data/obs_review_hourly_distribution.parquet"}
      />

      <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-semibold text-slate-600">Routes:</span>
          {picked.map((r) => (
            <span
              key={r}
              className="inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold"
              style={{ borderColor: colorOf(r), color: colorOf(r) }}
            >
              <span className="h-2 w-2 rounded-full" style={{ background: colorOf(r) }} />
              {r}
              {picked.length > 2 ? (
                <button
                  type="button"
                  aria-label={`Remove ${r}`}
                  onClick={() => setPicked(picked.filter((x) => x !== r))}
                  className="ml-0.5 text-slate-400 hover:text-slate-900"
                >
                  ×
                </button>
              ) : null}
            </span>
          ))}
          {picked.length < 4 ? (
            <select
              aria-label="Add a route to compare"
              value=""
              onChange={(e) => e.target.value && setPicked([...picked, e.target.value])}
              className="rounded-md border border-slate-300 px-2 py-1 text-xs"
            >
              <option value="">+ Add route</option>
              {available.map((r) => (
                <option key={r.route} value={r.route}>
                  {r.route} · {r.route_long_name}
                </option>
              ))}
            </select>
          ) : null}
          <span className="ml-auto text-[11px] text-slate-500">
            {query.dayType === "all" ? "All typical days" : query.dayType} · Published boardings · Scheduled service
          </span>
        </div>
        {data?.replay ? (
          <p className="mt-2 text-[11px] text-amber-800">
            Replay mode: recorded boardings after {data.replay.latest_revealed_date} are hidden.
          </p>
        ) : null}
        {data && data.excluded_dates.length ? (
          <p className="mt-1 text-[11px] text-slate-500">
            Left out of this period: {data.excluded_dates.map((d) => `${d.date} (${d.reason.split(" (")[0]})`).join(", ")}.
          </p>
        ) : null}
      </section>

      {error ? <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">{error}</div> : null}
      {loading && !data ? (
        <div className="rounded-xl border border-slate-200 bg-white p-8 text-center text-sm text-slate-500">Loading comparison...</div>
      ) : null}

      {data ? (
        <>
          <section className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
            <table className="min-w-full text-left text-xs" data-testid="compare-table">
              <thead className="bg-slate-50 text-[11px] uppercase text-slate-500">
                <tr>
                  <th className="px-3 py-2">Measure</th>
                  {data.routes.map((r) => (
                    <th key={r.route} className="px-3 py-2">
                      <button type="button" onClick={() => onSelectRoute(r.route)} className="font-bold hover:underline" style={{ color: colorOf(r.route) }}>
                        {r.route}
                      </button>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {metricRows.map(([label, fn]) => (
                  <tr key={label}>
                    <td className="px-3 py-1.5 text-slate-600">{label}</td>
                    {data.routes.map((r) => (
                      <td key={r.route} className="px-3 py-1.5 font-medium text-slate-900">
                        {fn(r)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          <section className="grid gap-4 lg:grid-cols-2">
            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <h2 className="text-sm font-bold text-slate-900">Boardings per scheduled service hour, by time of day</h2>
              <div className="mt-2 h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={bandRows} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis dataKey="band" tick={{ fontSize: 10 }} />
                    <YAxis tick={{ fontSize: 10 }} />
                    <Tooltip formatter={(v: number) => (v === null ? NOT_AVAILABLE : fmtNum(v, 1))} />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                    {data.routes.map((r) => (
                      <Bar key={r.route} dataKey={r.route} fill={colorOf(r.route)} />
                    ))}
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <h2 className="text-sm font-bold text-slate-900">Average boardings by hour</h2>
              <div className="mt-2 h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={hourlyRows} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis dataKey="hour" tick={{ fontSize: 10 }} interval={2} />
                    <YAxis tick={{ fontSize: 10 }} />
                    <Tooltip formatter={(v: number) => (v === null ? NOT_AVAILABLE : fmtNum(v, 1))} />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                    {data.routes.map((r) => (
                      <Line key={r.route} dataKey={r.route} stroke={colorOf(r.route)} strokeWidth={2} dot={false} />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm lg:col-span-2">
              <h2 className="text-sm font-bold text-slate-900">Daily boardings</h2>
              <p className="text-[11px] text-slate-500">Gaps are days left out of the typical-day table, not zero boardings.</p>
              <div className="mt-2 h-60">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={dailyRows} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis dataKey="date" tick={{ fontSize: 10 }} minTickGap={16} />
                    <YAxis tick={{ fontSize: 10 }} />
                    <Tooltip formatter={(v: number) => (v === null ? NOT_AVAILABLE : fmtInt(v))} />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                    {data.routes.map((r) => (
                      <Line key={r.route} dataKey={r.route} stroke={colorOf(r.route)} strokeWidth={1.5} dot={false} />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          </section>

          <section className="grid gap-4 lg:grid-cols-5">
            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm lg:col-span-3">
              <h2 className="text-sm font-bold text-slate-900">Where they run</h2>
              <p className="text-[11px] text-slate-500">Route shapes from GTFS {data.geometry_version ?? NOT_AVAILABLE}. The map shows paths, not bus positions.</p>
              <div className="mt-2 h-80 overflow-hidden rounded-lg border border-slate-200">
                <MapContainer center={[40.7831, -73.9712]} zoom={12} style={{ height: "100%", width: "100%" }} scrollWheelZoom={false}>
                  <TileLayer
                    attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                    url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                  />
                  {data.routes.map((r) =>
                    (r.geometry?.polylines ?? []).map((pl, i) => (
                      <Polyline key={`${r.route}-${i}`} positions={pl.coords} pathOptions={{ color: colorOf(r.route), weight: 4, opacity: 0.8 }}>
                        <LeafletTooltip sticky>{r.route}</LeafletTooltip>
                      </Polyline>
                    ))
                  )}
                </MapContainer>
              </div>
              <div className="mt-2 space-y-0.5 text-[11px] text-slate-500">
                {data.routes.map((r) => (
                  <div key={r.route}>
                    <span className="mr-1 inline-block h-2 w-2 rounded-full" style={{ background: colorOf(r.route) }} />
                    {r.route}: {r.geometry ? `${r.geometry.polylines.length} shape variant${r.geometry.polylines.length === 1 ? "" : "s"}` : "no shape available"} · GTFS {data.geometry_version ?? NOT_AVAILABLE}
                  </div>
                ))}
              </div>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm lg:col-span-2">
              <h2 className="text-sm font-bold text-slate-900">Shared stops</h2>
              {data.shared_stops.length === 0 ? (
                <p className="mt-2 text-sm text-slate-500">These routes share no stops in the GTFS stop lists.</p>
              ) : (
                <table className="mt-2 min-w-full text-left text-xs">
                  <thead className="text-[11px] uppercase text-slate-500">
                    <tr>
                      <th className="py-1">Pair</th>
                      <th className="py-1">Shared stops</th>
                      <th className="py-1">Share of smaller route</th>
                      <th className="py-1">Type</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {data.shared_stops.map((p) => (
                      <tr key={`${p.route_1}-${p.route_2}`}>
                        <td className="py-1 font-semibold">
                          {p.route_1} + {p.route_2}
                        </td>
                        <td className="py-1">{fmtInt(p.shared_stops_count)}</td>
                        <td className="py-1">{fmtSharePct(p.overlap_share, 0)}</td>
                        <td className="py-1">{p.overlap_category.replace(/_/g, " ")}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
              <p className="mt-3 text-[11px] text-slate-500">
                A high value on one measure can come from route length, speed or how often people get on and off. A low
                value can reflect a coverage role. Read these together, not as a single score.
              </p>
            </div>
          </section>
        </>
      ) : null}
    </div>
  );
};
