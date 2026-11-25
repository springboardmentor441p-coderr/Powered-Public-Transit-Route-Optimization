import { useEffect, useState } from "react";
import { apiClient } from "../api/client";
import {
  Badge,
  EmptyState,
  ErrorState,
  LoadingState,
  MethodNote,
  PaginationBar,
  SectionCard,
  formatNum,
} from "../components/ui";
import type { CorridorClusterListResponse, RouteCoRoutingResponse } from "../types/api";

export function CorridorsPage() {
  const [k, setK] = useState<number>(3);
  const [clusterType, setClusterType] = useState<string>("buffer");
  const [mode, setMode] = useState<string>("");
  const [offset, setOffset] = useState<number>(0);

  const [clusters, setClusters] = useState<CorridorClusterListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [routeId, setRouteId] = useState<string>("151");
  const [coRouting, setCoRouting] = useState<RouteCoRoutingResponse | null>(null);
  const [coLoading, setCoLoading] = useState(false);
  const [coError, setCoError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    apiClient
      .getCorridorClusters(
        {
          k,
          cluster_type: clusterType,
          mode: mode || undefined,
          limit: 15,
          offset,
        },
        controller.signal
      )
      .then(setClusters)
      .catch((err: unknown) => {
        if (err instanceof DOMException && err.name === "AbortError") return;
        setError(err instanceof Error ? err.message : "Failed to load corridor clusters.");
      })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, [k, clusterType, mode, offset]);

  useEffect(() => {
    if (!routeId.trim()) return;
    const controller = new AbortController();
    setCoLoading(true);
    setCoError(null);
    apiClient
      .getRouteCoRouting(routeId.trim(), { top_n: 8 }, controller.signal)
      .then(setCoRouting)
      .catch((err: unknown) => {
        if (err instanceof DOMException && err.name === "AbortError") return;
        setCoError(err instanceof Error ? err.message : "Failed to load route co-routing.");
      })
      .finally(() => setCoLoading(false));
    return () => controller.abort();
  }, [routeId]);

  return (
    <div className="space-y-6">
      <MethodNote title="Distinct Corridor Similarity Metrics">
        Buffer overlap, Fréchet geometric clustering, stop-set Jaccard similarity, and shared consecutive stop sequences
        measure distinct spatial and topological properties. They are kept strictly separate—never merged into a single
        composite similarity score—and do not represent socioeconomic equity.
      </MethodNote>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-12">
        <div className="xl:col-span-6">
          <SectionCard
            title="Corridor Cluster Assignments"
            subtitle="Phase 6.2 directional pattern clusters"
            actions={
              <div className="flex flex-wrap gap-2">
                <select
                  value={clusterType}
                  onChange={(e) => {
                    setClusterType(e.target.value);
                    setOffset(0);
                  }}
                  aria-label="Corridor cluster type"
                  className="rounded-lg border border-slate-700 bg-slate-950 px-2.5 py-1.5 text-xs text-slate-100"
                >
                  <option value="buffer">Buffer Overlap</option>
                  <option value="frechet">Fréchet Geometric</option>
                </select>
                <select
                  value={k}
                  onChange={(e) => {
                    setK(Number(e.target.value));
                    setOffset(0);
                  }}
                  aria-label="Cluster count k"
                  className="rounded-lg border border-slate-700 bg-slate-950 px-2.5 py-1.5 text-xs text-slate-100"
                >
                  <option value={3}>k = 3</option>
                  <option value={4}>k = 4</option>
                  <option value={5}>k = 5</option>
                </select>
                <select
                  value={mode}
                  onChange={(e) => {
                    setMode(e.target.value);
                    setOffset(0);
                  }}
                  aria-label="Corridor mode filter"
                  className="rounded-lg border border-slate-700 bg-slate-950 px-2.5 py-1.5 text-xs text-slate-100"
                >
                  <option value="">All</option>
                  <option value="bus">Bus</option>
                  <option value="rail">Rail</option>
                </select>
              </div>
            }
          >
            {loading ? (
              <LoadingState label="Loading corridor clusters..." />
            ) : error ? (
              <ErrorState message={error} />
            ) : !clusters || clusters.data.length === 0 ? (
              <EmptyState />
            ) : (
              <>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="border-b border-slate-800 text-slate-400">
                      <tr>
                        <th className="py-2 pr-2">Pattern</th>
                        <th className="py-2 pr-2">Route</th>
                        <th className="py-2 pr-2">Cluster</th>
                        <th className="py-2 text-right">Length (km)</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/70">
                      {clusters.data.map((c) => (
                        <tr
                          key={c.pattern_id}
                          onClick={() => setRouteId(c.route_id)}
                          className={`cursor-pointer ${
                            routeId === c.route_id ? "bg-sky-500/15" : "hover:bg-slate-800/40"
                          }`}
                        >
                          <td className="py-2 pr-2 font-mono text-sky-300">{c.pattern_id}</td>
                          <td className="py-2 pr-2 text-slate-200">{c.route_id}</td>
                          <td className="py-2 pr-2">
                            <Badge variant="violet">Cluster {c.cluster_id}</Badge>
                          </td>
                          <td className="py-2 text-right text-slate-300">{formatNum(c.length_km, 2)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <PaginationBar pagination={clusters.pagination} onPageChange={setOffset} />
              </>
            )}
          </SectionCard>
        </div>

        <div className="xl:col-span-6">
          <SectionCard
            title={`Co-Routing Profile — Route ${routeId}`}
            subtitle="Separate geographic buffer overlap, stop Jaccard, and consecutive stop sequences"
            actions={
              <input
                type="text"
                value={routeId}
                onChange={(e) => setRouteId(e.target.value)}
                placeholder="Route ID (e.g. 151)"
                aria-label="Co-routing route ID"
                className="w-36 rounded-lg border border-slate-700 bg-slate-950 px-2.5 py-1.5 text-xs text-slate-100"
              />
            }
          >
            {coLoading ? (
              <LoadingState label="Loading co-routing peers..." />
            ) : coError ? (
              <ErrorState message={coError} />
            ) : !coRouting || coRouting.patterns.length === 0 ? (
              <EmptyState />
            ) : (
              <div className="space-y-4">
                {coRouting.patterns.map((pat) => (
                  <div key={pat.pattern_id} className="space-y-3 rounded-lg border border-slate-800 bg-slate-950/60 p-3.5 text-xs">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="font-mono font-semibold text-sky-300">
                        Pattern {pat.pattern_id} (Dir {pat.direction_id})
                      </span>
                      <span className="text-slate-400">
                        {formatNum(pat.length_km, 2)} km • Missing matrix entries: {pat.missing_buffer_entries_count} buffer /{" "}
                        {pat.missing_jaccard_entries_count} Jaccard
                      </span>
                    </div>

                    <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                      <div>
                        <p className="mb-1.5 font-semibold text-slate-200">Buffer Overlap Peers</p>
                        {pat.geographic_overlap_peers.length === 0 ? (
                          <p className="text-slate-500">None</p>
                        ) : (
                          <ul className="space-y-1">
                            {pat.geographic_overlap_peers.slice(0, 5).map((p) => (
                              <li key={p.peer_pattern_id} className="flex justify-between text-slate-300">
                                <span>{p.peer_pattern_id}</span>
                                <span className="font-mono text-emerald-300">{formatNum(p.similarity_score, 4)}</span>
                              </li>
                            ))}
                          </ul>
                        )}
                      </div>

                      <div>
                        <p className="mb-1.5 font-semibold text-slate-200">Stop Jaccard Peers</p>
                        {pat.stop_jaccard_peers.length === 0 ? (
                          <p className="text-slate-500">None</p>
                        ) : (
                          <ul className="space-y-1">
                            {pat.stop_jaccard_peers.slice(0, 5).map((p) => (
                              <li key={p.peer_pattern_id} className="flex justify-between text-slate-300">
                                <span>{p.peer_pattern_id}</span>
                                <span className="font-mono text-violet-300">{formatNum(p.similarity_score, 4)}</span>
                              </li>
                            ))}
                          </ul>
                        )}
                      </div>
                    </div>

                    <div>
                      <p className="mb-1 font-semibold text-slate-200">
                        Shared Consecutive Stop Sequences ({pat.shared_consecutive_sequences.length})
                      </p>
                      {pat.shared_consecutive_sequences.slice(0, 3).map((seq, i) => (
                        <p key={`${seq.peer_pattern_id}-${i}`} className="text-slate-400">
                          With <span className="text-slate-200">{seq.peer_pattern_id}</span>: {seq.sequence_length} stops (
                          {seq.start_stop_id} → {seq.end_stop_id})
                        </p>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </SectionCard>
        </div>
      </div>
    </div>
  );
}
