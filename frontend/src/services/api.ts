import axios from 'axios'
import type {
  ClusterSummary,
  CompareResponse,
  ApiHealth,
  DatasetStatistics,
  HeadwaySummary,
  ModelMetadata,
  ModelMetric,
  Page,
  RouteFeature,
  RouteItem,
  RouteStatistics,
  ScheduledHour,
  SimilarityItem,
  StopItem,
  StopRoute,
  StopStatistics,
} from '../types/api'

const baseURL = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api/v1').replace(/\/$/, '')
const healthURL = `${baseURL.replace(/\/api\/v1$/, '')}/health`

export const apiClient = axios.create({ baseURL, timeout: 20_000 })

const responseCache = new Map<string, { expiresAt: number; request: Promise<unknown> }>()
const RESPONSE_CACHE_TTL_MS = 30_000
const RESPONSE_CACHE_LIMIT = 100

function cachedGet<T>(path: string, params: Record<string, string | number | undefined> = {}, ttl = RESPONSE_CACHE_TTL_MS): Promise<T> {
  const stableParams = Object.fromEntries(Object.entries(params).filter(([, value]) => value !== undefined).sort(([a], [b]) => a.localeCompare(b)))
  const key = `${path}?${new URLSearchParams(Object.entries(stableParams).map(([name, value]) => [name, String(value)]))}`
  const current = responseCache.get(key)
  if (current && current.expiresAt > Date.now()) return current.request as Promise<T>
  if (current) responseCache.delete(key)

  const request = apiClient.get<T>(path, { params: stableParams }).then((response) => response.data)
  responseCache.set(key, { expiresAt: Date.now() + ttl, request })
  request.catch(() => { responseCache.delete(key) })
  while (responseCache.size > RESPONSE_CACHE_LIMIT) {
    const oldest = responseCache.keys().next().value
    if (oldest === undefined) break
    responseCache.delete(oldest)
  }
  return request
}

let allStopsCache: { expiresAt: number; request: Promise<StopItem[]> } | null = null

export interface RouteQuery {
  limit?: number
  offset?: number
  q?: string
  min_trips?: number
  max_trips?: number
  min_stops?: number
  min_headway_seconds?: number
  max_headway_seconds?: number
  algorithm?: 'kmeans' | 'dbscan'
  cluster_id?: number
}

export interface StopQuery {
  limit?: number
  offset?: number
  q?: string
  min_routes?: number
}

export const api = {
  async health(): Promise<ApiHealth> {
    return (await axios.get<ApiHealth>(healthURL, { timeout: 5_000 })).data
  },
  async datasetStatistics(): Promise<DatasetStatistics> {
    return cachedGet('/analytics/statistics')
  },
  async routeStatistics(): Promise<RouteStatistics> {
    return cachedGet('/analytics/routes/statistics')
  },
  async stopStatistics(): Promise<StopStatistics> {
    return cachedGet('/analytics/stops/statistics')
  },
  async scheduledTripsByHour(): Promise<ScheduledHour[]> {
    return cachedGet('/analytics/scheduled-trips/by-hour')
  },
  async headways(routeId?: string): Promise<HeadwaySummary> {
    return cachedGet('/analytics/headways', routeId ? { route_id: routeId } : {})
  },
  async clusters(): Promise<ClusterSummary[]> {
    return cachedGet('/analytics/clusters')
  },
  async modelMetrics(): Promise<ModelMetric[]> {
    return cachedGet('/ml/metrics')
  },
  async models(): Promise<ModelMetadata[]> {
    return cachedGet('/ml/models')
  },
  async listRoutes(query: RouteQuery = {}): Promise<Page<RouteItem>> {
    return cachedGet('/routes', { ...query })
  },
  async route(routeId: string): Promise<RouteItem> {
    return cachedGet(`/routes/${encodeURIComponent(routeId)}`)
  },
  async routeFeatures(routeId: string): Promise<RouteFeature> {
    return cachedGet(`/routes/${encodeURIComponent(routeId)}/features`)
  },
  async routeCluster(routeId: string): Promise<{ route_id: string; kmeans_cluster_id: number | null; dbscan_cluster_id: number | null; fit_status: string }> {
    return cachedGet(`/routes/${encodeURIComponent(routeId)}/clusters`)
  },
  async routeComparison(routeIds: string[]): Promise<CompareResponse> {
    const params = new URLSearchParams()
    routeIds.forEach((id) => params.append('route_ids', id))
    return (await apiClient.get<CompareResponse>(`/routes/compare?${params.toString()}`)).data
  },
  async listStops(query: StopQuery = {}): Promise<Page<StopItem>> {
    return cachedGet('/stops', { ...query })
  },
  async routesAtStop(stopId: string): Promise<StopRoute[]> {
    return cachedGet(`/stops/${encodeURIComponent(stopId)}/routes`)
  },
  async similarities(routeId?: string, limit = 100): Promise<SimilarityItem[]> {
    return cachedGet('/analytics/route-similarity', { ...(routeId ? { route_id: routeId } : {}), limit })
  },
  async allStops(): Promise<StopItem[]> {
    if (allStopsCache && allStopsCache.expiresAt > Date.now()) return allStopsCache.request
    const firstPage = await api.listStops({ limit: 500, offset: 0 })
    const pages = Math.ceil(firstPage.total / 500)
    const rest = await Promise.all(Array.from({ length: pages - 1 }, (_, index) =>
      api.listStops({ limit: 500, offset: (index + 1) * 500 }),
    ))
    const result = [...firstPage.items, ...rest.flatMap((page) => page.items)]
    allStopsCache = { expiresAt: Date.now() + 5 * 60_000, request: Promise.resolve(result) }
    return result
  },
}

export function explainApiError(error: unknown): string {
  if (axios.isAxiosError(error)) {
    if (!error.response) return 'Could not reach the RouteRanker API. Check that the backend is running.'
    const payload: unknown = error.response.data
    const detail = typeof payload === 'object' && payload !== null && 'detail' in payload
      ? (payload as { detail?: unknown }).detail
      : undefined
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) return detail.map((item) => String(item.msg ?? 'Invalid request')).join(', ')
    return `The API returned an error (${error.response.status}).`
  }
  return error instanceof Error ? error.message : 'An unexpected error occurred.'
}
