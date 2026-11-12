/**
 * RouteRanker API Service
 * Centralized client for Chicago Transit Authority (CTA) endpoints
 */

const API_BASE = '/api';

export async function fetchJson(endpoint, options = {}) {
  try {
    const res = await fetch(`${API_BASE}${endpoint}`, options);
    if (!res.ok) {
      const errBody = await res.json().catch(() => ({}));
      throw new Error(errBody.detail || `HTTP Error ${res.status}: ${res.statusText}`);
    }
    return await res.json();
  } catch (error) {
    console.error(`API Error [${endpoint}]:`, error);
    throw error;
  }
}

// Transit & Live API
export const getTransitStatus = () => fetchJson('/transit/status');
export const getActiveAlerts = (routeId = null) => 
  fetchJson(`/transit/alerts${routeId ? `?route_id=${encodeURIComponent(routeId)}` : ''}`);
export const getBusVehicles = (routeId = '79') => 
  fetchJson(`/transit/bus/vehicles?route_id=${encodeURIComponent(routeId)}`);
export const getTrainPositions = (line = 'Red') => 
  fetchJson(`/transit/train/positions?line=${encodeURIComponent(line)}`);
export const getBusRoutes = () => fetchJson('/transit/bus/routes');
export const getRailStations = () => fetchJson('/transit/stations');

// Demand Forecasting API
export const getSystemForecast = (horizonDays = 14) => 
  fetchJson(`/forecast/system?horizon_days=${horizonDays}`);
export const getRouteForecast = (routeId, horizonDays = 7) => 
  fetchJson(`/forecast/route?route_id=${encodeURIComponent(routeId)}&horizon_days=${horizonDays}`);
export const getModelMetrics = () => fetchJson('/forecast/metrics');

// Route Planning API
export const searchLocations = (query) => 
  fetchJson(`/route/locations?query=${encodeURIComponent(query)}`);
export const planRoute = (origin, destination, optimizeFor = 'duration', maxTransfers = 3) => 
  fetchJson(`/route/plan?origin=${encodeURIComponent(origin)}&destination=${encodeURIComponent(destination)}&optimize_for=${optimizeFor}&max_transfers=${maxTransfers}`);

// Smart Recommendations Simulation API
export const simulateScenario = (routeId, proposedTrips) => 
  fetchJson(`/recommendations/simulate?route_id=${encodeURIComponent(routeId)}&proposed_trips=${proposedTrips}`);

// Analytics API
export const getRoutePerformance = (limit = 25) => 
  fetchJson(`/analytics/routes?limit=${limit}`);
export const getStationPerformance = (limit = 25) => 
  fetchJson(`/analytics/stations?limit=${limit}`);
export const getNetworkConnectivity = () => 
  fetchJson('/analytics/network');
export const getHistoricalTrend = (days = 60) => 
  fetchJson(`/analytics/historical-trend?days=${days}`);

// Technical Specification v3.8 Extensions: Route Groups, Productivity Rankings, Replays & Manifest
export const getRouteClusters = () => 
  fetchJson('/route-groups');
export const getRouteProductivityRankings = (dayType = 'W', sortBy = 'rides_per_scheduled_hour') => 
  fetchJson(`/rankings?day_type=${dayType}&sort_by=${sortBy}`);
export const createReplaySession = (reportingDelayDays = 1, playbackSpeedSec = 5) => 
  fetchJson(`/replays?reporting_delay_days=${reportingDelayDays}&playback_speed_sec=${playbackSpeedSec}`, { method: 'POST' });
export const getReplayState = (sessionId, focusRoute = '79') => 
  fetchJson(`/replays/${sessionId}?focus_route=${encodeURIComponent(focusRoute)}`);
export const controlReplaySession = (sessionId, action, targetDate = null) => 
  fetchJson(`/replays/${sessionId}/control?action=${action}${targetDate ? `&target_date=${targetDate}` : ''}`, { method: 'POST' });
export const getSourceManifest = () => 
  fetchJson('/data/manifest');


