import React, { useMemo, useState } from "react";
import {
  Area,
  AreaChart,
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
  fmtInt,
  fmtNum,
  fmtSharePct,
  NetworkDailyRow,
  NetworkHourlyRow,
  OverviewData,
} from "../api";
import { PageHeader } from "./PageHeader";

interface OverviewPageProps {
  overview: OverviewData;
  dailyRows: NetworkDailyRow[];
  hourlyJanSep: NetworkHourlyRow[];
  hourlyAugOct: NetworkHourlyRow[];
  onSelectRoute: (route: string) => void;
}

export const OverviewPage: React.FC<OverviewPageProps> = ({
  overview,
  dailyRows,
  hourlyJanSep,
  hourlyAugOct,
  onSelectRoute,
}) => {
  const [periodTag, setPeriodTag] = useState<string>("all");
  const [hourlyWindow, setHourlyWindow] = useState<"jan_sep" | "aug_oct">("jan_sep");
  const [hourlyMetric, setHourlyMetric] = useState<"ridership" | "rpt">("ridership");

  const filteredDaily = useMemo(() => {
    const base =
      periodTag === "all"
        ? dailyRows
        : dailyRows.filter((r) => r.period_tag === periodTag);
    return base.map((r) => ({
      ...r,
      ridership_plot: r.is_missing ? null : r.total_ridership,
    }));
  }, [dailyRows, periodTag]);

  const hourlyByHour = useMemo(() => {
    const src = hourlyWindow === "jan_sep" ? hourlyJanSep : hourlyAugOct;
    const byHr: Record<number, Record<string, unknown>> = {};
    for (let h = 0; h < 24; h++) {
      byHr[h] = { hour: `${String(h).padStart(2, "0")}:00`, hrNum: h };
    }
    src.forEach((row) => {
      const val =
        hourlyMetric === "ridership"
          ? row.mean_network_ridership
          : row.mean_riders_per_trip;
      if (row.day_type === "Typical Weekday") byHr[row.hour].weekday = val;
      if (row.day_type === "Typical Saturday") byHr[row.hour].saturday = val;
      if (row.day_type === "Typical Sunday") byHr[row.hour].sunday = val;
    });
    return Object.values(byHr);
  }, [hourlyWindow, hourlyJanSep, hourlyAugOct, hourlyMetric]);

  const ov = overview.overview;
  const v = overview.version;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Network Overview & Temporal Patterns"
        subtitle="Manhattan bus network study pipeline across MTA hourly ridership and GTFS timetables, tracking data exclusions, splits, and typical daily/hourly demand profiles."
        period={overview.period}
        source={overview.source}
        rightSlot={
          <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-right text-xs text-slate-600">
            <div>
              Build commit: <code className="font-semibold text-slate-900">{v.git_commit}</code>
            </div>
            <div>Exported: {v.export_date.slice(0, 10)}</div>
          </div>
        }
      />

      {/* Top KPI Cards */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="text-xs font-medium uppercase tracking-wide text-slate-500">
            Routes Included
          </div>
          <div className="mt-1 text-2xl font-bold text-slate-900">
            {fmtInt(ov.cleaning.routes_kept)}
          </div>
          <div className="mt-1 text-xs text-slate-500">
            {ov.cleaning.dropped_routes.length} non-Manhattan / pre-SBS / shuttle dropped
          </div>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="text-xs font-medium uppercase tracking-wide text-slate-500">
            Main Matched Rows (Jan–Sep)
          </div>
          <div className="mt-1 text-2xl font-bold text-slate-900">
            {fmtInt(ov.row_counts.matched_hourly_jan_sep)}
          </div>
          <div className="mt-1 text-xs text-slate-500">
            + {fmtInt(ov.row_counts.october_operational_rows)} active rows in Oct 18–31 check
          </div>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="text-xs font-medium uppercase tracking-wide text-slate-500">
            Excluded Dates & Outages
          </div>
          <div className="mt-1 text-2xl font-bold text-slate-900">
            {ov.exclusions.missing_ridership_dates.length}m /{" "}
            {ov.exclusions.storm_dates.length}s / {ov.exclusions.public_holidays.length}h
          </div>
          <div className="mt-1 text-xs text-slate-500">
            6 missing Jan days, 4 snow/storm days, {ov.exclusions.public_holidays.length} holidays, 4 outage blocks
          </div>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="text-xs font-medium uppercase tracking-wide text-slate-500">
            Official Test Runs Logged
          </div>
          <div className="mt-1 text-2xl font-bold text-emerald-700">
            {fmtInt(v.official_test_runs_logged)}
          </div>
          <div className="mt-1 text-xs text-slate-500">
            {ov.row_counts.more_trips_candidates} more-trips /{" "}
            {ov.row_counts.fewer_trips_candidates} fewer-trips cells (Aug–Oct)
          </div>
        </div>
      </div>

      {/* Daily Ridership Chart */}
      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-base font-semibold text-slate-900">
              Daily Network Ridership (Jan 4 – Oct 31, 2026)
            </h2>
            <p className="text-xs text-slate-500">
              Missing ridership dates (2026-01-10 to 2026-01-15) remain gapped as &quot;not available&quot; rather than coerced to 0.
            </p>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {[
              { id: "all", label: "All Months" },
              { id: "train", label: "Train (Jan–May)" },
              { id: "val", label: "Val (Jun–Jul)" },
              { id: "test", label: "Test (Aug–Sep)" },
              { id: "october", label: "Oct (1–31)" },
            ].map((btn) => (
              <button
                key={btn.id}
                type="button"
                onClick={() => setPeriodTag(btn.id)}
                className={`rounded-lg px-2.5 py-1 text-xs font-medium transition ${
                  periodTag === btn.id
                    ? "bg-blue-600 text-white"
                    : "bg-slate-100 text-slate-700 hover:bg-slate-200"
                }`}
              >
                {btn.label}
              </button>
            ))}
          </div>
        </div>
        <div className="h-72 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={filteredDaily} margin={{ top: 10, right: 16, left: 8, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis
                dataKey="date"
                tick={{ fontSize: 11 }}
                minTickGap={28}
              />
              <YAxis
                tick={{ fontSize: 11 }}
                tickFormatter={(v) => `${Math.round(Number(v) / 1000)}k`}
              />
              <Tooltip
                formatter={(val: unknown) =>
                  val === null || val === undefined
                    ? ["not available", "Total Ridership"]
                    : [fmtInt(Number(val)), "Total Ridership"]
                }
                labelFormatter={(label, payload) => {
                  const row = payload?.[0]?.payload as NetworkDailyRow | undefined;
                  return row ? `${label} (${row.day_type})` : String(label);
                }}
              />
              <Area
                type="monotone"
                dataKey="ridership_plot"
                name="Total Network Riders"
                stroke="#2563eb"
                fill="#dbeafe"
                strokeWidth={1.8}
                connectNulls={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Hourly Profile by Day Type */}
      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-base font-semibold text-slate-900">
              Typical Network Hourly Profile by Day Type
            </h2>
            <p className="text-xs text-slate-500">
              Aggregated across {hourlyWindow === "jan_sep" ? "Jan–Sep 2026 typical normal days" : "Aug–Oct 2026 review window (90 typical days)"}.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <select
              aria-label="Hourly profile window"
              value={hourlyWindow}
              onChange={(e) => setHourlyWindow(e.target.value as "jan_sep" | "aug_oct")}
              className="rounded-lg border border-slate-300 bg-white px-2.5 py-1 text-xs font-medium text-slate-700"
            >
              <option value="jan_sep">Jan–Sep Typical Days</option>
              <option value="aug_oct">Aug–Oct Review Window</option>
            </select>
            <select
              aria-label="Hourly metric"
              value={hourlyMetric}
              onChange={(e) => setHourlyMetric(e.target.value as "ridership" | "rpt")}
              className="rounded-lg border border-slate-300 bg-white px-2.5 py-1 text-xs font-medium text-slate-700"
            >
              <option value="ridership">Mean Network Riders / Hour</option>
              <option value="rpt">Mean Riders per Trip</option>
            </select>
          </div>
        </div>
        <div className="h-72 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={hourlyByHour} margin={{ top: 10, right: 16, left: 8, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="hour" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip
                formatter={(val: unknown) =>
                  fmtNum(val as number | null, hourlyMetric === "rpt" ? 2 : 0)
                }
              />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Line
                type="monotone"
                dataKey="weekday"
                name="Typical Weekday"
                stroke="#1d4ed8"
                strokeWidth={2.2}
                dot={false}
              />
              <Line
                type="monotone"
                dataKey="saturday"
                name="Typical Saturday"
                stroke="#059669"
                strokeWidth={2}
                dot={false}
              />
              <Line
                type="monotone"
                dataKey="sunday"
                name="Typical Sunday"
                stroke="#d97706"
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Data Splits, Dropped Routes & Exclusions */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <h3 className="mb-3 text-sm font-semibold text-slate-900">
            Data Splits & Row Counts
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-slate-200 text-slate-500">
                <tr>
                  <th className="py-2 pr-3 font-medium">Split</th>
                  <th className="py-2 pr-3 font-medium">Dates</th>
                  <th className="py-2 pr-3 font-medium text-right">Rows</th>
                  <th className="py-2 font-medium text-right">Routes</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {ov.splits.map((s) => (
                  <tr key={s.set}>
                    <td className="py-2 pr-3 font-medium text-slate-900">{s.set}</td>
                    <td className="py-2 pr-3 text-slate-600">
                      {s.start_date} to {s.end_date}
                    </td>
                    <td className="py-2 pr-3 text-right font-mono">{fmtInt(s.rows)}</td>
                    <td className="py-2 text-right font-mono">{fmtInt(s.routes)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="mt-4 rounded-lg bg-slate-50 p-3 text-xs text-slate-600">
            <span className="font-semibold text-slate-800">Zero-ridership active rows kept:</span>{" "}
            {fmtInt(ov.cleaning.zero_ridership_rows_kept)} (
            {fmtSharePct(ov.cleaning.zero_ridership_share)}) with 0 null/negative/duplicate validation issues.
          </div>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <h3 className="mb-3 text-sm font-semibold text-slate-900">
            Dropped Routes & Telemetry Exclusions
          </h3>
          <div className="space-y-2 text-xs">
            {ov.cleaning.dropped_routes.map((d) => (
              <div key={d.route} className="rounded-lg border border-slate-100 bg-slate-50 p-2.5">
                <span className="font-semibold text-slate-900">{d.route}</span>:{" "}
                <span className="text-slate-600">{d.reason}</span>
              </div>
            ))}
          </div>
          <div className="mt-3 text-xs text-slate-600">
            <div className="font-semibold text-slate-800">Outage & Single-Day Exclusions:</div>
            <ul className="mt-1 list-disc space-y-1 pl-4">
              {ov.exclusions.excluded_outage_blocks.map((b) => (
                <li key={`${b.date}-${b.hours}`}>
                  {b.date} ({b.hours}): {b.reason}
                </li>
              ))}
              {ov.exclusions.outlier_route_hours.map((o) => (
                <li key={`${o.route}-${o.date}`}>
                  <button
                    type="button"
                    onClick={() => onSelectRoute(o.route)}
                    className="font-semibold text-blue-700 underline"
                  >
                    {o.route}
                  </button>{" "}
                  {o.date} ({o.hours}): {o.reason}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>

      {/* GTFS Snapshot Versions */}
      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <h3 className="mb-3 text-sm font-semibold text-slate-900">
          GTFS Timetable Snapshots ({ov.gtfs_versions.length} Jan–Sep archived versions + Oct 17 feed)
        </h3>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-slate-200 text-slate-500">
              <tr>
                <th className="py-2 pr-3 font-medium">Snapshot</th>
                <th className="py-2 pr-3 font-medium">Service Range</th>
                <th className="py-2 pr-3 font-medium text-right">Trips</th>
                <th className="py-2 pr-3 font-medium text-right">Stops</th>
                <th className="py-2 pr-3 font-medium">Used</th>
                <th className="py-2 font-medium">Notes</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {ov.gtfs_versions.map((g) => (
                <tr key={String(g.snapshot_date)}>
                  <td className="py-2 pr-3 font-mono font-semibold text-slate-900">
                    {String(g.snapshot_date)}
                  </td>
                  <td className="py-2 pr-3 text-slate-600">
                    {String(g.service_start)} to {String(g.service_end)}
                  </td>
                  <td className="py-2 pr-3 text-right font-mono">
                    {fmtInt(g.n_trips as number | null)}
                  </td>
                  <td className="py-2 pr-3 text-right font-mono">
                    {fmtInt(g.n_stops as number | null)}
                  </td>
                  <td className="py-2 pr-3">
                    <span
                      className={`inline-block rounded px-2 py-0.5 font-medium ${
                        g.use
                          ? "bg-emerald-50 text-emerald-700"
                          : "bg-slate-100 text-slate-600"
                      }`}
                    >
                      {g.use ? "Active" : "Skipped"}
                    </span>
                  </td>
                  <td className="py-2 text-slate-600">
                    {(g.reason as string) || "Validated and assigned to calendar dates"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

