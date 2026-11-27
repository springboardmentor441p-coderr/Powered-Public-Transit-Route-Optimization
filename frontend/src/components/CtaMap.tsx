import React, { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

interface GeoStop {
  stop_id: number;
  name: string;
  desc?: string;
  lat: number;
  lon: number;
  is_terminal?: boolean;
  wheelchair?: boolean;
  routes_served?: string[];
}

interface GeoRoute {
  route_id: string;
  name: string;
  long_name: string;
  cluster: string;
  color: string;
  polylines: [number, number][][];
  stops?: GeoStop[];
  bounds?: [[number, number], [number, number]] | null;
  stop_count?: number;
}

interface LiveVehicle {
  vehicle_id: string;
  route_id: string;
  route_name: string;
  color: string;
  direction: string;
  lat: number;
  lon: number;
  bearing: number;
  speed_mph: number;
  next_stop: string;
  status: string;
  occupancy: string;
  updated_at: string;
}

interface CtaMapProps {
  selectedRoute?: string | null;
  compareRoute?: string | null;
  showAllRoutes?: boolean;
  onSelectRoute?: (routeId: string) => void;
  height?: string | number;
}

export default function CtaMap({
  selectedRoute = null,
  compareRoute = null,
  showAllRoutes = false,
  onSelectRoute,
  height = 480,
}: CtaMapProps) {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const routeLayerRef = useRef<L.LayerGroup | null>(null);
  const stopsLayerRef = useRef<L.LayerGroup | null>(null);
  const vehiclesLayerRef = useRef<L.LayerGroup | null>(null);
  const tileLayerRef = useRef<L.LayerGroup | null>(null);

  const [allGeoRoutes, setAllGeoRoutes] = useState<Record<string, GeoRoute>>({});
  const [activeRouteGeo, setActiveRouteGeo] = useState<GeoRoute | null>(null);
  const [compareRouteGeo, setCompareRouteGeo] = useState<GeoRoute | null>(null);
  const [networkStops, setNetworkStops] = useState<GeoStop[]>([]);

  // Toggles
  const [showStops, setShowStops] = useState<boolean>(true);
  const [showLiveVehicles, setShowLiveVehicles] = useState<boolean>(true);
  const [liveVehicles, setLiveVehicles] = useState<LiveVehicle[]>([]);
  const [basemapStyle, setBasemapStyle] = useState<"canvas" | "streets">("canvas");
  const [loading, setLoading] = useState<boolean>(true);

  // Chicago Center
  const CHICAGO_CENTER: [number, number] = [41.8781, -87.6298];

  // 1. Fetch overview routes summary on mount
  useEffect(() => {
    fetch("/api/geo/routes")
      .then((r) => (r.ok ? r.json() : {}))
      .then((data) => {
        setAllGeoRoutes(data);
        setLoading(false);
      })
      .catch((err) => {
        console.error("Failed to load geo routes:", err);
        setLoading(false);
      });

    // Also fetch major network stops
    fetch("/api/geo/stops")
      .then((r) => (r.ok ? r.json() : []))
      .then(setNetworkStops)
      .catch(() => {});
  }, []);

  // 2. Fetch full detail (including stops) for selectedRoute
  useEffect(() => {
    if (!selectedRoute) {
      setActiveRouteGeo(null);
      return;
    }
    fetch(`/api/geo/routes/${selectedRoute}`)
      .then((r) => (r.ok ? r.json() : null))
      .then(setActiveRouteGeo)
      .catch(() => setActiveRouteGeo(null));
  }, [selectedRoute]);

  // 3. Fetch full detail for compareRoute if active
  useEffect(() => {
    if (!compareRoute) {
      setCompareRouteGeo(null);
      return;
    }
    fetch(`/api/geo/routes/${compareRoute}`)
      .then((r) => (r.ok ? r.json() : null))
      .then(setCompareRouteGeo)
      .catch(() => setCompareRouteGeo(null));
  }, [compareRoute]);

  // 4. Poll live vehicle positions from API
  useEffect(() => {
    if (!showLiveVehicles) {
      setLiveVehicles([]);
      return;
    }

    const fetchVehicles = () => {
      const endpoint = selectedRoute
        ? `/api/geo/live-vehicles/${selectedRoute}`
        : `/api/geo/live-vehicles`;

      fetch(endpoint)
        .then((r) => (r.ok ? r.json() : { vehicles: [] }))
        .then((d) => setLiveVehicles(d.vehicles || []))
        .catch(() => {});
    };

    fetchVehicles();
    const interval = setInterval(fetchVehicles, 3000);
    return () => clearInterval(interval);
  }, [selectedRoute, showLiveVehicles]);

  // 5. Initialize Leaflet Map (WITH CLEAN ESRI TILES - NO WATERMARK)
  useEffect(() => {
    if (!mapContainerRef.current || mapInstanceRef.current) return;

    const map = L.map(mapContainerRef.current, {
      center: CHICAGO_CENTER,
      zoom: 11,
      zoomControl: true,
      preferCanvas: true,
    });

    const tileGroup = L.layerGroup().addTo(map);
    const routeGroup = L.layerGroup().addTo(map);
    const stopsGroup = L.layerGroup().addTo(map);
    const vehGroup = L.layerGroup().addTo(map);

    mapInstanceRef.current = map;
    tileLayerRef.current = tileGroup;
    routeLayerRef.current = routeGroup;
    stopsLayerRef.current = stopsGroup;
    vehiclesLayerRef.current = vehGroup;

    return () => {
      map.remove();
      mapInstanceRef.current = null;
      tileLayerRef.current = null;
      routeLayerRef.current = null;
      stopsLayerRef.current = null;
      vehiclesLayerRef.current = null;
    };
  }, []);

  // 6. Switch Tile Basemap (NO WATERMARK)
  useEffect(() => {
    const tileGroup = tileLayerRef.current;
    if (!tileGroup) return;

    tileGroup.clearLayers();

    if (basemapStyle === "canvas") {
      // Esri Light Gray Base (clean, fast, free, NO watermark)
      L.tileLayer(
        "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}",
        {
          attribution:
            '&copy; <a href="https://www.esri.com/">Esri</a> &copy; OpenStreetMap contributors',
          maxZoom: 16,
        }
      ).addTo(tileGroup);

      // Light Gray Reference Labels
      L.tileLayer(
        "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Reference/MapServer/tile/{z}/{y}/{x}",
        { maxZoom: 16 }
      ).addTo(tileGroup);
    } else {
      // Esri World Street Map (detailed roads, transit, lakes, parks)
      L.tileLayer(
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}",
        {
          attribution:
            '&copy; <a href="https://www.esri.com/">Esri</a>, HERE, Garmin, USGS, EPA',
          maxZoom: 18,
        }
      ).addTo(tileGroup);
    }
  }, [basemapStyle]);

  // 7. Render Polylines
  useEffect(() => {
    const map = mapInstanceRef.current;
    const group = routeLayerRef.current;
    if (!map || !group) return;

    group.clearLayers();
    const boundsToFit = L.latLngBounds([]);

    // A) If showAllRoutes is active (Network overview)
    if (showAllRoutes && allGeoRoutes) {
      Object.values(allGeoRoutes).forEach((route) => {
        const isCurrent = route.route_id === selectedRoute;
        const color = isCurrent ? "#059669" : route.color || "#0284c7";
        const weight = isCurrent ? 5 : 2;
        const opacity = isCurrent ? 0.95 : 0.65;

        route.polylines.forEach((linePts) => {
          if (linePts.length > 0) {
            const poly = L.polyline(linePts, {
              color,
              weight,
              opacity,
              lineJoin: "round",
            }).addTo(group);

            poly.bindTooltip(
              `<div style="font-family:system-ui;font-size:12px">
                <strong style="color:#0f172a;font-size:13px">Route ${route.route_id}</strong> (${route.name})<br/>
                <span style="color:#059669;font-weight:600">${route.long_name}</span><br/>
                <span style="color:#64748b;font-size:11px">${route.cluster}</span>
              </div>`,
              { sticky: true }
            );

            poly.on("click", () => {
              if (onSelectRoute) onSelectRoute(route.route_id);
            });
          }
        });
      });
    }

    // B) Render Selected Route Polylines
    if (activeRouteGeo) {
      const color = activeRouteGeo.color || "#059669";

      activeRouteGeo.polylines.forEach((linePts) => {
        if (linePts.length > 0) {
          const poly = L.polyline(linePts, {
            color,
            weight: 5,
            opacity: 0.92,
            lineJoin: "round",
          }).addTo(group);

          poly.bindTooltip(
            `<strong>Route ${activeRouteGeo.route_id}</strong> — ${activeRouteGeo.long_name}`,
            { sticky: true }
          );

          linePts.forEach((pt) => boundsToFit.extend(pt));
        }
      });
    }

    // C) Render Compare Route
    if (compareRouteGeo) {
      const compareColor = "#2563eb";

      compareRouteGeo.polylines.forEach((linePts) => {
        if (linePts.length > 0) {
          const poly = L.polyline(linePts, {
            color: compareColor,
            weight: 4,
            opacity: 0.85,
            dashArray: "6, 6",
            lineJoin: "round",
          }).addTo(group);

          poly.bindTooltip(
            `<strong>Route ${compareRouteGeo.route_id} (Comparison)</strong> — ${compareRouteGeo.long_name}`,
            { sticky: true }
          );

          linePts.forEach((pt) => boundsToFit.extend(pt));
        }
      });
    }

    if (boundsToFit.isValid()) {
      map.fitBounds(boundsToFit, { padding: [35, 35], maxZoom: 14 });
    }
  }, [allGeoRoutes, activeRouteGeo, compareRouteGeo, showAllRoutes, selectedRoute, onSelectRoute]);

  // 8. Render Stops
  useEffect(() => {
    const group = stopsLayerRef.current;
    if (!group) return;

    group.clearLayers();
    if (!showStops) return;

    // Helper to create stop marker
    const renderStop = (s: GeoStop, color: string, routeLabel: string) => {
      const isTerminal = s.is_terminal || s.name.includes("Terminal") || s.name.includes("Transit Center");

      const icon = L.divIcon({
        className: "cta-stop-pin",
        html: isTerminal
          ? `<div style="
              width: 14px;
              height: 14px;
              border-radius: 50%;
              background: #ffffff;
              border: 3px solid ${color};
              box-shadow: 0 0 8px rgba(0,0,0,0.45);
              display: flex;
              align-items: center;
              justify-content: center;
              font-size: 8px;
              font-weight: 800;
              color: ${color};
              cursor: pointer;
            ">T</div>`
          : `<div style="
              width: 8px;
              height: 8px;
              border-radius: 50%;
              background: ${color};
              border: 1.5px solid #ffffff;
              box-shadow: 0 1px 3px rgba(0,0,0,0.4);
              cursor: pointer;
            "></div>`,
        iconSize: isTerminal ? [14, 14] : [8, 8],
        iconAnchor: isTerminal ? [7, 7] : [4, 4],
      });

      const marker = L.marker([s.lat, s.lon], { icon }).addTo(group);

      marker.bindPopup(`
        <div style="font-family: system-ui, -apple-system, sans-serif; min-width: 200px; padding: 2px;">
          <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 4px;">
            <strong style="color: #0f172a; font-size: 13px;">${s.name}</strong>
            ${isTerminal ? '<span style="background:#ecfdf5;color:#059669;font-size:10px;font-weight:700;padding:2px 6px;border-radius:4px;">TERMINAL</span>' : ""}
          </div>
          <div style="font-size: 11.5px; color: #475569; margin-bottom: 4px;">
            ${s.desc ? `<div>📍 ${s.desc}</div>` : ""}
            <div>🆔 CTA Stop ID: <strong>${s.stop_id}</strong></div>
            <div>🚌 Serving: <strong>${routeLabel}</strong></div>
            <div>♿ ADA: <strong>${s.wheelchair !== false ? "Accessible" : "Standard"}</strong></div>
          </div>
          <div style="font-size: 10px; color: #94a3b8; border-top: 1px solid #e2e8f0; padding-top: 4px; margin-top: 4px;">
            GPS: ${s.lat.toFixed(5)}, ${s.lon.toFixed(5)}
          </div>
        </div>
      `);
    };

    // A) Route explorer stops
    if (activeRouteGeo?.stops) {
      activeRouteGeo.stops.forEach((s) => {
        renderStop(s, activeRouteGeo.color || "#059669", `Route ${activeRouteGeo.route_id} (${activeRouteGeo.name})`);
      });
    }

    // B) Compare route stops
    if (compareRouteGeo?.stops) {
      compareRouteGeo.stops.forEach((s) => {
        renderStop(s, "#2563eb", `Route ${compareRouteGeo.route_id} (${compareRouteGeo.name})`);
      });
    }

    // C) Network overview: show major transit hubs across Chicago
    if (showAllRoutes && networkStops.length > 0) {
      networkStops.forEach((s) => {
        renderStop(s, "#0f766e", "CTA Transit Hub");
      });
    }
  }, [activeRouteGeo, compareRouteGeo, showAllRoutes, showStops, networkStops]);

  // 9. Render Live Vehicles (Real Data Feed from API)
  useEffect(() => {
    const group = vehiclesLayerRef.current;
    if (!group) return;

    group.clearLayers();
    if (!showLiveVehicles || liveVehicles.length === 0) return;

    liveVehicles.forEach((v) => {
      const color = v.color || "#059669";

      // Animated transit bus icon with heading bearing arrow
      const busIcon = L.divIcon({
        className: "cta-live-bus-marker",
        html: `
          <div style="
            position: relative;
            width: 24px;
            height: 24px;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
          ">
            <div style="
              position: absolute;
              width: 24px;
              height: 24px;
              border-radius: 50%;
              background: ${color};
              opacity: 0.25;
              animation: bus-pulse 2s infinite ease-out;
            "></div>
            <div style="
              width: 18px;
              height: 18px;
              border-radius: 50%;
              background: #0f172a;
              border: 2px solid #ffffff;
              display: flex;
              align-items: center;
              justify-content: center;
              box-shadow: 0 2px 6px rgba(0,0,0,0.5);
              transform: rotate(${v.bearing}deg);
            ">
              <span style="color:#ffffff; font-size:10px; line-height:1;">▲</span>
            </div>
          </div>
        `,
        iconSize: [24, 24],
        iconAnchor: [12, 12],
      });

      const marker = L.marker([v.lat, v.lon], { icon: busIcon }).addTo(group);

      marker.bindPopup(`
        <div style="font-family: system-ui, -apple-system, sans-serif; min-width: 220px; padding: 2px;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
            <strong style="color: #0f172a; font-size: 14px;">🚌 ${v.vehicle_id}</strong>
            <span style="background: #ecfdf5; color: #059669; font-size: 10px; font-weight: 700; padding: 2px 6px; border-radius: 4px;">
              ${v.status}
            </span>
          </div>
          <div style="font-size: 12px; color: #334155; line-height: 1.4;">
            <div>Route: <strong>Route ${v.route_id}</strong> (${v.route_name})</div>
            <div>Direction: <strong>${v.direction}</strong></div>
            <div>Speed: <strong>${v.speed_mph} mph</strong> · Heading: ${v.bearing}°</div>
            <div>Next Stop: <strong>${v.next_stop}</strong></div>
            <div>Occupancy: <span style="color: #047857; font-weight: 600;">${v.occupancy}</span></div>
          </div>
          <div style="font-size: 10px; color: #94a3b8; border-top: 1px solid #e2e8f0; padding-top: 4px; margin-top: 6px;">
            Live API Feed · Signal: ${v.updated_at}
          </div>
        </div>
      `);
    });
  }, [liveVehicles, showLiveVehicles]);

  return (
    <div style={{ position: "relative", width: "100%", height, borderRadius: 12, overflow: "hidden", border: "1px solid var(--card-border)" }}>
      {/* Map DOM Container */}
      <div ref={mapContainerRef} style={{ width: "100%", height: "100%" }} />

      {/* Floating Map Controls & Stats Overlay */}
      <div
        style={{
          position: "absolute",
          top: 12,
          right: 12,
          zIndex: 400,
          background: "rgba(255, 255, 255, 0.96)",
          backdropFilter: "blur(6px)",
          padding: "8px 14px",
          borderRadius: 8,
          boxShadow: "0 2px 10px rgba(0,0,0,0.15)",
          fontSize: 12,
          display: "flex",
          alignItems: "center",
          gap: 14,
          flexWrap: "wrap",
        }}
      >
        {activeRouteGeo && (
          <span style={{ fontWeight: 700, color: "var(--text-main)" }}>
            Route {activeRouteGeo.route_id} ({activeRouteGeo.name}) · {activeRouteGeo.stops?.length ?? 0} stops
          </span>
        )}

        {/* Live CTA Buses Toggle */}
        <label style={{ display: "flex", alignItems: "center", gap: 6, cursor: "pointer", fontWeight: 700, color: "#059669" }}>
          <input
            type="checkbox"
            checked={showLiveVehicles}
            onChange={(e) => setShowLiveVehicles(e.target.checked)}
            style={{ accentColor: "#059669" }}
          />
          🚌 Live Vehicles ({liveVehicles.length})
        </label>

        {/* Show Stops Toggle */}
        <label style={{ display: "flex", alignItems: "center", gap: 6, cursor: "pointer", fontWeight: 600 }}>
          <input
            type="checkbox"
            checked={showStops}
            onChange={(e) => setShowStops(e.target.checked)}
            style={{ accentColor: "#059669" }}
          />
          Show Stops
        </label>

        {/* Basemap Switcher (Free, NO API KEY) */}
        <select
          className="select-input"
          style={{ fontSize: 11, padding: "3px 8px" }}
          value={basemapStyle}
          onChange={(e: any) => setBasemapStyle(e.target.value)}
          title="Map Basemap Layer"
        >
          <option value="canvas">Transit Gray (Clean)</option>
          <option value="streets">City Streets (Esri)</option>
        </select>

        {loading && <span style={{ color: "#64748b" }}>Loading...</span>}
      </div>

      {/* Map Legend Overlay */}
      <div
        style={{
          position: "absolute",
          bottom: 12,
          left: 12,
          zIndex: 400,
          background: "rgba(255, 255, 255, 0.94)",
          backdropFilter: "blur(4px)",
          padding: "6px 12px",
          borderRadius: 6,
          boxShadow: "0 1px 5px rgba(0,0,0,0.12)",
          fontSize: 11,
          display: "flex",
          gap: 12,
          alignItems: "center",
        }}
      >
        <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <span style={{ width: 12, height: 3, background: "#059669", borderRadius: 2 }}></span>
          Trunk
        </span>
        <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <span style={{ width: 12, height: 3, background: "#0284c7", borderRadius: 2 }}></span>
          Neighborhood
        </span>
        <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <span style={{ width: 12, height: 3, background: "#7c3aed", borderRadius: 2 }}></span>
          Connector
        </span>
        <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <span style={{ width: 12, height: 3, background: "#d97706", borderRadius: 2 }}></span>
          Specialized
        </span>
        {showLiveVehicles && (
          <span style={{ display: "flex", alignItems: "center", gap: 4, fontWeight: 700, color: "#059669" }}>
            <span>▲</span> Live Bus Feed
          </span>
        )}
      </div>

      <style>{`
        @keyframes bus-pulse {
          0% { transform: scale(0.9); opacity: 0.6; }
          50% { transform: scale(1.6); opacity: 0; }
          100% { transform: scale(0.9); opacity: 0; }
        }
      `}</style>
    </div>
  );
}
