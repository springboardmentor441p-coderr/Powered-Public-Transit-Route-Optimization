import { useEffect, useState } from "react";
import { Search } from "lucide-react";
import { apiClient } from "../api/client";
import {
  Badge,
  EmptyState,
  ErrorState,
  LoadingState,
  PaginationBar,
  SectionCard,
  formatInt,
  formatNum,
} from "../components/ui";
import type { RouteDetailResponse, RouteExplanationResponse, RouteListResponse } from "../types/api";

export function RoutesPage({
  initialRouteId,
  onOpenRidership,
}: {
  initialRouteId?: string | null;
  onOpenRidership: (routeId: string) => void;
}) {
  const [mode, setMode] = useState<string>("");
  const [search, setSearch] = useState<string>("");
  const [offset, setOffset] = useState(0);
  const [listData, setListData] = useState<RouteListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [selectedId, setSelectedId] = useState<string>(initialRouteId ?? "151");
  const [detail, setDetail] = useState<RouteDetailResponse | null>(null);
  const [explanation, setExplanation] = useState<RouteExplanationResponse | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);

  useEffect(() => {
    if (initialRouteId) setSelectedId(initialRouteId);
  }, [initialRouteId]);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    apiClient
      .getRoutes(
        {
          mode: mode || undefined,
          search: search.trim() || undefined,
          limit: 15,
          offset,
        },
        controller.signal
      )
      .then(setListData)
      .catch((err: unknown) => {
        if (err instanceof DOMException && err.name === "AbortError") return;
        setError(err instanceof Error ? err.message : "Failed to load routes.");
      })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, [mode, search, offset]);

  useEffect(() => {
    if (!selectedId) return;
    const controller = new AbortController();
    setDetailLoading(true);
    setDetailError(null);
    Promise.all([
      apiClient.getRouteDetail(selectedId, controller.signal),
      apiClient.getRouteExplanation(selectedId, undefined, controller.signal).catch(() => null),
    ])
      .then(([d, exp]) => {
        setDetail(d);
        setExplanation(exp);
      })
      .catch((err: unknown) => {
        if (err instanceof DOMException && err.name === "AbortError") return;
        setDetailError(err instanceof Error ? err.message : "Failed to load route details.");
      })
      .finally(() => setDetailLoading(false));
    return () => controller.abort();
  }, [selectedId]);

  return (
    <div className="grid grid-cols-1 gap-6 xl:grid-cols-12">
      <div className="xl:col-span-7">
        <SectionCard
          title="Route Explorer"
          subtitle="Search and filter across 125 CTA bus routes and 8 rail lines"
          actions={
            <div className="flex flex-wrap items-center gap-2">
              <div className="relative">
                <Search className="pointer-events-none absolute left-2.5 top-2 h-3.5 w-3.5 text-slate-400" />
                <input
                  type="text"
                  value={search}
                  onChange={(e) => {
                    setSearch(e.target.value);
                    setOffset(0);
                  }}
                  placeholder="Search route ID or name..."
                  aria-label="Search routes"
                  className="rounded-lg border border-slate-700 bg-slate-950 py-1.5 pl-8 pr-3 text-xs text-slate-100 placeholder:text-slate-500 focus:border-sky-400 focus:outline-none"
                />
              </div>
              <select
                value={mode}
                onChange={(e) => {
                  setMode(e.target.value);
                  setOffset(0);
                }}
                aria-label="Filter by mode"
                className="rounded-lg border border-slate-700 bg-slate-950 px-2.5 py-1.5 text-xs text-slate-100 focus:border-sky-400 focus:outline-none"
              >
                <option value="">All Modes</option>
                <option value="bus">Bus</option>
                <option value="rail">Rail</option>
              </select>
            </div>
          }
        >
          {loading ? (
            <LoadingState label="Loading routes..." />
          ) : error ? (
            <ErrorState message={error} />
          ) : !listData || listData.data.length === 0 ? (
            <EmptyState title="No routes found" description="Clear the search filter or switch mode." />
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="border-b border-slate-800 text-slate-400">
                    <tr>
                      <th className="py-2 pr-3 font-medium">Route</th>
                      <th className="py-2 pr-3 font-medium">Name</th>
                      <th className="py-2 pr-3 font-medium">Mode</th>
                      <th className="py-2 pr-3 font-medium text-right">Trips</th>
                      <th className="py-2 font-medium text-right">Span (h)</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/70">
                    {listData.data.map((r) => {
                      const active = r.route_id === selectedId;
                      return (
                        <tr
                          key={r.route_id}
                          onClick={() => setSelectedId(r.route_id)}
                          className={`cursor-pointer transition-colors ${
                            active ? "bg-sky-500/15" : "hover:bg-slate-800/50"
                          }`}
                        >
                          <td className="py-2.5 pr-3 font-semibold text-sky-300">{r.route_id}</td>
                          <td className="py-2.5 pr-3 text-slate-200">{r.route_long_name}</td>
                          <td className="py-2.5 pr-3">
                            <Badge variant={r.is_rail ? "violet" : "sky"}>
                              {r.is_rail ? "Rail" : "Bus"}
                            </Badge>
                          </td>
                          <td className="py-2.5 pr-3 text-right text-slate-300">{formatInt(r.scheduled_trips)}</td>
                          <td className="py-2.5 text-right text-slate-300">{formatNum(r.service_span_hours, 1)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              <PaginationBar pagination={listData.pagination} onPageChange={setOffset} />
            </>
          )}
        </SectionCard>
      </div>

      <div className="xl:col-span-5">
        <SectionCard
          title={detail ? `Route ${detail.route_id} Profile` : "Route Details"}
          subtitle={detail ? detail.route_long_name : "Select a route to inspect metrics"}
          actions={
            detail && !detail.is_rail ? (
              <button
                type="button"
                onClick={() => onOpenRidership(detail.route_id)}
                className="rounded-lg border border-emerald-500/40 bg-emerald-950/40 px-3 py-1 text-xs font-medium text-emerald-300 hover:bg-emerald-900/60"
              >
                View Ridership
              </button>
            ) : undefined
          }
        >
          {detailLoading ? (
            <LoadingState label="Loading route profile..." />
          ) : detailError ? (
            <ErrorState message={detailError} />
          ) : !detail ? (
            <EmptyState />
          ) : (
            <div className="space-y-4 text-xs">
              <div className="flex flex-wrap gap-2">
                <Badge variant={detail.is_rail ? "violet" : "sky"}>
                  {detail.is_rail ? "CTA Rail" : "CTA Bus"}
                </Badge>
                {detail.operational.operational_cluster_label && (
                  <Badge variant="slate">{detail.operational.operational_cluster_label}</Badge>
                )}
                {detail.regional_partition && <Badge variant="amber">{detail.regional_partition}</Badge>}
              </div>

              <div className="grid grid-cols-2 gap-3 rounded-lg border border-slate-800 bg-slate-950/60 p-3">
                <div>
                  <p className="text-slate-400">Scheduled Trips</p>
                  <p className="font-semibold text-slate-100">{formatInt(detail.operational.scheduled_trips)}</p>
                </div>
                <div>
                  <p className="text-slate-400">Route Length</p>
                  <p className="font-semibold text-slate-100">{formatNum(detail.operational.route_length_km)} km</p>
                </div>
                <div>
                  <p className="text-slate-400">AM Headway</p>
                  <p className="font-semibold text-slate-100">
                    {detail.operational.am_headway_min !== null ? `${formatNum(detail.operational.am_headway_min, 1)} min` : "Missing / N/A"}
                  </p>
                </div>
                <div>
                  <p className="text-slate-400">Unique Stops</p>
                  <p className="font-semibold text-slate-100">{formatInt(detail.operational.unique_stops_count)}</p>
                </div>
                <div>
                  <p className="text-slate-400">Mean Daily Rides</p>
                  <p className="font-semibold text-slate-100">
                    {detail.demand.demand_metrics_available
                      ? formatInt(detail.demand.historical_mean_daily_rides)
                      : "Unavailable (Rail)"}
                  </p>
                </div>
                <div>
                  <p className="text-slate-400">Hub Stop Count</p>
                  <p className="font-semibold text-slate-100">{formatInt(detail.hubs.hub_stop_count)}</p>
                </div>
              </div>

              {explanation && (
                <div className="space-y-2 rounded-lg border border-slate-800 bg-slate-950/60 p-3">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-slate-200">
                      Ranking: #{explanation.rank} of {explanation.total_routes} ({explanation.track})
                    </span>
                    <Badge variant="emerald">Score {formatNum(explanation.overall_score, 4)}</Badge>
                  </div>
                  <p className="leading-relaxed text-slate-300">{explanation.narrative}</p>
                </div>
              )}
            </div>
          )}
        </SectionCard>
      </div>
    </div>
  );
}
