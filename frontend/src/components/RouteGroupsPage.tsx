import React, { useMemo, useState } from "react";
import { MapContainer, Polyline, Popup, TileLayer } from "react-leaflet";
import {
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";
import { fmtInt, fmtNum, fmtSharePct, GroupsData } from "../api";
import { PageHeader } from "./PageHeader";

interface RouteGroupsPageProps {
  groups: GroupsData;
  onSelectRoute: (route: string) => void;
}

const GROUP_COLORS: Record<number, string> = {
  1: "#1d4ed8",
  2: "#059669",
  3: "#d97706",
  0: "#dc2626",
};

const GROUP_SHORT: Record<number, string> = {
  1: "Group 1: Longer routes (~7k riders/day, n=18)",
  2: "Group 2: Short routes, high riders/svc-hr (n=15)",
  3: "Group 3: Short routes, fewer/less steady riders (n=7)",
  0: "Outlier Removed Before Clustering: M35 (n=1)",
};

export const RouteGroupsPage: React.FC<RouteGroupsPageProps> = ({
  groups,
  onSelectRoute,
}) => {
  const [visibleGroups, setVisibleGroups] = useState<Record<number, boolean>>({
    1: true,
    2: true,
    3: true,
    0: true,
  });

  const toggleGroup = (gid: number) => {
    setVisibleGroups((prev) => ({ ...prev, [gid]: !prev[gid] }));
  };

  const routesByGroup = useMemo(() => {
    const out: Record<number, Array<Record<string, unknown>>> = { 1: [], 2: [], 3: [] };
    groups.routes.forEach((r) => {
      const gid = Number(r.group_id);
      if (gid === 1 || gid === 2 || gid === 3) {
        out[gid].push(r);
      }
    });
    return out;
  }, [groups.routes]);

  const varRatio = groups.metadata.pca_explained_variance_ratio;
  const pc1Pct = varRatio?.[0] !== undefined ? (varRatio[0] * 100).toFixed(1) : "36.1";
  const pc2Pct = varRatio?.[1] !== undefined ? (varRatio[1] * 100).toFixed(1) : "23.1";

  return (
    <div className="space-y-6">
      <PageHeader
        title="Route Groups, Corridor Map & Clustering Validation"
        subtitle="K-Means k=3 grouping over 40 Manhattan routes (with M35 separated as a 1-route outlier before clustering), paired with PCA projection, stop overlap caveat, and k=2 vs k=3 stability comparison."
        period={groups.period}
        source={groups.source}
      />

      {/* Group Filter Pills + Caveats */}
      <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-xs text-amber-950">
        <div className="font-semibold">Shared-Corridor & Clustering Notes</div>
        <p className="mt-1">{groups.metadata.overlap_note}</p>
        <p className="mt-1">{groups.metadata.k2_vs_k3_decision_note}</p>
      </div>

      <div className="flex flex-wrap gap-2">
        {[1, 2, 3, 0].map((gid) => (
          <button
            key={gid}
            type="button"
            onClick={() => toggleGroup(gid)}
            className={`inline-flex items-center gap-2 rounded-lg border px-3 py-1.5 text-xs font-medium transition ${
              visibleGroups[gid]
                ? "border-slate-300 bg-white text-slate-900 shadow-sm"
                : "border-slate-200 bg-slate-100 text-slate-400"
            }`}
          >
            <span
              className="h-2.5 w-2.5 rounded-full"
              style={{ backgroundColor: GROUP_COLORS[gid] }}
            />
            {GROUP_SHORT[gid]}
          </button>
        ))}
      </div>

      {/* Interactive Map + PCA Scatter */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="mb-1 text-sm font-semibold text-slate-900">
            Manhattan Bus Network Route Map by Group
          </h2>
          <p className="mb-3 text-xs text-slate-500">
            Click any corridor polyline to inspect metrics or jump to its Route Detail page.
          </p>
          <div className="h-96 w-full overflow-hidden rounded-lg border border-slate-200">
            <MapContainer
              center={groups.geometries.center ?? [40.7831, -73.9712]}
              zoom={12}
              style={{ height: "100%", width: "100%" }}
            >
              <TileLayer
                attribution="&copy; OpenStreetMap"
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              />
              {groups.routes.map((row) => {
                const routeId = String(row.route_id);
                const gid = Number(row.group_id);
                if (!visibleGroups[gid]) return null;
                const geom = groups.geometries.routes[routeId];
                if (!geom) return null;
                const color = GROUP_COLORS[gid] ?? "#64748b";
                return geom.polylines.map((pl) => (
                  <Polyline
                    key={`${routeId}-${pl.direction_id}`}
                    positions={pl.coords}
                    pathOptions={{ color, weight: gid === 0 ? 5 : 3, opacity: 0.78 }}
                  >
                    <Popup>
                      <div className="text-xs">
                        <div className="font-bold text-slate-900">{routeId}</div>
                        <div className="text-slate-600">{String(row.group_label)}</div>
                        <div className="mt-1">
                          Weekday riders: {fmtInt(row.weekday_riders_est as number | null)} | Length:{" "}
                          {fmtNum(row.route_length_km as number | null, 2)} km
                        </div>
                        <button
                          type="button"
                          onClick={() => onSelectRoute(routeId)}
                          className="mt-2 rounded bg-blue-600 px-2 py-1 text-[11px] font-medium text-white"
                        >
                          Open Route Detail
                        </button>
                      </div>
                    </Popup>
                  </Polyline>
                ));
              })}
            </MapContainer>
          </div>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="mb-1 text-sm font-semibold text-slate-900">
            2D PCA Scatter of 40 Clustered Routes (M35 Excluded as Outlier)
          </h2>
          <p className="mb-3 text-xs text-slate-500">
            PC1 ({pc1Pct}% var) and PC2 ({pc2Pct}% var) capture{" "}
            {fmtNum((groups.metadata.pca_total_variance_explained ?? 0.5913) * 100, 1)}% of total variance.
          </p>
          <div className="h-96 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <ScatterChart margin={{ top: 12, right: 20, bottom: 16, left: 4 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis
                  type="number"
                  dataKey="pc1_40"
                  name="PC1"
                  tick={{ fontSize: 11 }}
                  label={{ value: `PC1 (${pc1Pct}% variance)`, position: "bottom", fontSize: 11 }}
                />
                <YAxis
                  type="number"
                  dataKey="pc2_40"
                  name="PC2"
                  tick={{ fontSize: 11 }}
                  label={{ value: `PC2 (${pc2Pct}% variance)`, angle: -90, position: "insideLeft", fontSize: 11 }}
                />
                <ZAxis type="number" dataKey="weekday_riders_est" range={[50, 260]} />
                <Tooltip
                  cursor={{ strokeDasharray: "3 3" }}
                  content={({ active, payload }) => {
                    if (!active || !payload?.length) return null;
                    const p = payload[0].payload as Record<string, unknown>;
                    return (
                      <div className="rounded-lg border border-slate-200 bg-white p-2.5 text-xs shadow-md">
                        <div className="font-bold text-slate-900">{String(p.route_id)}</div>
                        <div className="text-slate-600">{String(p.group_label)}</div>
                        <div className="mt-1">
                          Weekday riders: {fmtInt(p.weekday_riders_est as number | null)}
                        </div>
                        <div>
                          Length: {fmtNum(p.route_length_km as number | null, 2)} km | Peak riders/svc-hr:{" "}
                          {fmtNum(p.peak_riders_per_service_hour as number | null, 1)}
                        </div>
                      </div>
                    );
                  }}
                />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                {[1, 2, 3].map((gid) =>
                  visibleGroups[gid] ? (
                    <Scatter
                      key={gid}
                      name={`Group ${gid}`}
                      data={routesByGroup[gid]}
                      fill={GROUP_COLORS[gid]}
                      onClick={(entry) => {
                        if (entry?.route_id) onSelectRoute(String(entry.route_id));
                      }}
                    />
                  ) : null
                )}
              </ScatterChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Group Unscaled Profiles */}
      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <h3 className="mb-3 text-sm font-semibold text-slate-900">
          Group Profiles (Unscaled Medians) & Non-Fitting Exceptions
        </h3>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {groups.group_profiles.map((gp) => {
            const gid = Number(gp.group_id);
            return (
              <div
                key={gid}
                className="rounded-lg border border-slate-200 p-4"
                style={{
                  borderLeftWidth: 4,
                  borderLeftColor: GROUP_COLORS[gid] ?? "#64748b",
                }}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="text-sm font-semibold text-slate-900">
                    {String(gp.group_label)}
                  </div>
                  <span className="shrink-0 rounded bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-700">
                    {fmtInt(gp.n_routes as number | null)} routes
                  </span>
                </div>
                <div className="mt-2 grid grid-cols-3 gap-2 text-xs text-slate-700">
                  <div>
                    <span className="text-slate-500">Weekday riders:</span>{" "}
                    {fmtInt(gp.weekday_riders_median_est as number | null)}
                  </div>
                  <div>
                    <span className="text-slate-500">Length:</span>{" "}
                    {fmtNum(gp.route_length_km as number | null, 2)} km
                  </div>
                  <div>
                    <span className="text-slate-500">Peak r/svc-hr:</span>{" "}
                    {fmtNum(gp.peak_riders_per_service_hour as number | null, 1)}
                  </div>
                  <div>
                    <span className="text-slate-500">Variability CV:</span>{" "}
                    {fmtNum(gp.demand_variability as number | null, 3)}
                  </div>
                  <div>
                    <span className="text-slate-500">Weekend ratio:</span>{" "}
                    {fmtNum(gp.weekend_to_weekday_ratio as number | null, 3)}
                  </div>
                  <div>
                    <span className="text-slate-500">Excl stops:</span>{" "}
                    {fmtSharePct(gp.exclusive_stop_share as number | null)}
                  </div>
                </div>
                <p className="mt-2 text-xs text-slate-600">
                  <span className="font-semibold text-slate-800">Routes:</span>{" "}
                  {String(gp.routes)}
                </p>
                <p className="mt-1 text-xs text-slate-600">
                  <span className="font-semibold text-slate-800">Exceptions:</span>{" "}
                  {String(gp.non_fitting_members)}
                </p>
              </div>
            );
          })}
        </div>
      </div>

      {/* k Selection Stability Table */}
      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <h3 className="mb-3 text-sm font-semibold text-slate-900">
          K-Selection Stability & Silhouette Diagnostics (40 Routes vs 41 Routes)
        </h3>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-slate-200 text-slate-500">
              <tr>
                <th className="py-2 pr-3 font-medium">Route Set</th>
                <th className="py-2 pr-3 text-right font-medium">k</th>
                <th className="py-2 pr-3 text-right font-medium">Silhouette</th>
                <th className="py-2 pr-3 text-right font-medium">10-Start ARI</th>
                <th className="py-2 pr-3 text-right font-medium">LOO ARI</th>
                <th className="py-2 pr-3 font-medium">Cluster Sizes</th>
                <th className="py-2 font-medium">Decision Note</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {groups.k_selection.map((row, idx) => (
                <tr
                  key={idx}
                  className={row.is_selected_k ? "bg-emerald-50/50" : undefined}
                >
                  <td className="py-2 pr-3 font-medium text-slate-800">{String(row.route_set)}</td>
                  <td className="py-2 pr-3 text-right font-mono font-bold">
                    {fmtInt(row.k as number | null)}
                  </td>
                  <td className="py-2 pr-3 text-right font-mono">
                    {fmtNum(row.silhouette_score as number | null, 3)}
                  </td>
                  <td className="py-2 pr-3 text-right font-mono">
                    {fmtNum(row.ari_10starts_mean as number | null, 3)}
                  </td>
                  <td className="py-2 pr-3 text-right font-mono">
                    {fmtNum(row.ari_loo_mean as number | null, 3)}
                  </td>
                  <td className="py-2 pr-3 font-mono">{String(row.cluster_sizes)}</td>
                  <td className="py-2 text-slate-600">{String(row.selection_note)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
