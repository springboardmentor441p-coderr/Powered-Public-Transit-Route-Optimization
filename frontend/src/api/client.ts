const API_BASE = "http://localhost:8000/api";

export async function fetchCoverage() {
  const res = await fetch(`${API_BASE}/data/coverage`);
  return res.json();
}

export async function fetchRoutes() {
  const res = await fetch(`${API_BASE}/routes`);
  return res.json();
}

export async function fetchRouteHistory(route: string, cutoffDate?: string) {
  const q = cutoffDate ? `?cutoff_date=${encodeURIComponent(cutoffDate)}` : "";
  const res = await fetch(`${API_BASE}/routes/${encodeURIComponent(route)}/history${q}`);
  return res.json();
}

export async function fetchRankings(daytype: string) {
  const res = await fetch(`${API_BASE}/rankings?daytype=${daytype}`);
  return res.json();
}

export async function compareRoutes(routeA: string, routeB: string, daytype: string) {
  const res = await fetch(`${API_BASE}/routes/compare?route_a=${routeA}&route_b=${routeB}&daytype=${daytype}`);
  return res.json();
}

export async function requestForecast(route: string, targetDate: string, virtualDate: string) {
  const res = await fetch(`${API_BASE}/forecasts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ route, target_date: targetDate, virtual_date: virtualDate, reporting_delay_days: 1 }),
  });
  return res.json();
}

export async function createReplaySession() {
  const res = await fetch(`${API_BASE}/replays`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ start_date: "2026-06-01", end_date: "2026-07-31", reporting_delay_days: 1, speed_seconds: 5 }),
  });
  return res.json();
}

export async function controlReplaySession(sessionId: string, action: "start" | "pause" | "advance" | "reset") {
  const res = await fetch(`${API_BASE}/replays/${sessionId}/control`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action }),
  });
  return res.json();
}

export async function runServiceScenario(payload: {
  route: string;
  service_date: string;
  proposed_trips: number;
  demand_multiplier: number;
  assumed_trip_duration_minutes?: number;
}) {
  const res = await fetch(`${API_BASE}/scenarios`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return res.json();
}
