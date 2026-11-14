import React, { useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, fmtInt, fmtNum, fmtSharePct, GtfsUploadResponse } from "../api";
import { PageHeader } from "./PageHeader";

export const GtfsUploadPage: React.FC = () => {
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<GtfsUploadResponse | null>(null);
  const [filterMode, setFilterMode] = useState<"all" | "study" | "schedule_only">("all");

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) {
      setError("Choose a .zip GTFS archive first.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await api.uploadGtfs(file);
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "GTFS upload validation failed");
      setResult(null);
    } finally {
      setLoading(false);
    }
  };

  const filteredRoutes = useMemo(() => {
    if (!result) return [];
    if (filterMode === "study") return result.routes.filter((r) => r.has_ridership_history);
    if (filterMode === "schedule_only")
      return result.routes.filter((r) => !r.has_ridership_history);
    return result.routes;
  }, [result, filterMode]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="GTFS Feed Upload & Safe Schedule Inspector"
        subtitle="Upload any GTFS .zip feed (up to 50 MB compressed / 300 MB uncompressed). Safely extracts to an isolated temporary directory with Zip Slip prevention, runs Milestone 1 integrity, schedule & overlap checks, and matches against the 41 Manhattan study routes."
        period={result?.period ?? "On-demand uploaded GTFS archive"}
        source={result?.source ?? "POST /api/gtfs/upload (Milestone 1 integrity, profile & overlap checks)"}
      />

      {/* Upload Box */}
      <form
        onSubmit={handleUpload}
        className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
      >
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end">
          <div className="flex-1">
            <label htmlFor="gtfs-file-input" className="block text-xs font-semibold text-slate-800">
              GTFS Archive (.zip, max 50 MB upload / 300 MB unzipped)
            </label>
            <input
              id="gtfs-file-input"
              type="file"
              accept=".zip"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="mt-2 block w-full text-xs text-slate-600 file:mr-4 file:rounded-lg file:border-0 file:bg-blue-50 file:px-4 file:py-2 file:text-xs file:font-semibold file:text-blue-700 hover:file:bg-blue-100"
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="rounded-lg bg-slate-900 px-5 py-2.5 text-xs font-semibold text-white hover:bg-slate-800 disabled:opacity-50"
          >
            {loading ? "Inspecting Feed..." : "Inspect GTFS Archive"}
          </button>
        </div>
        <p className="mt-3 text-xs text-slate-500">
          Routes outside the 41 Manhattan study set are clearly flagged as{" "}
          <span className="font-semibold text-slate-700">
            &quot;no ridership history, schedule analysis only&quot;
          </span>{" "}
          and never invent ridership numbers.
        </p>
        {loading ? (
          <div className="mt-3 rounded-lg border border-blue-200 bg-blue-50 p-3 text-xs text-blue-900">
            Inspecting GTFS archive... Full city feeds (~8 MB / ~1.2M stop times) typically take
            10–30 seconds to check referential integrity, service schedules, and stop overlaps.
          </div>
        ) : null}
        {error ? (
          <div className="mt-3 rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-700">
            {error}
          </div>
        ) : null}
      </form>

      {result ? (
        <div className="space-y-6">
          {/* Integrity Summary */}
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="text-[11px] font-medium uppercase text-slate-500">
                Referential Integrity
              </div>
              <div
                className={`mt-1 text-lg font-bold ${
                  result.integrity.referential_integrity_passed
                    ? "text-emerald-700"
                    : "text-rose-700"
                }`}
              >
                {result.integrity.referential_integrity_passed ? "PASSED" : "FAILED"}
              </div>
              <div className="text-[11px] text-slate-500">
                Missing r/t/s:{" "}
                {fmtInt(result.integrity.trips_missing_routes as number)}/
                {fmtInt(result.integrity.st_missing_trips as number)}/
                {fmtInt(result.integrity.st_missing_stops as number)}
              </div>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="text-[11px] font-medium uppercase text-slate-500">
                Routes & Trips
              </div>
              <div className="mt-1 text-lg font-bold text-slate-900">
                {fmtInt(result.summary.routes_in_feed)} routes
              </div>
              <div className="text-[11px] text-slate-500">
                {fmtInt(result.integrity.n_trips as number)} total trips
              </div>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="text-[11px] font-medium uppercase text-slate-500">
                Manhattan History Match
              </div>
              <div className="mt-1 text-lg font-bold text-slate-900">
                {result.summary.study_routes_matched} matched /{" "}
                {result.summary.non_study_routes_schedule_only} schedule-only
              </div>
              <div className="text-[11px] text-slate-500">Against 41 study routes</div>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="text-[11px] font-medium uppercase text-slate-500">
                Spillover Times (&gt;=24:00)
              </div>
              <div className="mt-1 text-lg font-bold text-slate-900">
                {fmtInt(result.integrity.times_ge_24h as number)}
              </div>
              <div className="text-[11px] text-slate-500">
                Max hour: {fmtInt(result.integrity.max_hour_encoded as number)}h
              </div>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="text-[11px] font-medium uppercase text-slate-500">
                Overlapping Pairs
              </div>
              <div className="mt-1 text-lg font-bold text-slate-900">
                {fmtInt(result.summary.overlapping_pairs_total)}
              </div>
              <div className="text-[11px] text-slate-500">
                Rep date: {result.summary.representative_weekday_date}
              </div>
            </div>
          </div>

          {/* Hourly Schedule Histogram */}
          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <h2 className="mb-3 text-sm font-semibold text-slate-900">
              Representative Weekday Hourly Scheduled Trips ({result.filename})
            </h2>
            <div className="h-60 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={result.network_hourly_schedule}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="hour" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Bar dataKey="trips_running" name="Trips Running" fill="#2563eb" radius={[3, 3, 0, 0]} isAnimationActive={false} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Routes Table */}
          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <h3 className="text-sm font-semibold text-slate-900">
                Uploaded Feed Route Analysis ({filteredRoutes.length} routes shown)
              </h3>
              <div className="flex gap-1.5">
                {[
                  { id: "all", label: "All Routes" },
                  { id: "study", label: "Study Matched (Manhattan)" },
                  { id: "schedule_only", label: "Schedule Analysis Only" },
                ].map((f) => (
                  <button
                    key={f.id}
                    type="button"
                    onClick={() => setFilterMode(f.id as "all" | "study" | "schedule_only")}
                    className={`rounded-md px-2.5 py-1 text-xs font-medium ${
                      filterMode === f.id
                        ? "bg-slate-900 text-white"
                        : "bg-slate-100 text-slate-700"
                    }`}
                  >
                    {f.label}
                  </button>
                ))}
              </div>
            </div>
            <div className="max-h-96 overflow-auto">
              <table className="w-full text-left text-xs">
                <thead className="sticky top-0 bg-slate-50 border-b border-slate-200 text-slate-600">
                  <tr>
                    <th className="py-2 pr-3 font-medium">Route</th>
                    <th className="py-2 pr-3 text-right font-medium">Wk/Sat/Sun Trips</th>
                    <th className="py-2 pr-3 text-right font-medium">Stops (Excl%)</th>
                    <th className="py-2 pr-3 text-right font-medium">Length / Speed</th>
                    <th className="py-2 pr-3 text-right font-medium">Study Avg Riders</th>
                    <th className="py-2 font-medium">History Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {filteredRoutes.map((r) => (
                    <tr key={r.route_id}>
                      <td className="py-2 pr-3">
                        <span className="font-bold text-slate-900">{r.route_id}</span>{" "}
                        <span className="text-slate-500">{r.route_long_name}</span>
                      </td>
                      <td className="py-2 pr-3 text-right font-mono">
                        {fmtInt(r.trips_per_weekday)} / {fmtInt(r.trips_per_saturday)} /{" "}
                        {fmtInt(r.trips_per_sunday)}
                      </td>
                      <td className="py-2 pr-3 text-right font-mono">
                        {fmtInt(r.stop_count)} ({fmtSharePct(r.exclusive_stop_share)})
                      </td>
                      <td className="py-2 pr-3 text-right font-mono">
                        {fmtNum(r.route_length_km, 2)} km / {fmtNum(r.avg_scheduled_speed_kmh, 1)} km/h
                      </td>
                      <td className="py-2 pr-3 text-right font-mono">
                        {fmtInt(r.study_avg_daily_riders)}
                      </td>
                      <td className="py-2">
                        <span
                          className={`rounded px-2 py-0.5 text-[11px] font-medium ${
                            r.has_ridership_history
                              ? "bg-emerald-50 text-emerald-700"
                              : "bg-slate-100 text-slate-700"
                          }`}
                        >
                          {r.status_note}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
};

