import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "../styles.css";

const CITY_GEOJSON = "https://data.cityofchicago.org/api/v3/views/6uva-a5ei/query.geojson?accessType=DOWNLOAD";
const CITY_GEOJSON_FALLBACK = "https://data.cityofchicago.org/resource/6uva-a5ei.geojson?$limit=5000";
const COUNTY_GEOJSON = "https://gis12.cookcountyil.gov/traditional/rest/services/publicTransit/MapServer/1/query?where=1%3D1&outFields=*&outSR=4326&f=geojson";

async function api(path, options = {}) {
  const response = await fetch(path, { headers: { Accept: "application/json", ...(options.headers || {}) }, ...options });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || `Request failed (${response.status})`);
  return body;
}

function routeName(feature) {
  const props = feature.properties || {};
  return String(props.route ?? props.ROUTE ?? props.route_number ?? props.route_num ?? props.route_short_name ?? props.rt ?? props.name ?? props.NAME ?? "");
}

function getDemandColor(value, low, high) {
  const t = Math.max(0, Math.min(1, high > low ? (value - low) / (high - low) : 0.5));
  const rgb = [40 + 210 * t, 150 - 90 * t, 220 - 190 * t].map(Math.round);
  return `rgb(${rgb.join(",")})`;
}

function MapCanvas({ geometry, selectedRoute, demand, demandMode, vehicles, onRouteSelect }) {
  const elementRef = useRef(null);
  const mapRef = useRef(null);
  const routeLayerRef = useRef(null);
  const vehicleLayerRef = useRef(null);

  useEffect(() => {
    if (!elementRef.current || mapRef.current) return undefined;
    const map = L.map(elementRef.current, { zoomControl: false, preferCanvas: true }).setView([41.8781, -87.6298], 10);
    L.control.zoom({ position: "bottomright" }).addTo(map);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    }).addTo(map);
    vehicleLayerRef.current = L.layerGroup().addTo(map);
    mapRef.current = map;
    return () => { map.remove(); mapRef.current = null; };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !geometry) return;
    if (routeLayerRef.current) map.removeLayer(routeLayerRef.current);
    const values = Object.values(demand || {});
    const low = values.length ? Math.min(...values) : 0;
    const high = values.length ? Math.max(...values) : 0;
    const layer = L.geoJSON(geometry, {
      style: (feature) => {
        const route = routeName(feature);
        if (demandMode && demand) {
          const value = demand[route];
          if (value == null) return { color: "#cbd4cf", weight: 1.5, opacity: 0.45 };
          const t = high > low ? (value - low) / (high - low) : 0.5;
          return { color: getDemandColor(value, low, high), weight: 2 + 4 * t, opacity: 0.9 };
        }
        return route === selectedRoute
          ? { color: "#087b63", weight: 5, opacity: 0.98 }
          : { color: "#71837a", weight: 1.6, opacity: 0.35 };
      },
      onEachFeature: (feature, featureLayer) => {
        const route = routeName(feature);
        const mean = demand?.[route];
        const demandText = mean == null ? "No matched ridership summary" : `${Math.round(mean).toLocaleString()} mean boardings / observed day`;
        featureLayer.bindTooltip(`Route ${route}<br>${demandText}`, { sticky: true, opacity: 0.95 });
        featureLayer.on("click", () => onRouteSelect(route));
      },
    }).addTo(map);
    routeLayerRef.current = layer;
    const bounds = layer.getBounds();
    if (bounds.isValid()) map.fitBounds(bounds.pad(0.04), { maxZoom: 12 });
  }, [geometry, selectedRoute, demand, demandMode, onRouteSelect]);

  useEffect(() => {
    const group = vehicleLayerRef.current;
    if (!group) return;
    group.clearLayers();
    vehicles.forEach((bus) => {
      const lat = Number(bus.lat);
      const lon = Number(bus.lon);
      if (!Number.isFinite(lat) || !Number.isFinite(lon)) return;
      L.circleMarker([lat, lon], { radius: 6, color: "#fff", weight: 2, fillColor: "#eb742f", fillOpacity: 1 })
        .bindPopup(`<strong>Route ${bus.rt || ""}</strong><br>${bus.des || "CTA bus"}<br>Vehicle ${bus.vid || "—"}`)
        .addTo(group);
    });
  }, [vehicles]);

  return <div id="map" ref={elementRef} role="application" aria-label="Interactive map of Chicago CTA bus routes" />;
}

function App() {
  const [view, setView] = useState("map");
  const [geometry, setGeometry] = useState(null);
  const [geometryError, setGeometryError] = useState("");
  const [geometrySource, setGeometrySource] = useState("Loading map data");
  const [mapAttempt, setMapAttempt] = useState(0);
  const [routeNames, setRouteNames] = useState([]);
  const [selectedRoute, setSelectedRoute] = useState("1");
  const [demand, setDemand] = useState(null);
  const [demandPeriod, setDemandPeriod] = useState("");
  const [sourceLatest, setSourceLatest] = useState("");
  const [demandError, setDemandError] = useState("");
  const [demandMode, setDemandMode] = useState(false);
  const [liveEnabled, setLiveEnabled] = useState(false);
  const [vehicles, setVehicles] = useState([]);
  const [liveStatus, setLiveStatus] = useState("Turn on to request current bus locations. Requires a server-side CTA API key.");
  const [liveTimestamp, setLiveTimestamp] = useState("");
  const [model, setModel] = useState(null);
  const [modelError, setModelError] = useState("");
  const [targetDate, setTargetDate] = useState("");
  const [dayType, setDayType] = useState("W");
  const [forecast, setForecast] = useState(null);
  const [forecastError, setForecastError] = useState("");
  const [forecastLoading, setForecastLoading] = useState(false);
  const [scenarioRows, setScenarioRows] = useState([{ route: "1", predicted_rides: "", scheduled_trips: "" }]);
  const [scenarioShift, setScenarioShift] = useState(10);
  const [scenarioResult, setScenarioResult] = useState(null);
  const [scenarioError, setScenarioError] = useState("");
  const chooseRoute = useCallback((route) => {
    if (routeNames.includes(route)) setSelectedRoute(route);
  }, [routeNames]);

  const applyGeometry = useCallback((data, source) => {
    if (data?.type !== "FeatureCollection" || !Array.isArray(data.features)) throw new Error("Expected a GeoJSON FeatureCollection.");
    const features = data.features.filter((feature) => ["LineString", "MultiLineString"].includes(feature.geometry?.type) && routeName(feature));
    if (!features.length) throw new Error("No route line features were found in this GeoJSON.");
    const cleanData = { ...data, features };
    const names = [...new Set(features.map(routeName))].sort((a, b) => a.localeCompare(b, undefined, { numeric: true }));
    setGeometry(cleanData);
    setRouteNames(names);
    setSelectedRoute((current) => names.includes(current) ? current : names[0]);
    setGeometrySource(source);
    setGeometryError("");
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function loadGeometry() {
      try {
        const data = await api("/api/v1/map/geometry");
        if (!cancelled) applyGeometry(data, data.source_metadata?.label || "Official route geometry");
      } catch (apiError) {
        let loaded = false;
        let browserError = null;
        for (const url of [CITY_GEOJSON, CITY_GEOJSON_FALLBACK, COUNTY_GEOJSON]) {
          try {
            const response = await fetch(url);
            if (!response.ok) throw new Error(`City portal returned ${response.status}`);
            const data = await response.json();
            if (!cancelled) applyGeometry(data, url === COUNTY_GEOJSON ? "Cook County CTA route layer · browser-loaded" : "City of Chicago route geometry · browser-loaded");
            loaded = true;
            break;
          } catch (error) { browserError = error; }
        }
        if (!loaded) {
          if (!cancelled) {
            setGeometryError(`Could not reach the City route data service${browserError ? ` (${browserError.message})` : ""}. Retry, or download the official GeoJSON and load it below.`);
            setGeometrySource("Map data unavailable");
            console.error("Route geometry unavailable", apiError, browserError);
          }
        }
      }
    }
    async function loadDemand() {
      try {
        const result = await api("/api/v1/map/demand");
        if (cancelled) return;
        if (result.available) {
          setDemand(result.mean_daily_boardings);
          setDemandPeriod(`${result.period_start} to ${result.period_end}`);
          setSourceLatest(result.source_latest_date || "");
          if (result.source_latest_date) {
            const earliestAllowed = new Date(`${result.source_latest_date}T00:00:00Z`);
            earliestAllowed.setUTCDate(earliestAllowed.getUTCDate() + 1);
            const tomorrow = new Date();
            tomorrow.setDate(tomorrow.getDate() + 1);
            const defaultDate = new Date(Math.max(earliestAllowed.getTime(), tomorrow.getTime()));
            setTargetDate(`${defaultDate.getFullYear()}-${String(defaultDate.getMonth() + 1).padStart(2, "0")}-${String(defaultDate.getDate()).padStart(2, "0")}`);
          }
        } else setDemandError(result.detail || "Ridership data is not configured on this server.");
      } catch (error) { if (!cancelled) setDemandError(error.message); }
    }
    async function loadModel() {
      try { const result = await api("/api/v1/forecasts/model"); if (!cancelled) setModel(result); }
      catch (error) { if (!cancelled) setModelError(error.message); }
    }
    loadGeometry(); loadDemand(); loadModel();
    return () => { cancelled = true; };
  }, [applyGeometry, mapAttempt]);

  const refreshVehicles = useCallback(async () => {
    if (!selectedRoute) return;
    setLiveStatus("Requesting current CTA bus positions…");
    try {
      const result = await api(`/api/v1/map/vehicles?routes=${encodeURIComponent(selectedRoute)}`);
      setVehicles(result.vehicles || []);
      setLiveTimestamp(result.timestamp || "Time unavailable");
      setLiveStatus(result.vehicles?.length ? `Current vehicle positions for route ${selectedRoute}.` : "No active buses returned for this route.");
    } catch (error) {
      setVehicles([]);
      setLiveStatus(error.message.includes("server secrets")
        ? "Live locations need a CTA Bus Tracker key configured on this web server."
        : `Live positions unavailable: ${error.message}`);
    }
  }, [selectedRoute]);

  useEffect(() => {
    if (!liveEnabled) { setVehicles([]); return undefined; }
    refreshVehicles();
    const timer = setInterval(refreshVehicles, 30000);
    return () => clearInterval(timer);
  }, [liveEnabled, refreshVehicles]);

  const selectedTest = useMemo(() => {
    if (!model) return null;
    const name = model.model_selection.paired_matched_validation_winner;
    return { name, metrics: model.paired_test[name], baseline: model.paired_test.past_four_same_weekdays };
  }, [model]);

  async function onGeoJsonChange(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    try { applyGeometry(JSON.parse(await file.text()), `Local file · ${file.name}`); }
    catch (error) { setGeometryError(error.message); }
  }

  async function submitForecast(event) {
    event.preventDefault();
    setForecast(null);
    setForecastError("");
    setForecastLoading(true);
    try {
      const result = await api("/api/v1/forecasts/predict-one", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ route: selectedRoute, date: targetDate, daytype: dayType }),
      });
      setForecast(result);
    } catch (error) { setForecastError(error.message); }
    finally { setForecastLoading(false); }
  }

  async function submitScenario(event) {
    event.preventDefault();
    setScenarioResult(null);
    setScenarioError("");
    const routes = scenarioRows.map((row) => ({
      route: row.route,
      predicted_rides: Number(row.predicted_rides),
      scheduled_trips: Number(row.scheduled_trips),
    }));
    try {
      const result = await api("/api/v1/scenarios/rebalance-trips", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ routes, max_shift_pct: scenarioShift / 100 }),
      });
      setScenarioResult(result);
    } catch (error) { setScenarioError(error.message); }
  }

  const improvement = selectedTest?.baseline?.mae
    ? 100 * (selectedTest.baseline.mae - selectedTest.metrics.mae) / selectedTest.baseline.mae : null;
  const historyAgeDays = sourceLatest ? Math.floor((Date.now() - Date.parse(`${sourceLatest}T00:00:00`)) / 86400000) : null;

  return <div className="shell">
    <header className="topbar">
      <a className="brand" href="#map" aria-label="RouteRanker home"><span className="brand-mark">R</span><span>Route<span className="brand-light">Ranker</span><small>CHICAGO · CTA BUS NETWORK</small></span></a>
      <nav className="nav-tabs" aria-label="Main navigation">
        <button className={`nav-tab ${view === "map" ? "active" : ""}`} onClick={() => setView("map")}>Network map</button>
        <button className={`nav-tab ${view === "forecast" ? "active" : ""}`} onClick={() => setView("forecast")}>One-day forecast</button>
        <button className={`nav-tab ${view === "scenario" ? "active" : ""}`} onClick={() => setView("scenario")}>Scenario</button>
        <button className={`nav-tab ${view === "model" ? "active" : ""}`} onClick={() => setView("model")}>Model evidence</button>
      </nav>
      <div className="top-status"><span className={`status-dot ${geometry ? "ready" : ""}`} /><span>{geometry ? "Route map ready" : geometryError ? "Map source unavailable" : "Loading map"}</span></div>
    </header>

    {view === "map" ? <main className="view active">
      <div className="page-heading"><div><p className="eyebrow">TRANSIT PLANNING WORKSPACE</p><h1>Chicago bus network</h1><p className="subhead">Explore route geography, observed demand, and current bus locations.</p></div><div className="updated-chip"><span className="pulse" />{geometrySource}</div></div>
      <div className="map-layout">
        <section className="map-card" aria-label="Interactive CTA route map">
          <MapCanvas geometry={geometry} selectedRoute={selectedRoute} demand={demand} demandMode={demandMode} vehicles={vehicles} onRouteSelect={chooseRoute} />
          {geometryError && <div className="map-message error"><strong>Route map unavailable</strong><span>{geometryError}</span><button className="button secondary" onClick={() => setMapAttempt((attempt) => attempt + 1)}>Retry map</button><a href={CITY_GEOJSON} target="_blank" rel="noreferrer">Open official route GeoJSON</a><label className="button secondary" htmlFor="geojson-upload">Load downloaded GeoJSON</label></div>}
          {!geometry && !geometryError && <div className="map-message">Loading CTA route network…</div>}
          <div className="map-attribution">Static route geometry · current bus markers shown separately</div>
        </section>
        <aside className="control-panel">
          <div className="panel-title"><div><p className="eyebrow">MAP CONTROLS</p><h2>Route layers</h2></div><span className="route-count">{routeNames.length || "—"} routes</span></div>
          <label className="field-label" htmlFor="route-select">Highlight route</label>
          <select id="route-select" value={selectedRoute} disabled={!routeNames.length} onChange={(e) => setSelectedRoute(e.target.value)}>
            {routeNames.length ? routeNames.map((route) => <option key={route} value={route}>Route {route}</option>) : <option>Loading routes…</option>}
          </select>
          <div className="segmented" role="group" aria-label="Route map coloring">
            <button className={`segment ${!demandMode ? "active" : ""}`} onClick={() => setDemandMode(false)}>Route</button>
            <button className={`segment ${demandMode ? "active" : ""}`} disabled={!demand} onClick={() => setDemandMode(true)}>Demand</button>
          </div>
          {demandMode ? <div className="legend"><span>Lower</span><i /><span>Higher</span><small>Mean boardings per observed day</small></div> : <p className="helper-text">Route colors identify the selected route.</p>}
          {demandError && <p className="helper-text">{demandError}</p>}
          {demandPeriod && demandMode && <p className="helper-text">Averages {demandPeriod}.</p>}

          <div className="panel-divider" />
          <div className="live-header"><div><p className="eyebrow">CTA BUS TRACKER</p><h3>Live bus positions</h3></div><label className="switch"><input type="checkbox" checked={liveEnabled} onChange={(e) => setLiveEnabled(e.target.checked)} /><span /></label></div>
          <p className="helper-text">{liveStatus}</p>
          {liveEnabled && <button className="button secondary" onClick={refreshVehicles}>Refresh locations</button>}
          {liveEnabled && <div className="live-summary"><strong>{vehicles.length}</strong><span>buses on selected route</span><small>CTA feed: {liveTimestamp}</small></div>}
          <div className="panel-divider" />
          <div className="source-footer"><span className="source-icon">↗</span><span>Route paths · {geometrySource.includes("Cook County") ? <a href="https://gis12.cookcountyil.gov/traditional/rest/services/publicTransit/MapServer/layers" target="_blank" rel="noreferrer">Cook County CTA route layer</a> : <a href="https://data.cityofchicago.org/Transportation/CTA-Bus-Routes/6uva-a5ei" target="_blank" rel="noreferrer">City of Chicago Open Data</a>}</span></div>
          <a className="upload-link" href={CITY_GEOJSON} target="_blank" rel="noreferrer">Download route GeoJSON</a>
          <label className="upload-link" htmlFor="geojson-upload">Use a local GeoJSON file instead</label>
          <input id="geojson-upload" className="visually-hidden" type="file" accept=".json,.geojson,application/geo+json,application/json" onChange={onGeoJsonChange} />
        </aside>
      </div>
      <div className="info-strip"><span className="info-icon">i</span><p>Demand shading summarizes route-level boardings over the latest 84 days in the supplied ridership file. It does not represent passenger load on individual road segments. Bus markers are near-real-time vehicle positions, not general road traffic.</p></div>
    </main> : view === "forecast" ? <main className="view active">
      <div className="page-heading"><div><p className="eyebrow">SAVED MODEL INFERENCE</p><h1>One-day route forecast</h1><p className="subhead">Predict measured boardings for a single route and service date using server-configured history.</p></div></div>
      <div className="forecast-layout">
        <form className="content-card forecast-form" onSubmit={submitForecast}>
          <label className="field-label" htmlFor="forecast-route">CTA bus route</label>
          {routeNames.length ? <select id="forecast-route" value={selectedRoute} onChange={(event) => setSelectedRoute(event.target.value)}>{routeNames.map((route) => <option key={route} value={route}>Route {route}</option>)}</select> : <input id="forecast-route" aria-label="CTA route number" value={selectedRoute} onChange={(event) => setSelectedRoute(event.target.value)} required />}
          <label className="field-label" htmlFor="forecast-date">Forecast date</label>
          <input id="forecast-date" type="date" value={targetDate} min={sourceLatest ? new Date(new Date(`${sourceLatest}T00:00:00Z`).getTime() + 86400000).toISOString().slice(0, 10) : undefined} onChange={(event) => setTargetDate(event.target.value)} required />
          <label className="field-label" htmlFor="forecast-daytype">CTA service day type</label>
          <select id="forecast-daytype" value={dayType} onChange={(event) => setDayType(event.target.value)}><option value="W">Weekday</option><option value="A">Saturday</option><option value="U">Sunday / holiday</option></select>
          <p className="helper-text">History and the trained model are loaded from this server. The target must be after the reporting-delay cutoff.</p>
          {sourceLatest && historyAgeDays > 7 && <p className="caveat">The configured ridership file ends {sourceLatest} ({historyAgeDays} days ago). Update the server’s CTA_RIDERSHIP_CSV before treating a forecast as current.</p>}
          <button className="button primary" type="submit" disabled={!targetDate || !routeNames.length || forecastLoading}>{forecastLoading ? "Calculating…" : "Generate forecast"}</button>
          {forecastError && <p className="error-text">{forecastError}</p>}
          {forecast && <div className="forecast-result"><p className="eyebrow">PREDICTED DAILY BOARDINGS</p><strong>{Math.round(forecast.prediction.predicted_rides).toLocaleString()}</strong><span>Route {forecast.prediction.route} · {forecast.prediction.date} · {forecast.prediction.daytype === "W" ? "Weekday" : forecast.prediction.daytype === "A" ? "Saturday" : "Sunday / holiday"}</span><small>{forecast.model} · history through {forecast.history_latest_date}</small></div>}
        </form>
        <article className="content-card forecast-context"><p className="eyebrow">FORECAST CONTEXT</p><h2>One date at a time</h2><p>The saved model uses the server’s ridership history through its permitted reporting cutoff. For a later forecast, new eligible ridership data must be available to the server.</p><p className="caveat">A route-level daily boarding forecast is not passenger load, crowding, vehicle occupancy, or a service-change recommendation.</p><a className="text-link" href="/docs" target="_blank" rel="noreferrer">Forecast API documentation →</a></article>
      </div>
    </main> : view === "scenario" ? <main className="view active">
      <div className="page-heading"><div><p className="eyebrow">BOUNDED PLANNING SANDBOX</p><h1>Trip allocation scenario</h1><p className="subhead">Compare a trip-neutral allocation using route-level demand estimates and daily scheduled trips.</p></div></div>
      <div className="scenario-layout">
        <form className="content-card scenario-form" onSubmit={submitScenario}>
          <div className="scenario-form-head"><div><p className="eyebrow">INPUTS</p><h2>Routes and daily service</h2></div><button className="button secondary" type="button" onClick={() => setScenarioRows((rows) => [...rows, { route: routeNames.find((route) => !rows.some((row) => row.route === route)) || "", predicted_rides: "", scheduled_trips: "" }])} disabled={!routeNames.some((route) => !scenarioRows.some((row) => row.route === route))}>Add route</button></div>
          <div className="scenario-table-wrap"><table className="scenario-table"><thead><tr><th>Route</th><th>Predicted boardings/day</th><th>Scheduled trips/day</th><th /></tr></thead><tbody>{scenarioRows.map((row, index) => <tr key={`${index}-${row.route}`}>
            <td>{routeNames.length ? <select aria-label={`Scenario route ${index + 1}`} value={row.route} onChange={(event) => setScenarioRows((rows) => rows.map((item, i) => i === index ? { ...item, route: event.target.value } : item))}>{routeNames.map((route) => <option key={route} value={route}>Route {route}</option>)}{!routeNames.includes(row.route) && <option value={row.route}>{row.route || "Choose route"}</option>}</select> : <input aria-label={`Scenario route ${index + 1}`} value={row.route} onChange={(event) => setScenarioRows((rows) => rows.map((item, i) => i === index ? { ...item, route: event.target.value } : item))} required />}</td>
            <td><input aria-label={`Predicted boardings for route ${row.route}`} type="number" min="0" step="1" value={row.predicted_rides} onChange={(event) => setScenarioRows((rows) => rows.map((item, i) => i === index ? { ...item, predicted_rides: event.target.value } : item))} required /></td>
            <td><input aria-label={`Scheduled trips for route ${row.route}`} type="number" min="1" step="1" value={row.scheduled_trips} onChange={(event) => setScenarioRows((rows) => rows.map((item, i) => i === index ? { ...item, scheduled_trips: event.target.value } : item))} required /></td>
            <td><button className="remove-row" aria-label={`Remove route ${row.route}`} type="button" onClick={() => setScenarioRows((rows) => rows.filter((_, i) => i !== index))} disabled={scenarioRows.length < 2}>×</button></td>
          </tr>)}</tbody></table></div>
          <label className="field-label" htmlFor="shift-bound">Maximum trip shift per route <strong>{scenarioShift}%</strong></label>
          <input id="shift-bound" type="range" min="0" max="50" step="5" value={scenarioShift} onChange={(event) => setScenarioShift(Number(event.target.value))} />
          <button className="button primary" type="submit" disabled={scenarioRows.length < 1}>Calculate bounded scenario</button>
          {scenarioError && <p className="error-text">{scenarioError}</p>}
        </form>
        <article className="content-card scenario-notes"><p className="eyebrow">MODEL LIMITS</p><h2>A screening scenario</h2><p>The calculator holds the total number of trips fixed and bounds changes by route. It minimizes the highest aggregate boardings-per-trip ratio.</p><p className="caveat">Boardings divided by trips is not passenger load or crowding. This omits fleet, crew, travel time, accessibility, equity, transfers, and route overlap. It is not an automatic service recommendation.</p></article>
      </div>
      {scenarioResult && <section className="scenario-output"><div className="scenario-results-heading"><div><p className="eyebrow">SCENARIO RESULTS</p><h2>Trip-neutral comparison</h2></div><span className="route-count">{scenarioResult.scenario_total_trips.toLocaleString()} total trips · unchanged</span></div>
        <div className="metric-grid"><Metric label="Current highest ratio" value={scenarioResult.current_max_boardings_per_trip.toFixed(1)} note="boardings per scheduled trip"/><Metric label="Scenario highest ratio" value={scenarioResult.scenario_max_boardings_per_trip.toFixed(1)} note="aggregate proxy, not vehicle load"/><Metric label="Current mean route ratio" value={scenarioResult.current_mean_route_boardings_per_trip.toFixed(1)} note="boardings per scheduled trip"/><Metric label="Scenario mean route ratio" value={scenarioResult.scenario_mean_route_boardings_per_trip.toFixed(1)} note="bounded, trip-neutral scenario"/></div>
        <div className="content-card scenario-table-wrap"><table className="scenario-table results-table"><thead><tr><th>Route</th><th>Current trips</th><th>Scenario trips</th><th>Change</th><th>Boardings/current trip</th><th>Boardings/scenario trip</th></tr></thead><tbody>{scenarioResult.routes.map((row) => <tr key={row.route}><td>Route {row.route}</td><td>{row.current_scheduled_trips}</td><td>{row.scenario_scheduled_trips}</td><td>{row.trip_change > 0 ? "+" : ""}{row.trip_change}</td><td>{row.boardings_per_current_trip.toFixed(1)}</td><td>{row.boardings_per_scenario_trip.toFixed(1)}</td></tr>)}</tbody></table></div>
      </section>}
    </main> : <main className="view active">
      <div className="page-heading"><div><p className="eyebrow">EVALUATION SUMMARY</p><h1>Model evidence</h1><p className="subhead">A transparent snapshot of the trained model and its measured test performance.</p></div></div>
      {selectedTest ? <>
        <div className="metric-grid">
          <Metric label="Test MAE" value={selectedTest.metrics.mae.toFixed(1)} note="rides per route-day" />
          <Metric label="Test WAPE" value={`${(selectedTest.metrics.wape * 100).toFixed(2)}%`} note="weighted absolute percentage error" />
          <Metric label="Compared route-days" value={Number(selectedTest.metrics.rows).toLocaleString()} note="matched test observations" />
          <Metric label="Vs. seasonal baseline" value={`${improvement.toFixed(1)}%`} note="lower MAE than past-four-weekday baseline" />
        </div>
        <div className="content-grid">
          <article className="content-card"><p className="eyebrow">SELECTED MODEL</p><h2>{selectedTest.name.replaceAll("_", " ")}</h2><p className="subhead">Validation-selected demand-only Random Forest model.</p><dl className="detail-list"><dt>Training cutoff</dt><dd>{model.artifact_training?.training_cutoff || "Unavailable"}</dd><dt>Training examples</dt><dd>{model.artifact_training?.training_rows ? Number(model.artifact_training.training_rows).toLocaleString() : "Unavailable"}</dd><dt>Forecast target</dt><dd>Daily boardings by route</dd><dt>Model available to API</dt><dd>{model.model_artifact_configured ? "Yes" : "No — configure the model artifact on the server"}</dd></dl></article>
          <article className="content-card"><p className="eyebrow">INTERPRETATION</p><h2>Measured daily boardings</h2><p>The forecast target is the number of reported boardings for one route on one service day. The model does not estimate onboard occupancy, crowding, lateness, road congestion, or service quality.</p><p className="caveat">{model.source?.matches_mentor_reference ? "The evaluation source matches the mentor's frozen dataset." : "The evaluation used the supplied export, not the mentor's frozen CSV. Treat these scores as development evidence."}</p><a className="text-link" href="/docs" target="_blank" rel="noreferrer">Explore the forecast API documentation →</a></article>
        </div>
        <p className="page-footnote">The June–July evaluation window was inspected during development. Scores are development evidence, not a fresh blind test.</p>
      </> : <div className="metric-card loading-card">{modelError || "Loading evaluation…"}</div>}
    </main>}
    <footer><span>RouteRanker</span><span>Research prototype · CTA bus boardings</span></footer>
  </div>;
}

function Metric({ label, value, note }) {
  return <article className="metric-card"><span>{label}</span><strong>{value}</strong><small>{note}</small></article>;
}

createRoot(document.getElementById("root")).render(<React.StrictMode><App /></React.StrictMode>);
