import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
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
import type {
  RankingListResponse,
  RouteExplanationResponse,
  SensitivityListResponse,
} from "../types/api";

type TrackTab = "bus" | "rail" | "unified";

export function RankingsPage() {
  const [track, setTrack] = useState<TrackTab>("bus");
  const [offset, setOffset] = useState(0);
  const [rankings, setRankings] = useState<RankingListResponse | null>(null);
  const [sensitivity, setSensitivity] = useState<SensitivityListResponse | null>(null);
  const [selected, setSelected] = useState<{ routeId: string; track: TrackTab } | null>({
    routeId: "151",
    track: "bus",
  });
  const [explanation, setExplanation] = useState<RouteExplanationResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);

    const fetchRankings =
      track === "bus"
        ? apiClient.getBusRankings({ limit: 20, offset }, controller.signal)
        : track === "rail"
        ? apiClient.getRailRankings(undefined, controller.signal)
        : apiClient.getUnifiedRankings({ limit: 20, offset }, controller.signal);

    const trackFilter = track === "bus" ? "BUS_PRIORITY" : track === "rail" ? "RAIL_PRIORITY" : "UNIFIED_SUPPLY";

    Promise.all([fetchRankings, apiClient.getSensitivity({ track: trackFilter }, controller.signal)])
      .then(([rankRes, sensRes]) => {
        setRankings(rankRes);
        setSensitivity(sensRes);
        if (rankRes.data.length > 0) {
          setSelected({ routeId: rankRes.data[0].route_id, track });
        } else {
          setSelected(null);
        }
      })
      .catch((err: unknown) => {
        if (err instanceof DOMException && err.name === "AbortError") return;
        setError(err instanceof Error ? err.message : "Failed to load rankings.");
      })
      .finally(() => setLoading(false));

    return () => controller.abort();
  }, [track, offset]);

  useEffect(() => {
    if (!selected || selected.track !== track) return;
    const controller = new AbortController();
    const trackParam = track === "bus" ? "BUS_PRIORITY" : track === "rail" ? "RAIL_PRIORITY" : "UNIFIED_SUPPLY";
    apiClient
      .getRouteExplanation(selected.routeId, trackParam, controller.signal)
      .then(setExplanation)
      .catch(() => setExplanation(null));
    return () => controller.abort();
  }, [selected, track]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap gap-2">
        {(
          [
            ["bus", "Track 1: Bus Rankings (125)"],
            ["rail", "Track 2: Rail Rankings (8)"],
            ["unified", "Track 3: Unified Structural (133)"],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            onClick={() => {
              setTrack(id);
              setOffset(0);
              setSelected(null);
              setExplanation(null);
            }}
            className={`rounded-lg px-4 py-2 text-xs font-semibold transition-colors ${
              track === id
                ? "bg-sky-500 text-slate-950"
                : "border border-slate-700 bg-slate-900 text-slate-300 hover:bg-slate-800"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {track === "unified" && (
        <MethodNote title="Cross-Modal Comparison Boundary" tone="warning">
          Unified Track 3 compares bus and rail routes on structural service, hub, and corridor pillars only. Bus
          ridership demand is excluded so bus and rail scores remain structurally comparable without conflating modes.
        </MethodNote>
      )}
      {track === "rail" && (
        <MethodNote title="Rail Methodology">
          Track 2 sets the demand pressure pillar to 0.0 by design because CTA bus ridership tables do not include rail
          line boardings.
        </MethodNote>
      )}

      {loading ? (
        <LoadingState label="Loading ranking track..." />
      ) : error ? (
        <ErrorState message={error} />
      ) : !rankings || rankings.data.length === 0 ? (
        <EmptyState />
      ) : (
        <div className="grid grid-cols-1 gap-6 xl:grid-cols-12">
          <div className="xl:col-span-7">
            <SectionCard title={`Rankings — ${rankings.track}`} subtitle={`Profile: ${rankings.profile}`}>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="border-b border-slate-800 text-slate-400">
                    <tr>
                      <th className="py-2 pr-2 font-medium">Rank</th>
                      <th className="py-2 pr-2 font-medium">Route</th>
                      <th className="py-2 pr-2 font-medium">Name</th>
                      <th className="py-2 pr-2 font-medium text-right">Score</th>
                      <th className="py-2 pr-2 font-medium text-right">TOPSIS</th>
                      <th className="py-2 font-medium">Flags</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/70">
                    {rankings.data.map((item) => (
                      <tr
                        key={item.route_id}
                        onClick={() => setSelected({ routeId: item.route_id, track })}
                        className={`cursor-pointer ${
                          selected?.routeId === item.route_id ? "bg-sky-500/15" : "hover:bg-slate-800/50"
                        }`}
                      >
                        <td className="py-2.5 pr-2 font-bold text-slate-100">#{item.rank}</td>
                        <td className="py-2.5 pr-2 font-semibold text-sky-300">{item.route_id}</td>
                        <td className="py-2.5 pr-2 text-slate-200">{item.route_long_name}</td>
                        <td className="py-2.5 pr-2 text-right font-mono text-emerald-300">
                          {formatNum(item.overall_score, 4)}
                        </td>
                        <td className="py-2.5 pr-2 text-right font-mono text-slate-300">
                          {formatNum(item.topsis_score, 4)}
                        </td>
                        <td className="py-2.5">
                          {item.is_headway_missing ? (
                            <Badge variant="amber">No Headway</Badge>
                          ) : (
                            <Badge variant={item.is_rail ? "violet" : "slate"}>
                              {item.is_rail ? "Rail" : "Complete"}
                            </Badge>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {track !== "rail" && <PaginationBar pagination={rankings.pagination} onPageChange={setOffset} />}
            </SectionCard>
          </div>

          <div className="space-y-6 xl:col-span-5">
            {explanation && (
              <SectionCard
                title={`Explanation — Route ${explanation.route_id}`}
                subtitle={`Rank #${explanation.rank}/${explanation.total_routes} • Weight coverage ${(explanation.valid_weight_coverage * 100).toFixed(0)}%`}
              >
                <div className="h-52 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={[
                        { pillar: "Demand", value: explanation.pillars.demand_pressure },
                        { pillar: "Service", value: explanation.pillars.service_provision },
                        { pillar: "Hubs", value: explanation.pillars.network_hubs },
                        { pillar: "Corridor", value: explanation.pillars.corridor_structure },
                      ]}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                      <XAxis dataKey="pillar" stroke="#94a3b8" fontSize={11} />
                      <YAxis stroke="#94a3b8" fontSize={11} />
                      <Tooltip
                        contentStyle={{ backgroundColor: "#0f172a", borderColor: "#334155", color: "#f8fafc" }}
                      />
                      <Bar dataKey="value" fill="#38bdf8" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
                <p className="mt-3 text-xs leading-relaxed text-slate-300">{explanation.narrative}</p>
              </SectionCard>
            )}

            {sensitivity && sensitivity.data.length > 0 && (
              <SectionCard
                title="Weight Sensitivity Scenarios"
                subtitle={`${sensitivity.total_scenarios} perturbations evaluated`}
              >
                <div className="max-h-56 overflow-y-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="border-b border-slate-800 text-slate-400">
                      <tr>
                        <th className="py-1.5 pr-2">Criterion</th>
                        <th className="py-1.5 pr-2 text-right">Delta</th>
                        <th className="py-1.5 pr-2 text-right">Spearman ρ</th>
                        <th className="py-1.5 text-right">Top-10</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/70">
                      {sensitivity.data.slice(0, 12).map((s) => (
                        <tr key={s.scenario_id}>
                          <td className="py-1.5 pr-2 text-slate-200">{s.target_criterion}</td>
                          <td className="py-1.5 pr-2 text-right font-mono text-slate-300">{s.delta}</td>
                          <td className="py-1.5 pr-2 text-right font-mono text-emerald-300">
                            {formatNum(s.spearman_rho, 4)}
                          </td>
                          <td className="py-1.5 text-right text-slate-300">{s.top_10_overlap}/10</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </SectionCard>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
