import { useEffect, useState } from "react";
import { CircleMarker, MapContainer, Popup, TileLayer } from "react-leaflet";
import { apiClient } from "../api/client";
import {
  Badge,
  EmptyState,
  ErrorState,
  KpiCard,
  LoadingState,
  MethodNote,
  PaginationBar,
  SectionCard,
  formatInt,
  formatNum,
} from "../components/ui";
import type {
  ClusterSummaryResponse,
  SpatialHubsListResponse,
  TopHubsResponse,
} from "../types/api";

export function SpatialPage() {
  const [config, setConfig] = useState<"a" | "b" | "c">("a");
  const [viewMode, setViewMode] = useState<"top" | "all">("top");
  const [eligibleOnly, setEligibleOnly] = useState<boolean>(false);
  const [dbscanCluster, setDbscanCluster] = useState<string>("");
  const [offset, setOffset] = useState(0);

  const [summary, setSummary] = useState<ClusterSummaryResponse | null>(null);
  const [topHubs, setTopHubs] = useState<TopHubsResponse | null>(null);
  const [allHubs, setAllHubs] = useState<SpatialHubsListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    apiClient
      .getSpatialClustersSummary(controller.signal)
      .then(setSummary)
      .catch(() => {});
    return () => controller.abort();
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);

    if (viewMode === "top") {
      apiClient
        .getTopHubs({ config, limit: 100, offset: 0 }, controller.signal)
        .then((res) => {
          setTopHubs(res);
          setAllHubs(null);
        })
        .catch((err: unknown) => {
          if (err instanceof DOMException && err.name === "AbortError") return;
          setError(err instanceof Error ? err.message : "Failed to load top hubs.");
        })
        .finally(() => setLoading(false));
    } else {
      const parsedCluster = dbscanCluster.trim() === "" ? undefined : Number(dbscanCluster);
      apiClient
        .getSpatialHubs(
          {
            config,
            eligible_only: eligibleOnly || undefined,
            dbscan_cluster: Number.isFinite(parsedCluster) ? parsedCluster : undefined,
            limit: 50,
            offset,
          },
          controller.signal
        )
        .then((res) => {
          setAllHubs(res);
          setTopHubs(null);
        })
        .catch((err: unknown) => {
          if (err instanceof DOMException && err.name === "AbortError") return;
          setError(err instanceof Error ? err.message : "Failed to load spatial stops.");
        })
        .finally(() => setLoading(false));
    }

    return () => controller.abort();
  }, [config, viewMode, eligibleOnly, dbscanCluster, offset]);

  const mapPoints =
    viewMode === "top"
      ? (topHubs?.data ?? [])
          .filter((h) => h.coordinates.coordinates_available && h.coordinates.lat !== null && h.coordinates.lon !== null)
          .map((h) => ({
            id: h.stop_id,
            name: h.stop_name,
            lat: h.coordinates.lat as number,
            lon: h.coordinates.lon as number,
            rank: h.rank,
            score: h.hub_score,
            routes: h.routes_served,
            isNoise: false,
            cluster: 0,
          }))
      : (allHubs?.data ?? [])
          .filter((s) => s.coordinates.coordinates_available && s.coordinates.lat !== null && s.coordinates.lon !== null)
          .map((s) => ({
            id: s.stop_id,
            name: s.stop_name,
            lat: s.coordinates.lat as number,
            lon: s.coordinates.lon as number,
            rank: s.rank,
            score: s.hub_score,
            routes: s.routes_served,
            isNoise: s.is_noise_point,
            cluster: s.dbscan_cluster,
          }));

  return (
    <div className="space-y-6">
      <MethodNote title="Spatial Demand Proxy & Clustering Scope">
        Stop-level demand attribution is an operational proxy derived from GTFS visit shares and route-level ridership,
        not direct APC stop-level passenger counts. Geographic DBSCAN clustering reflects stop density, not socioeconomic
        equity.
      </MethodNote>

      {summary && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <KpiCard label="Boarding Stops Input" value={formatInt(summary.boarding_stops_input_count)} accent="sky" />
          <KpiCard label="DBSCAN Clusters" value={formatInt(summary.dbscan_cluster_count)} accent="emerald" />
          <KpiCard label="DBSCAN Noise Stops (-1)" value={formatInt(summary.dbscan_noise_stop_count)} accent="amber" />
          <KpiCard label="Hub-Eligible Stops" value={formatInt(summary.kmeans_eligible_stops_count)} accent="violet" />
        </div>
      )}

      <SectionCard
        title="Spatial Hub Controls"
        subtitle="Switch between Canonical Top-100 Hubs and full DBSCAN stop exploration"
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <select
              value={viewMode}
              onChange={(e) => {
                setViewMode(e.target.value as "top" | "all");
                setOffset(0);
              }}
              aria-label="Spatial view mode"
              className="rounded-lg border border-slate-700 bg-slate-950 px-2.5 py-1.5 text-xs text-slate-100"
            >
              <option value="top">Top-100 Canonical Hubs</option>
              <option value="all">All Stops (DBSCAN &amp; Noise)</option>
            </select>

            <select
              value={config}
              onChange={(e) => {
                setConfig(e.target.value as "a" | "b" | "c");
                setOffset(0);
              }}
              aria-label="Hub weighting configuration"
              className="rounded-lg border border-slate-700 bg-slate-950 px-2.5 py-1.5 text-xs text-slate-100"
            >
              <option value="a">Config A (Balanced)</option>
              <option value="b">Config B (Connectivity)</option>
              <option value="c">Config C (Demand Proxy)</option>
            </select>

            {viewMode === "all" && (
              <>
                <input
                  type="number"
                  value={dbscanCluster}
                  onChange={(e) => {
                    setDbscanCluster(e.target.value);
                    setOffset(0);
                  }}
                  placeholder="DBSCAN ID (-1 = noise)"
                  aria-label="Filter by DBSCAN cluster"
                  className="w-40 rounded-lg border border-slate-700 bg-slate-950 px-2.5 py-1.5 text-xs text-slate-100"
                />
                <label className="inline-flex items-center gap-1.5 text-xs text-slate-300">
                  <input
                    type="checkbox"
                    checked={eligibleOnly}
                    onChange={(e) => {
                      setEligibleOnly(e.target.checked);
                      setOffset(0);
                    }}
                    className="rounded border-slate-700 bg-slate-950"
                  />
                  Eligible Only
                </label>
              </>
            )}
          </div>
        }
      >
        {loading ? (
          <LoadingState label="Loading spatial hub coordinates..." />
        ) : error ? (
          <ErrorState message={error} />
        ) : mapPoints.length === 0 ? (
          <EmptyState title="No stops match filters" />
        ) : (
          <div className="space-y-5">
            <div className="h-[420px] w-full overflow-hidden rounded-xl border border-slate-800">
              <MapContainer center={[41.8781, -87.6298]} zoom={11} className="h-full w-full">
                <TileLayer
                  attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                  url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                />
                {mapPoints.map((pt) => (
                  <CircleMarker
                    key={pt.id}
                    center={[pt.lat, pt.lon]}
                    radius={pt.rank && pt.rank <= 10 ? 8 : 5}
                    pathOptions={{
                      color: pt.isNoise ? "#f59e0b" : "#38bdf8",
                      fillColor: pt.isNoise ? "#f59e0b" : "#0ea5e9",
                      fillOpacity: 0.75,
                    }}
                  >
                    <Popup>
                      <div className="text-xs text-slate-900">
                        <p className="font-bold">
                          {pt.name} (Stop {pt.id})
                        </p>
                        {pt.rank !== null && <p>Rank: #{pt.rank}</p>}
                        {pt.score !== null && <p>Hub Score: {formatNum(pt.score, 4)}</p>}
                        {pt.routes !== null && <p>Routes Served: {pt.routes}</p>}
                        {viewMode === "all" && <p>DBSCAN Cluster: {pt.isNoise ? "-1 (Noise)" : pt.cluster}</p>}
                      </div>
                    </Popup>
                  </CircleMarker>
                ))}
              </MapContainer>
            </div>

            <div className="max-h-72 overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="border-b border-slate-800 text-slate-400">
                  <tr>
                    <th className="py-2 pr-3">Rank</th>
                    <th className="py-2 pr-3">Stop ID</th>
                    <th className="py-2 pr-3">Stop Name</th>
                    <th className="py-2 pr-3 text-right">Hub Score</th>
                    <th className="py-2 pr-3 text-right">Routes</th>
                    <th className="py-2">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/70">
                  {mapPoints.slice(0, 25).map((pt) => (
                    <tr key={pt.id} className="hover:bg-slate-800/40">
                      <td className="py-2 pr-3 font-semibold text-slate-100">
                        {pt.rank !== null ? `#${pt.rank}` : "—"}
                      </td>
                      <td className="py-2 pr-3 font-mono text-sky-300">{pt.id}</td>
                      <td className="py-2 pr-3 text-slate-200">{pt.name}</td>
                      <td className="py-2 pr-3 text-right font-mono text-emerald-300">
                        {pt.score !== null ? formatNum(pt.score, 4) : "N/A"}
                      </td>
                      <td className="py-2 pr-3 text-right text-slate-300">{pt.routes ?? "N/A"}</td>
                      <td className="py-2">
                        {pt.isNoise ? (
                          <Badge variant="amber">Noise (-1)</Badge>
                        ) : (
                          <Badge variant="sky">{viewMode === "top" ? "Top-100" : `Cluster ${pt.cluster}`}</Badge>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {viewMode === "all" && allHubs && (
              <PaginationBar pagination={allHubs.pagination} onPageChange={setOffset} />
            )}
          </div>
        )}
      </SectionCard>
    </div>
  );
}
