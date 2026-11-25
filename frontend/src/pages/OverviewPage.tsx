import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { apiClient } from "../api/client";
import {
  ErrorState,
  KpiCard,
  LoadingState,
  MethodNote,
  SectionCard,
  formatInt,
  formatNum,
} from "../components/ui";
import type {
  ClusterSummaryResponse,
  CorridorClusterListResponse,
  RankingListResponse,
  RidershipTimeseriesResponse,
  RouteListResponse,
} from "../types/api";

interface OverviewData {
  routes: RouteListResponse;
  busTop: RankingListResponse;
  railTop: RankingListResponse;
  clusters: ClusterSummaryResponse;
  corridors: CorridorClusterListResponse;
  sampleRidership: RidershipTimeseriesResponse;
}

export function OverviewPage({
  onSelectRoute,
  onRetrySuccess,
}: {
  onSelectRoute: (routeId: string) => void;
  onRetrySuccess?: () => void;
}) {
  const [data, setData] = useState<OverviewData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);

    Promise.all([
      apiClient.getRoutes({ limit: 1 }, controller.signal),
      apiClient.getBusRankings({ limit: 10, offset: 0 }, controller.signal),
      apiClient.getRailRankings(undefined, controller.signal),
      apiClient.getSpatialClustersSummary(controller.signal),
      apiClient.getCorridorClusters({ limit: 1 }, controller.signal),
      apiClient.getRidershipTimeseries("151", { granularity: "monthly", limit: 36 }, controller.signal),
    ])
      .then(([routes, busTop, railTop, clusters, corridors, sampleRidership]) => {
        setData({ routes, busTop, railTop, clusters, corridors, sampleRidership });
        if (reloadKey > 0) {
          onRetrySuccess?.();
        }
      })
      .catch((err: unknown) => {
        if (err instanceof DOMException && err.name === "AbortError") return;
        setError(err instanceof Error ? err.message : "Failed to load overview metrics.");
      })
      .finally(() => setLoading(false));

    return () => controller.abort();
  }, [reloadKey]);

  if (loading) return <LoadingState label="Loading system overview from backend APIs..." />;
  if (error || !data) return <ErrorState message={error ?? "Overview data unavailable"} onRetry={() => setReloadKey((k) => k + 1)} />;

  const topBus = data.busTop.data[0];
  const topRail = data.railTop.data[0];

  const busChartData = data.busTop.data.map((r) => ({
    name: r.route_id,
    score: Number(r.overall_score.toFixed(4)),
    trips: r.scheduled_trips,
  }));

  const railChartData = data.railTop.data.map((r) => ({
    name: r.route_id,
    score: Number(r.overall_score.toFixed(4)),
    trips: r.scheduled_trips,
  }));

  const ridershipChartData = data.sampleRidership.data.map((obs) => ({
    period: obs.period,
    total_rides: obs.total_rides ?? 0,
  }));

  return (
    <div className="space-y-6">
      <MethodNote title="Historical Analytical Dashboard">
        All metrics reflect verified CTA GTFS snapshot and historical ridership records (2024–2026-08-31), not real-time
        vehicle telemetry.
      </MethodNote>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <KpiCard
          label="Canonical Routes"
          value={formatInt(data.routes.pagination.total)}
          subtext="125 CTA bus routes + 8 CTA rail lines"
          accent="sky"
        />
        <KpiCard
          label="Top-Ranked Bus Route (Track 1)"
          value={topBus ? `Route ${topBus.route_id}` : "N/A"}
          subtext={topBus ? `Score ${formatNum(topBus.overall_score, 4)} • ${formatInt(topBus.scheduled_trips)} trips` : undefined}
          accent="emerald"
        />
        <KpiCard
          label="Top-Ranked Rail Line (Track 2)"
          value={topRail ? `${topRail.route_id} Line` : "N/A"}
          subtext={topRail ? `Structural score ${formatNum(topRail.overall_score, 4)} (demand pillar 0.0)` : undefined}
          accent="violet"
        />
        <KpiCard
          label="Spatial Boarding Stops"
          value={formatInt(data.clusters.boarding_stops_input_count)}
          subtext={`${formatInt(data.clusters.dbscan_cluster_count)} DBSCAN clusters • ${formatInt(data.clusters.kmeans_eligible_stops_count)} hub-eligible`}
          accent="amber"
        />
        <KpiCard
          label="Corridor Route-Direction Patterns"
          value={formatInt(data.corridors.pagination.total)}
          subtext="Phase 6.2/6.3 directional corridor topology"
          accent="sky"
        />
        <KpiCard
          label="Bus Ridership Window"
          value="2024-01 to 2026-08"
          subtext={`Route 151 monthly observations: ${formatInt(data.sampleRidership.total_observations)}`}
          accent="emerald"
        />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <SectionCard
          title="Top 10 Bus Routes — Track 1 Composite Score"
          subtitle="Bus-only ranking methodology (demand, service provision, hubs, corridor structure)"
        >
          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={busChartData} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="name" stroke="#94a3b8" fontSize={12} />
                <YAxis stroke="#94a3b8" fontSize={12} domain={[0, "auto"]} />
                <Tooltip
                  contentStyle={{ backgroundColor: "#0f172a", borderColor: "#334155", color: "#f8fafc" }}
                />
                <Bar
                  dataKey="score"
                  name="Composite Score"
                  fill="#38bdf8"
                  radius={[4, 4, 0, 0]}
                  onClick={(entry) => {
                    if (entry && typeof entry.name === "string") onSelectRoute(entry.name);
                  }}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </SectionCard>

        <SectionCard
          title="CTA Rail Lines — Track 2 Structural Score"
          subtitle="Rail-only methodology (demand pillar excluded; 0.0 weight by design)"
        >
          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={railChartData} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="name" stroke="#94a3b8" fontSize={12} />
                <YAxis stroke="#94a3b8" fontSize={12} domain={[0, "auto"]} />
                <Tooltip
                  contentStyle={{ backgroundColor: "#0f172a", borderColor: "#334155", color: "#f8fafc" }}
                />
                <Bar
                  dataKey="score"
                  name="Structural Score"
                  fill="#a78bfa"
                  radius={[4, 4, 0, 0]}
                  onClick={(entry) => {
                    if (entry && typeof entry.name === "string") onSelectRoute(entry.name);
                  }}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </SectionCard>
      </div>

      <SectionCard
        title="Historical Monthly Ridership Trend — Benchmark Bus Route 151"
        subtitle="Total monthly CTA boardings from DuckDB analytical.daily_ridership (2024-01 to 2026-08)"
      >
        <div className="h-72 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={ridershipChartData} margin={{ top: 8, right: 16, left: 10, bottom: 8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="period" stroke="#94a3b8" fontSize={11} />
              <YAxis stroke="#94a3b8" fontSize={12} />
              <Tooltip
                contentStyle={{ backgroundColor: "#0f172a", borderColor: "#334155", color: "#f8fafc" }}
              />
              <Line
                type="monotone"
                dataKey="total_rides"
                name="Total Monthly Rides"
                stroke="#34d399"
                strokeWidth={2}
                dot={{ r: 2.5 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </SectionCard>
    </div>
  );
}
