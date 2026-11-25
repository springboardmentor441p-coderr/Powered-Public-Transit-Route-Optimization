# AI_RouteRanker — Milestone 8: Backend API Integration
## Phase 8 Frontend-Backend API Integration Contract & TypeScript Definitions

**Project:** `D:\B.TECH_PROJECTS\AI_RouteRanker`  
**Milestone:** 8 — Backend API Integration  
**Document:** Frontend Integration Contract, Data Structures & TypeScript Types  
**Author:** AI_RouteRanker Engineering & Analytics Team  
**Date:** 2026-11-25T17:29:00+05:30  
**Target Client:** React 19 + TypeScript + Vite + Tailwind CSS (`frontend/`)  
**Status:** APPROVED INTEGRATION CONTRACT (PLANNING PHASE)  

---

## 1. Integration Scope & Client Architecture

The frontend client in `frontend/` utilizes **React 19**, **TypeScript**, **Tailwind CSS v4**, **Recharts**, and **Leaflet**. The Vite development server provides a built-in reverse proxy mapping `/api` requests to `http://127.0.0.1:8000`.

This contract establishes the formal data structures, TypeScript interfaces, error models, and component-ready schemas required by the frontend client to consume the backend APIs without type mismatches or runtime deserialization bugs.

---

## 2. Global TypeScript Interfaces & Models

The following TypeScript definitions will be placed in `frontend/src/types/api.ts` during frontend implementation:

```typescript
// =============================================================================
// AI_RouteRanker API Integration Contract - TypeScript Definitions
// =============================================================================

/** Standard API Error Response (RFC 7807 compliant) */
export interface ApiErrorResponse {
  error: {
    code: string;
    message: string;
    status: number;
    timestamp: string;
    details?: Record<string, unknown>;
  };
}

/** Standard Paginated Wrapper */
export interface PaginatedResponse<T> {
  total: number;
  offset: number;
  limit: number;
  items: T[];
}

/** Health Check Response */
export interface HealthResponse {
  status: 'ok' | 'degraded' | 'error';
  message: string;
  project: string;
  version: string;
  environment: string;
  timestamp: string;
}

// -----------------------------------------------------------------------------
// Route Directory Types
// -----------------------------------------------------------------------------

export interface RouteSummary {
  route_id: string;
  route_short_name: string;
  route_long_name: string;
  route_type: number; // 3 = Bus, 1 = Rail
  is_rail: boolean;
  operational_cluster: string;
  regional_partition: string;
  scheduled_trips: number;
  service_span_hours: number;
  am_headway_min: number | null;
  forecasted_daily_demand: number | null;
}

export interface RouteDetail {
  route_id: string;
  route_short_name: string;
  route_long_name: string;
  is_rail: boolean;
  operational: {
    scheduled_trips: number;
    service_span_hours: number;
    am_headway_min: number | null;
    route_length_km: number;
    unique_stops_count: number;
    operational_cluster: string;
  };
  demand: {
    historical_mean_daily_rides: number | null;
    forecasted_daily_demand: number | null;
    rides_per_trip: number | null;
    load_intensity_factor: number | null;
  };
  hubs: {
    hub_stop_count: number;
    hub_stop_ratio: number;
    hub_connectivity_index: number;
  };
  corridor: {
    max_corridor_overlap: number;
    corridor_duplication_index: number;
    shared_consecutive_stops: number;
  };
}

// -----------------------------------------------------------------------------
// Multi-Criteria Route Ranking Types
// -----------------------------------------------------------------------------

export interface RankingPillars {
  demand_score: number;
  service_score: number;
  hub_score: number;
  corridor_score: number;
}

export interface RankingContributions {
  forecasted_demand?: number;
  load_intensity?: number;
  scheduled_trips?: number;
  service_span?: number;
  am_headway?: number;
  hub_stop_ratio?: number;
  corridor_duplication?: number;
}

export interface BusRankingItem {
  rank: number;
  route_id: string;
  route_short_name: string;
  wsm_score: number;
  percentile_rank: number;
  topsis_score: number;
  topsis_rank: number;
  pillars: RankingPillars;
  contributions: RankingContributions;
  is_headway_missing: boolean;
}

export interface RailRankingItem {
  rank: number;
  route_id: string;
  route_short_name: string;
  wsm_score: number;
  topsis_score: number;
  scheduled_trips: number;
  service_span_hours: number;
  am_headway_min: number;
  corridor_duplication_index: number;
  pillars: RankingPillars;
}

export interface UnifiedRankingItem {
  rank: number;
  route_id: string;
  route_short_name: string;
  is_rail: boolean;
  wsm_score: number;
  topsis_score: number;
  scheduled_trips: number;
  service_span_hours: number;
  am_headway_min: number | null;
  corridor_duplication_index: number;
}

// -----------------------------------------------------------------------------
// Natural-Language Explanation Types
// -----------------------------------------------------------------------------

export interface FeatureDriver {
  criterion: string;
  feature_key: string;
  contribution: number;
  score: number;
}

export interface RouteExplanation {
  route_id: string;
  route_name: string;
  track: 'BUS_PRIORITY' | 'RAIL_PRIORITY' | 'UNIFIED_SUPPLY';
  profile: string;
  rank: number;
  total_routes: number;
  overall_score: number;
  narrative: string;
  top_positive_drivers: FeatureDriver[];
  top_negative_drivers: FeatureDriver[];
  is_headway_missing: boolean;
  missing_criteria: string[];
}

// -----------------------------------------------------------------------------
// Spatial Transit Hub Types (Leaflet Ready)
// -----------------------------------------------------------------------------

export interface TransitHubMarker {
  stop_id: string;
  stop_name: string;
  lat: number;
  lon: number;
  total_visits: number;
  routes_served_count: number;
  hub_importance_score: number;
  is_rail_station: boolean;
  hub_tier?: 'Top 10 Tier-1' | 'Top 50 Major' | 'Regional Connector';
}

// -----------------------------------------------------------------------------
// Sensitivity Analysis Types
// -----------------------------------------------------------------------------

export interface SensitivityScenario {
  scenario_id: string;
  track: string;
  target_criterion: string;
  delta: number; // e.g., -0.20, -0.10, +0.10, +0.20
  spearman_rho: number;
  mean_absolute_rank_shift: number;
  max_rank_shift: number;
  top_10_overlap: number;
  top_20_overlap: number;
}

// -----------------------------------------------------------------------------
// Historical Ridership Telemetry Types (Recharts Ready)
// -----------------------------------------------------------------------------

export interface RidershipDataPoint {
  year_month: string; // "2024-05"
  weekday_avg_rides: number;
  saturday_avg_rides: number;
  sunday_avg_rides: number;
  total_monthly_rides: number;
}

export interface RouteRidershipTimeSeries {
  route_id: string;
  route_name: string;
  data_points: RidershipDataPoint[];
}
```

---

## 3. UI State Management & Data Fetching Patterns

### 3.1 Standard Async State Pattern
Every client data-fetching hook must maintain an explicit four-state lifecycle:
```typescript
interface AsyncState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  status: 'idle' | 'loading' | 'success' | 'error';
}
```

### 3.2 Standard Error Handling & Fallbacks
- When an API call returns `404 Not Found` (e.g. invalid route), the UI displays a clean inline alert:  
  *"Route {id} does not exist in the canonical 133 CTA route roster. Please select a valid route."*
- When an API call returns `503 Service Unavailable`, the UI renders a non-blocking banner:  
  *"Analytics service is currently degraded or offline. Retrying in 5 seconds..."*

---

## 4. Chart-Ready & Map-Ready Format Specifications

### 4.1 Recharts Integration Formats
Recharts requires an array of homogeneous objects where keys correspond to line or bar data keys:
```json
[
  { "month": "2023-01", "Weekday": 17420, "Saturday": 9840, "Sunday": 7650 },
  { "month": "2023-02", "Weekday": 17850, "Saturday": 10120, "Sunday": 7890 }
]
```
The `/api/ridership/routes/{id}/timeseries` endpoint directly formats its response to this schema, avoiding runtime client-side mapping loops.

### 4.2 Leaflet / React-Leaflet Map Formats
Leaflet markers consume `[lat, lon]` tuples. The `/api/spatial/hubs/top` endpoint provides explicit `lat` and `lon` float coordinates:
```tsx
<MapContainer center={[41.8781, -87.6298]} zoom={12}>
  <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
  {hubs.map(hub => (
    <CircleMarker 
      key={hub.stop_id} 
      center={[hub.lat, hub.lon]} 
      radius={Math.max(4, hub.hub_importance_score * 12)}
    >
      <Popup>
        <strong>{hub.stop_name}</strong><br/>
        Routes Served: {hub.routes_served_count}<br/>
        Importance: {hub.hub_importance_score.toFixed(3)}
      </Popup>
    </CircleMarker>
  ))}
</MapContainer>
```
