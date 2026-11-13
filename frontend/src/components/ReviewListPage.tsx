import React, { useMemo, useState } from "react";
import {
  fmtNum,
  fmtPct,
  fmtSharePct,
  formatReviewCategory,
  formatTimeBandLabel,
  ReviewCell,
} from "../api";
import { PageHeader } from "./PageHeader";

interface ReviewListPageProps {
  cells: ReviewCell[];
  period: string;
  source: string;
  onSelectRoute: (route: string) => void;
  onOpenScenario: (route: string, dayGroup: string, timeBand: string) => void;
}

export const ReviewListPage: React.FC<ReviewListPageProps> = ({
  cells,
  period,
  source,
  onSelectRoute,
  onOpenScenario,
}) => {
  const [dayGroup, setDayGroup] = useState<string>("all");
  const [category, setCategory] = useState<string>("all");
  const [timeBand, setTimeBand] = useState<string>("all");
  const [search, setSearch] = useState<string>("");
  const [sortBy, setSortBy] = useState<
    "high_demand_freq_pct" | "obs_riders_per_service_hour" | "exclusive_stop_share"
  >("high_demand_freq_pct");
  const [sortDir, setSortDir] = useState<"desc" | "asc">("desc");

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    const list = cells.filter((c) => {
      if (dayGroup !== "all" && c.day_group !== dayGroup) return false;
      if (category !== "all" && c.review_category !== category) return false;
      if (timeBand !== "all" && c.time_band !== timeBand) return false;
      if (
        q &&
        !c.route.toLowerCase().includes(q) &&
        !c.route_long_name.toLowerCase().includes(q)
      ) {
        return false;
      }
      return true;
    });
    return [...list].sort((a, b) => {
      const av = a[sortBy] ?? 0;
      const bv = b[sortBy] ?? 0;
      return sortDir === "desc" ? bv - av : av - bv;
    });
  }, [cells, dayGroup, category, timeBand, search, sortBy, sortDir]);

  const counts = useMemo(() => {
    const more = cells.filter((c) => c.review_category === "more_trips_candidate").length;
    const fewer = cells.filter((c) => c.review_category === "fewer_trips_candidate").length;
    const ok = cells.length - more - fewer;
    return { more, fewer, ok };
  }, [cells]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Aug–Oct 2026 Service Review List (400 Route × Day-Group × Time-Band Cells)"
        subtitle="Built strictly from 90 observed typical days (63 weekdays + 27 weekend days) after logging the final Aug–Sep test run. Candidates require >= 20 active days and >= 2.0 trips/day."
        period={period}
        source={source}
      />

      {/* Category Summary Chips */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <button
          type="button"
          onClick={() => setCategory(category === "more_trips_candidate" ? "all" : "more_trips_candidate")}
          className={`rounded-xl border p-4 text-left shadow-sm transition ${
            category === "more_trips_candidate"
              ? "border-amber-500 bg-amber-50"
              : "border-slate-200 bg-white hover:bg-slate-50"
          }`}
        >
          <div className="text-xs font-medium uppercase text-amber-800">
            More Trips Review Candidates
          </div>
          <div className="mt-1 text-2xl font-bold text-slate-900">{counts.more}</div>
          <div className="mt-0.5 text-xs text-slate-600">
            &gt;= 40 riders/svc-hr & &gt;= 65% hours above fixed p75
          </div>
        </button>

        <button
          type="button"
          onClick={() => setCategory(category === "fewer_trips_candidate" ? "all" : "fewer_trips_candidate")}
          className={`rounded-xl border p-4 text-left shadow-sm transition ${
            category === "fewer_trips_candidate"
              ? "border-blue-500 bg-blue-50"
              : "border-slate-200 bg-white hover:bg-slate-50"
          }`}
        >
          <div className="text-xs font-medium uppercase text-blue-800">
            Fewer Trips Review Candidates
          </div>
          <div className="mt-1 text-2xl font-bold text-slate-900">{counts.fewer}</div>
          <div className="mt-0.5 text-xs text-slate-600">
            &lt;= 22 riders/svc-hr & &lt;= 15% hours above fixed p75
          </div>
        </button>

        <button
          type="button"
          onClick={() => setCategory("all")}
          className="rounded-xl border border-slate-200 bg-white p-4 text-left shadow-sm hover:bg-slate-50"
        >
          <div className="text-xs font-medium uppercase text-slate-500">
            Within Normal Threshold
          </div>
          <div className="mt-1 text-2xl font-bold text-slate-900">{counts.ok}</div>
          <div className="mt-0.5 text-xs text-slate-600">
            Click to show all {cells.length} active route cells
          </div>
        </button>
      </div>

      {/* Filters & Sort */}
      <div className="flex flex-wrap items-center gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Filter by route (e.g. M15+)..."
          className="w-48 rounded-lg border border-slate-300 px-3 py-1.5 text-xs text-slate-900"
        />
        <select
          aria-label="Day group filter"
          value={dayGroup}
          onChange={(e) => setDayGroup(e.target.value)}
          className="rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-xs text-slate-700"
        >
          <option value="all">All Day Groups</option>
          <option value="weekday">Weekday (63d)</option>
          <option value="weekend">Weekend (27d)</option>
        </select>
        <select
          aria-label="Category filter"
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          className="rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-xs text-slate-700"
        >
          <option value="all">All Categories</option>
          <option value="more_trips_candidate">More Trips Review</option>
          <option value="fewer_trips_candidate">Fewer Trips Review</option>
          <option value="within_threshold">Within Threshold</option>
        </select>
        <select
          aria-label="Time band filter"
          value={timeBand}
          onChange={(e) => setTimeBand(e.target.value)}
          className="rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-xs text-slate-700"
        >
          <option value="all">All Time Bands</option>
          <option value="early_morning">Early Morning</option>
          <option value="morning_peak">Morning Peak</option>
          <option value="midday">Midday</option>
          <option value="evening_peak">Evening Peak</option>
          <option value="night">Night</option>
        </select>
        <div className="ml-auto flex items-center gap-2 text-xs">
          <span className="text-slate-500">Sort:</span>
          <select
            aria-label="Sort review list"
            value={sortBy}
            onChange={(e) =>
              setSortBy(
                e.target.value as
                  | "high_demand_freq_pct"
                  | "obs_riders_per_service_hour"
                  | "exclusive_stop_share"
              )
            }
            className="rounded-lg border border-slate-300 bg-white px-2 py-1 text-xs text-slate-700"
          >
            <option value="high_demand_freq_pct">High Riders/Trip Hours %</option>
            <option value="obs_riders_per_service_hour">Riders / Service-Hour</option>
            <option value="exclusive_stop_share">Exclusive Stop Share</option>
          </select>
          <button
            type="button"
            onClick={() => setSortDir((d) => (d === "desc" ? "asc" : "desc"))}
            className="rounded-lg border border-slate-300 bg-slate-50 px-2.5 py-1 text-xs font-medium text-slate-700"
          >
            {sortDir === "desc" ? "Desc" : "Asc"}
          </button>
          <span className="font-mono text-slate-500">{filtered.length} rows</span>
        </div>
      </div>

      {/* Table */}
      <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="max-h-[32rem] overflow-auto">
          <table className="w-full text-left text-xs">
            <thead className="sticky top-0 bg-slate-50 border-b border-slate-200 text-slate-600">
              <tr>
                <th className="p-3 font-medium">Route</th>
                <th className="p-3 font-medium">Day Group · Band</th>
                <th className="p-3 text-right font-medium">Days</th>
                <th className="p-3 text-right font-medium">Riders/Trip</th>
                <th className="p-3 text-right font-medium">Riders/Svc-Hr</th>
                <th className="p-3 text-right font-medium">High-Demand Hrs %</th>
                <th className="p-3 text-right font-medium">Excl Stops</th>
                <th className="p-3 font-medium">Category & Action</th>
                <th className="p-3 text-right font-medium">Scenario</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filtered.map((c) => (
                <tr
                  key={`${c.route}-${c.day_group}-${c.time_band}`}
                  className="hover:bg-slate-50"
                >
                  <td className="p-3">
                    <button
                      type="button"
                      onClick={() => onSelectRoute(c.route)}
                      className="font-semibold text-blue-700 hover:underline"
                    >
                      {c.route}
                    </button>
                    <div className="text-[11px] text-slate-500">Group {c.group_id}</div>
                  </td>
                  <td className="p-3">
                    <div className="font-medium text-slate-900">{c.day_group}</div>
                    <div className="text-[11px] text-slate-500">
                      {formatTimeBandLabel(c.time_band)}
                    </div>
                  </td>
                  <td className="p-3 text-right font-mono">{c.days_count}</td>
                  <td className="p-3 text-right font-mono">
                    {fmtNum(c.obs_riders_per_trip, 1)}
                  </td>
                  <td className="p-3 text-right font-mono font-semibold">
                    {fmtNum(c.obs_riders_per_service_hour, 1)}
                  </td>
                  <td className="p-3 text-right font-mono">
                    {fmtPct(c.high_demand_freq_pct, 1)}
                  </td>
                  <td className="p-3 text-right font-mono">
                    {fmtSharePct(c.exclusive_stop_share)}
                  </td>
                  <td className="p-3 max-w-xs">
                    <span
                      className={`inline-block rounded px-2 py-0.5 text-[11px] font-medium ${
                        c.review_category === "more_trips_candidate"
                          ? "bg-amber-100 text-amber-900"
                          : c.review_category === "fewer_trips_candidate"
                          ? "bg-blue-100 text-blue-900"
                          : "bg-slate-100 text-slate-700"
                      }`}
                    >
                      {formatReviewCategory(c.review_category)}
                    </span>
                    <div className="mt-1 text-[11px] text-slate-600">{c.recommended_action}</div>
                  </td>
                  <td className="p-3 text-right">
                    <button
                      type="button"
                      onClick={() => onOpenScenario(c.route, c.day_group, c.time_band)}
                      className="rounded-lg bg-slate-900 px-2.5 py-1 text-[11px] font-medium text-white hover:bg-slate-700"
                    >
                      Simulate
                    </button>
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

