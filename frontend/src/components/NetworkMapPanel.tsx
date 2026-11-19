import React from "react";
import { MapContainer, Polyline, TileLayer, Tooltip as LeafletTooltip } from "react-leaflet";
import { GroupsData, RouteSummary } from "../api";

interface NetworkMapPanelProps {
  geometries: GroupsData["geometries"];
  routes: RouteSummary[];
  selectedRoute: string;
  onPickRoute: (route: string) => void;
  onOpenRoute: (route: string) => void;
}

export const NetworkMapPanel: React.FC<NetworkMapPanelProps> = ({
  geometries,
  routes,
  selectedRoute,
  onPickRoute,
  onOpenRoute,
}) => {
  const others = Object.values(geometries.routes).filter((g) => g.route !== selectedRoute);
  const sel = geometries.routes[selectedRoute];
  const prof = routes.find((r) => r.route === selectedRoute);

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm" data-testid="network-map">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="text-sm font-bold text-slate-900">Network map</h2>
          <p className="text-xs text-slate-500">
            All 41 study routes in grey. The selected route is highlighted. Click a line to select it. Shapes from GTFS{" "}
            {geometries.source_snapshot}; they show paths, not live bus positions.
          </p>
        </div>
        {prof ? (
          <div className="text-right text-xs">
            <div className="font-bold text-blue-700">
              {prof.route} · {prof.route_long_name}
            </div>
            <button type="button" onClick={() => onOpenRoute(prof.route)} className="font-semibold text-slate-600 hover:underline">
              Open route detail →
            </button>
          </div>
        ) : null}
      </div>
      <div className="mt-3 h-[22rem] overflow-hidden rounded-lg border border-slate-200">
        <MapContainer center={geometries.center ?? [40.7831, -73.9712]} zoom={12} style={{ height: "100%", width: "100%" }} scrollWheelZoom={false}>
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          {others.map((g) =>
            g.polylines.map((pl) => (
              <Polyline
                key={`${g.route}-${pl.direction_id}`}
                positions={pl.coords}
                pathOptions={{ color: "#94a3b8", weight: 2, opacity: 0.6 }}
                eventHandlers={{ click: () => onPickRoute(g.route) }}
              >
                <LeafletTooltip sticky>{g.route}</LeafletTooltip>
              </Polyline>
            ))
          )}
          {sel
            ? sel.polylines.map((pl) => (
                <Polyline key={`sel-${pl.direction_id}`} positions={pl.coords} pathOptions={{ color: "#2563eb", weight: 6, opacity: 0.95 }}>
                  <LeafletTooltip sticky>{selectedRoute}</LeafletTooltip>
                </Polyline>
              ))
            : null}
        </MapContainer>
      </div>
      <p className="mt-2 text-[11px] text-slate-500">
        {sel
          ? `${selectedRoute}: ${sel.polylines.length} shape variant${sel.polylines.length === 1 ? "" : "s"} · GTFS ${geometries.source_snapshot}. `
          : `${selectedRoute}: no shape in GTFS ${geometries.source_snapshot}. `}
        Street tiles need internet; the route lines still draw without them.
      </p>
    </section>
  );
};
