import type {
  ClusterSummaryResponse,
  CorridorClusterListResponse,
  HealthCheckResponse,
  HistoricalForecastResponse,
  HistoricalForecastSummaryResponse,
  RankingListResponse,
  RidershipTimeseriesResponse,
  RouteCoRoutingResponse,
  RouteDetailResponse,
  RouteExplanationResponse,
  RouteListResponse,
  SensitivityListResponse,
  SpatialHubsListResponse,
  TopHubsResponse,
} from "../types/api";

const rawBase = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "";
export const API_BASE_URL = rawBase.replace(/\/+$/, "");

export class ApiClientError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(message: string, status = 0, code = "NETWORK_ERROR") {
    super(message);
    this.name = "ApiClientError";
    this.status = status;
    this.code = code;
  }
}

type QueryValue = string | number | boolean | undefined | null;

function buildQuery(params?: Record<string, QueryValue>): string {
  if (!params) return "";
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== "") {
      sp.set(k, String(v));
    }
  }
  const qs = sp.toString();
  return qs ? `?${qs}` : "";
}

async function requestJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const url = `${API_BASE_URL}${path}`;
  let response: Response;
  try {
    response = await fetch(url, {
      method: "GET",
      headers: { Accept: "application/json" },
      signal,
    });
  } catch (err: unknown) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw err;
    }
    throw new ApiClientError(
      "Unable to reach the FastAPI backend. Ensure uvicorn is running on port 8000.",
      0,
      "NETWORK_ERROR"
    );
  }

  let body: unknown = null;
  try {
    body = await response.json();
  } catch (err: unknown) {
    if ((err instanceof DOMException && err.name === "AbortError") || signal?.aborted) {
      throw err instanceof Error ? err : new DOMException("Aborted", "AbortError");
    }
    if (!response.ok) {
      throw new ApiClientError(`Backend returned HTTP ${response.status}`, response.status, "HTTP_ERROR");
    }
    throw new ApiClientError("Backend returned an invalid JSON payload.", response.status, "INVALID_JSON");
  }

  if (!response.ok) {
    const errObj = body as { detail?: string; error?: { code?: string; message?: string }; title?: string } | null;
    const msg =
      errObj?.error?.message ||
      (typeof errObj?.detail === "string" ? errObj.detail : undefined) ||
      errObj?.title ||
      `Request failed with HTTP ${response.status}`;
    const code = errObj?.error?.code || `HTTP_${response.status}`;
    throw new ApiClientError(msg, response.status, code);
  }

  return body as T;
}

export const apiClient = {
  getHealth(signal?: AbortSignal) {
    return requestJson<HealthCheckResponse>("/api/health", signal);
  },

  getRoutes(
    params?: {
      mode?: string;
      cluster?: number;
      partition?: string;
      search?: string;
      sort_by?: string;
      order?: string;
      limit?: number;
      offset?: number;
    },
    signal?: AbortSignal
  ) {
    return requestJson<RouteListResponse>(`/api/v1/routes${buildQuery(params)}`, signal);
  },

  getRouteDetail(routeId: string, signal?: AbortSignal) {
    return requestJson<RouteDetailResponse>(`/api/v1/routes/${encodeURIComponent(routeId)}`, signal);
  },

  getBusRankings(
    params?: {
      partition?: string;
      min_rank?: number;
      max_rank?: number;
      sort_by?: string;
      order?: string;
      limit?: number;
      offset?: number;
    },
    signal?: AbortSignal
  ) {
    return requestJson<RankingListResponse>(`/api/v1/rankings/bus${buildQuery(params)}`, signal);
  },

  getRailRankings(params?: { sort_by?: string; order?: string }, signal?: AbortSignal) {
    return requestJson<RankingListResponse>(`/api/v1/rankings/rail${buildQuery(params)}`, signal);
  },

  getUnifiedRankings(
    params?: {
      mode?: string;
      min_rank?: number;
      max_rank?: number;
      sort_by?: string;
      order?: string;
      limit?: number;
      offset?: number;
    },
    signal?: AbortSignal
  ) {
    return requestJson<RankingListResponse>(`/api/v1/rankings/unified${buildQuery(params)}`, signal);
  },

  getRouteExplanation(routeId: string, track?: string, signal?: AbortSignal) {
    return requestJson<RouteExplanationResponse>(
      `/api/v1/rankings/routes/${encodeURIComponent(routeId)}/explanation${buildQuery({ track })}`,
      signal
    );
  },

  getSensitivity(params?: { track?: string; target_criterion?: string }, signal?: AbortSignal) {
    return requestJson<SensitivityListResponse>(`/api/v1/rankings/sensitivity${buildQuery(params)}`, signal);
  },

  getRidershipTimeseries(
    routeId: string,
    params?: {
      start_date?: string;
      end_date?: string;
      granularity?: "daily" | "monthly";
      daytype?: string;
      limit?: number;
      offset?: number;
    },
    signal?: AbortSignal
  ) {
    return requestJson<RidershipTimeseriesResponse>(
      `/api/v1/ridership/routes/${encodeURIComponent(routeId)}/timeseries${buildQuery(params)}`,
      signal
    );
  },

  getTopHubs(params?: { config?: "a" | "b" | "c"; limit?: number; offset?: number }, signal?: AbortSignal) {
    return requestJson<TopHubsResponse>(`/api/v1/spatial/hubs/top${buildQuery(params)}`, signal);
  },

  getSpatialHubs(
    params?: {
      config?: "a" | "b" | "c";
      min_routes?: number;
      dbscan_cluster?: number;
      eligible_only?: boolean;
      min_lat?: number;
      min_lon?: number;
      max_lat?: number;
      max_lon?: number;
      sort_by?: string;
      order?: string;
      limit?: number;
      offset?: number;
    },
    signal?: AbortSignal
  ) {
    return requestJson<SpatialHubsListResponse>(`/api/v1/spatial/hubs${buildQuery(params)}`, signal);
  },

  getSpatialClustersSummary(signal?: AbortSignal) {
    return requestJson<ClusterSummaryResponse>("/api/v1/spatial/clusters/summary", signal);
  },

  getCorridorClusters(
    params?: {
      k?: number;
      cluster_type?: string;
      cluster_id?: number;
      mode?: string;
      route_id?: string;
      direction_id?: number;
      sort_by?: string;
      order?: string;
      limit?: number;
      offset?: number;
    },
    signal?: AbortSignal
  ) {
    return requestJson<CorridorClusterListResponse>(`/api/v1/corridors/clusters${buildQuery(params)}`, signal);
  },

  getRouteCoRouting(
    routeId: string,
    params?: { direction_id?: number; min_similarity?: number; top_n?: number },
    signal?: AbortSignal
  ) {
    return requestJson<RouteCoRoutingResponse>(
      `/api/v1/corridors/routes/${encodeURIComponent(routeId)}/co-routing${buildQuery(params)}`,
      signal
    );
  },

  getHistoricalForecast(
    params?: {
      tier?: "tier1" | "tier2";
      period?: "validation" | "test" | "august_holdout";
      route_id?: string;
      start_date?: string;
      end_date?: string;
      limit?: number;
      offset?: number;
    },
    signal?: AbortSignal
  ) {
    return requestJson<HistoricalForecastResponse>(`/api/v1/forecasting/historical${buildQuery(params)}`, signal);
  },

  getHistoricalForecastSummary(
    params?: { tier?: "tier1" | "tier2"; period?: "validation" | "test" | "august_holdout" },
    signal?: AbortSignal
  ) {
    return requestJson<HistoricalForecastSummaryResponse>(
      `/api/v1/forecasting/historical/summary${buildQuery(params)}`,
      signal
    );
  },
};
