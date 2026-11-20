const API_BASE = "http://localhost:8000/api";

function authHeaders(): Record<string, string> {
  const token = localStorage.getItem("rr_token");
  if (token) return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
  return { "Content-Type": "application/json" };
}

export async function login(username: string, password: string) {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) throw new Error("Invalid credentials");
  const data = await res.json();
  localStorage.setItem("rr_token", data.access_token);
  localStorage.setItem("rr_user", JSON.stringify(data.user));
  return data;
}

export function logout() {
  localStorage.removeItem("rr_token");
  localStorage.removeItem("rr_user");
}

export function getStoredUser() {
  const u = localStorage.getItem("rr_user");
  return u ? JSON.parse(u) : null;
}

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

export async function fetchAlerts() {
  const res = await fetch(`${API_BASE}/alerts`);
  return res.json();
}

export async function acknowledgeAlert(alertId: string) {
  const res = await fetch(`${API_BASE}/alerts/${alertId}/acknowledge`, {
    method: "POST",
    headers: authHeaders(),
  });
  return res.json();
}

export async function fetchBroadcasts() {
  const res = await fetch(`${API_BASE}/broadcasts`);
  return res.json();
}

export async function createBroadcast(payload: { title: string; message: string; severity: string; affected_routes: string[] }) {
  const res = await fetch(`${API_BASE}/broadcasts`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Failed to create broadcast (Admin/Operator required)");
  return res.json();
}

export async function deactivateBroadcast(broadcastId: string) {
  const res = await fetch(`${API_BASE}/broadcasts/${broadcastId}/deactivate`, {
    method: "POST",
    headers: authHeaders(),
  });
  return res.json();
}

export async function fetchHeatmapData(daytype: string) {
  const res = await fetch(`${API_BASE}/heatmap?daytype=${daytype}`);
  return res.json();
}

export async function createScheduleUpdate(payload: { route: string; service_date: string; new_scheduled_trips: number; reason: string }) {
  const res = await fetch(`${API_BASE}/schedule-updates`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Failed to update schedule (Admin/Operator required)");
  return res.json();
}

export async function fetchScheduleUpdates() {
  const res = await fetch(`${API_BASE}/schedule-updates`);
  return res.json();
}

export async function fetchNotifications() {
  const res = await fetch(`${API_BASE}/notifications`);
  return res.json();
}
