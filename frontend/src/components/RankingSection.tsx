import React, { useEffect, useState } from "react";
import {
  api,
  DAY_TYPES,
  fmtInt,
  fmtNum,
  fmtSharePct,
  HistoryQuery,
  NOT_AVAILABLE,
  RankingData,
  RankingRow,
} from "../api";

interface RankingSectionProps {
  query: HistoryQuery;
  groupOptions: Array<{ id: number; label: string }>;
  onSelectRoute: (route: string) => void;
}

function formatIndicator(indicator: string, row: RankingRow): string {
  switch (indicator) {
    case "riders_per_service_hour":
      return fmtNum(row.riders_per_service_hour, 1);
    case "riders_per_trip":
      return fmtNum(row.riders_per_trip, 1);
    case "share_hours_above_p75":
      return fmtSharePct(row.share_hours_above_p75, 1);
    case "mean_daily_boardings":
      return fmtInt(row.mean_daily_boardings);
    default:
      return NOT_AVAILABLE;
  }
}

export const RankingSection: React.FC<RankingSectionProps> = ({ query, groupOptions, onSelectRoute }) => {
  const [indicator, setIndicator] = useState("riders_per_service_hour");
  const [direction, setDirection] = useState<"asc" | "desc">("desc");
  const [dayType, setDayType] = useState<string>(query.dayType !== "all" ? query.dayType : "Typical Weekday");
  const [minDays, setMinDays] = useState<number | "">("");
  const [groupId, setGroupId] = useState<number | null>(null);
  const [data, setData] = useState<RankingData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showAll, setShowAll] = useState(false);

  useEffect(() => {
    if (query.dayType !== "all") setDayType(query.dayType);
  }, [query.dayType]);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    api
      .getRankings({
        indicator,
        direction,
        day_type: dayType,
        min_days: minDays === "" ? undefined : minDays,
        group_id: groupId,
        ctx: query,
      })
      .then((d) => {
        if (cancelled) return;
        setData(d);
        if (minDays === "") setMinDays(d.resolved_config.min_observed_days);
      })
      .catch((e) => !cancelled && setError(e instanceof Error ? e.message : "Could not load the ranking."));
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [indicator, direction, dayType, minDays, groupId, query.start, query.end, query.replayId, query.revealedThrough]);

  const def = data?.indicators[indicator];
  const rows = data ? (showAll ? data.rows : data.rows.slice(0, 15)) : [];
  const fieldCls = "rounded-md border border-slate-300 bg-white px-2 py-1 text-xs text-slate-900";

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm" data-testid="ranking-section">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="text-base font-bold text-slate-900">Route ranking</h2>
          <p className="text-xs text-slate-600">
            One named measure at a time, compared within one day type. Routes that miss the data rules stay in the list
            without a rank.
          </p>
        </div>
        <span className="text-[11px] text-slate-500">{data?.period}</span>
      </div>

      <div className="mt-4 flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-0.5 text-[11px] font-semibold text-slate-500">
          Measure
          <select
            aria-label="Ranking measure"
            value={indicator}
            onChange={(e) => {
              setIndicator(e.target.value);
              const d = data?.indicators[e.target.value]?.default_direction;
              if (d) setDirection(d);
            }}
            className={fieldCls}
          >
            {Object.entries(data?.indicators ?? { riders_per_service_hour: { label: "Boardings per scheduled service hour" } }).map(
              ([k, v]) => (
                <option key={k} value={k}>
                  {(v as { label: string }).label}
                </option>
              )
            )}
          </select>
        </label>
        <label className="flex flex-col gap-0.5 text-[11px] font-semibold text-slate-500">
          Order
          <select
            aria-label="Ranking order"
            value={direction}
            onChange={(e) => setDirection(e.target.value as "asc" | "desc")}
            className={fieldCls}
          >
            <option value="desc">Highest first</option>
            <option value="asc">Lowest first</option>
          </select>
        </label>
        <label className="flex flex-col gap-0.5 text-[11px] font-semibold text-slate-500">
          Day type
          <select aria-label="Ranking day type" value={dayType} onChange={(e) => setDayType(e.target.value)} className={fieldCls}>
            {DAY_TYPES.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-0.5 text-[11px] font-semibold text-slate-500">
          Minimum observed days
          <input
            type="number"
            aria-label="Minimum observed days"
            min={1}
            max={90}
            value={minDays}
            onChange={(e) => setMinDays(e.target.value === "" ? "" : Math.max(1, Number(e.target.value)))}
            className={`${fieldCls} w-24`}
          />
        </label>
        <label className="flex flex-col gap-0.5 text-[11px] font-semibold text-slate-500">
          Compare within
          <select
            aria-label="Peer group"
            value={groupId === null ? "" : String(groupId)}
            onChange={(e) => setGroupId(e.target.value === "" ? null : Number(e.target.value))}
            className={fieldCls}
          >
            <option value="">All 41 routes</option>
            {groupOptions.map((g) => (
              <option key={g.id} value={g.id}>
                {g.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      {error ? <div className="mt-3 rounded-md bg-red-50 p-3 text-xs text-red-800">{error}</div> : null}

      {data && def ? (
        <div className="mt-4 grid gap-4 lg:grid-cols-3">
          <div className="lg:col-span-2">
            <div className="max-h-[28rem] overflow-auto rounded-lg border border-slate-200">
              <table className="min-w-full text-left text-xs" data-testid="ranking-table">
                <thead className="sticky top-0 bg-slate-50 text-[11px] uppercase text-slate-500">
                  <tr>
                    <th className="px-2 py-1.5">Rank</th>
                    <th className="px-2 py-1.5">Route</th>
                    <th className="px-2 py-1.5">{def.label}</th>
                    <th className="px-2 py-1.5">Days</th>
                    <th className="px-2 py-1.5">Avg daily boardings</th>
                    <th className="px-2 py-1.5">Total boardings</th>
                    <th className="px-2 py-1.5">Service hours</th>
                    <th className="px-2 py-1.5">Note</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {rows.map((r) => (
                    <tr key={r.route} className={r.eligible ? "" : "bg-slate-50 text-slate-500"}>
                      <td className="px-2 py-1.5 font-bold">{r.rank ?? "Unranked"}</td>
                      <td className="px-2 py-1.5">
                        <button type="button" onClick={() => onSelectRoute(r.route)} className="font-semibold text-blue-700 hover:underline">
                          {r.route}
                        </button>
                        <div className="text-[10px] text-slate-500">{r.route_long_name}</div>
                      </td>
                      <td className="px-2 py-1.5 font-semibold">{formatIndicator(indicator, r)}</td>
                      <td className="px-2 py-1.5">{fmtInt(r.observed_days)}</td>
                      <td className="px-2 py-1.5">{fmtInt(r.mean_daily_boardings)}</td>
                      <td className="px-2 py-1.5">{fmtInt(r.total_boardings)}</td>
                      <td className="px-2 py-1.5">{fmtNum(r.total_service_hours, 0)}</td>
                      <td className="px-2 py-1.5 text-[11px]">{r.ineligible_reason ?? ""}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {data.rows.length > 15 ? (
              <button type="button" onClick={() => setShowAll(!showAll)} className="mt-2 text-xs font-semibold text-blue-700 hover:underline">
                {showAll ? "Show top 15" : `Show all ${data.rows.length} routes`}
              </button>
            ) : null}
          </div>

          <div className="space-y-3 text-xs">
            <div className="rounded-lg border border-slate-200 p-3">
              <div className="font-semibold text-slate-900">How this is worked out</div>
              <dl className="mt-2 space-y-1.5">
                <div>
                  <dt className="text-slate-500">Top of the fraction</dt>
                  <dd>{def.numerator}</dd>
                </div>
                <div>
                  <dt className="text-slate-500">Bottom of the fraction</dt>
                  <dd>{def.denominator}</dd>
                </div>
                <div>
                  <dt className="text-slate-500">What a high value means</dt>
                  <dd>{def.meaning}</dd>
                </div>
                <div>
                  <dt className="text-slate-500">Rules to be ranked</dt>
                  <dd>
                    At least {data.resolved_config.min_observed_days} observed {dayType.replace("Typical ", "").toLowerCase()}s
                    and {data.resolved_config.min_avg_trips_running_per_day} or more trips running per day on average.{" "}
                    {data.resolved_config.ties}
                  </dd>
                </div>
              </dl>
              <p className="mt-2 text-[11px] text-slate-500">
                {data.eligible_count} of {data.count} routes ranked · config {data.resolved_config.config_version}
              </p>
            </div>
            <div className="rounded-lg border border-slate-200 p-3" data-testid="ranking-sensitivity">
              <div className="font-semibold text-slate-900">Does the minimum-days rule change the result?</div>
              <table className="mt-2 w-full text-left text-[11px]">
                <thead className="text-slate-500">
                  <tr>
                    <th className="py-0.5">Min days</th>
                    <th className="py-0.5">Ranked</th>
                    <th className="py-0.5">Top 5</th>
                  </tr>
                </thead>
                <tbody>
                  {data.sensitivity.map((s) => (
                    <tr key={s.min_days} className={s.min_days === data.resolved_config.min_observed_days ? "font-semibold text-slate-900" : ""}>
                      <td className="py-0.5">{s.min_days}</td>
                      <td className="py-0.5">{s.eligible_routes}</td>
                      <td className="py-0.5">{s.top_5.length ? s.top_5.join(", ") : "none ranked"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="mt-2 text-[11px] leading-snug text-slate-500">{data.resolved_config.min_observed_days_reason}</p>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
};
