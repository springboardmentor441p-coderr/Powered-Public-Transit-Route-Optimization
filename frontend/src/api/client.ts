// The one place the frontend talks to the API. Every call goes to /api/... on the same origin; Vite's proxy
// forwards it to uvicorn, so the backend needs no CORS.
//
// Cutoff: every function takes optional { cutoff, dataVersion }. Stage 6 passes no cutoff (historical
// analysis). Stage 7's replay will pass one, and the BACKEND then hides every date after it in SQL; the client
// only forwards it, it never filters data itself.
import type {
  CompareResponse, Coverage, DayType, ModelsResponse, GroupsResponse, HistoryResponse, MapLinesResponse, OverlapResponse,
  PeriodName, RankingMetric, RankingResponse, RoutesResponse, TrendResponse,
} from './types'

export type ApiOptions = { cutoff?: string | null; dataVersion?: string | null; signal?: AbortSignal }
type Params = Record<string, string | number | boolean | null | undefined>

/** An API failure, carrying FastAPI's own message (e.g. "compare needs 2 to 8 routes, got 1"). */
export class ApiError extends Error {
  readonly status: number
  readonly url: string
  constructor(status: number, message: string, url: string) {
    super(message)
    this.status = status
    this.url = url
  }
}

/** Build "/api/...?..." : null/undefined params are left out; cutoff and data_version are added only when set. */
export function buildUrl(path: string, params: Params = {}, opts: ApiOptions = {}): string {
  const q = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) if (v !== null && v !== undefined && v !== '') q.set(k, String(v))
  if (opts.cutoff) q.set('cutoff', opts.cutoff)
  if (opts.dataVersion) q.set('data_version', opts.dataVersion)
  const s = q.toString()
  return s ? `${path}?${s}` : path
}

/** FastAPI errors: {"detail": "text"} or {"detail": [{"msg": ..., "loc": [...]}]} (422 validation). */
export function errorMessage(body: unknown, status: number): string {
  const detail = (body as { detail?: unknown } | null)?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail.map(d => {
      const e = d as { msg?: string; loc?: unknown[] }
      const where = Array.isArray(e.loc) ? e.loc.filter(x => x !== 'query').join('.') : ''
      return where ? `${where}: ${e.msg ?? 'invalid'}` : (e.msg ?? 'invalid')
    }).join('; ')
  }
  return status === 502 || status === 504 ? 'the API is not reachable (is uvicorn running on 127.0.0.1:8000?)'
    : `request failed with status ${status}`
}

export async function apiGet<T>(path: string, params: Params = {}, opts: ApiOptions = {}): Promise<T> {
  const url = buildUrl(path, params, opts)
  let res: Response
  try {
    res = await fetch(url, { signal: opts.signal, headers: { Accept: 'application/json' } })
  } catch (e) {
    if ((e as Error).name === 'AbortError') throw e
    throw new ApiError(0, 'the API is not reachable (is uvicorn running on 127.0.0.1:8000?)', url)
  }
  // Reading the body can fail for two different reasons, and they must not be confused:
  //  - the request was cancelled (the screen moved on): re-throw the AbortError, so the caller ignores it;
  //  - the body is not JSON: an error body may be plain text (use its status), but a 200 answer MUST be JSON.
  // Before this, a cancelled read became a "successful" null, and a screen could render null as its data.
  let body: unknown = null
  try {
    body = await res.json()
  } catch (e) {
    if ((e as Error).name === 'AbortError') throw e
    if (res.ok) throw new ApiError(res.status, 'the API answered, but not with readable data', url)
  }
  if (!res.ok) throw new ApiError(res.status, errorMessage(body, res.status), url)
  if (body == null) throw new ApiError(res.status, 'the API answered with no data', url)
  return body as T
}

// ---- one function per endpoint ---------------------------------------------------------------------------
export type PeriodChoice = { period?: PeriodName; start?: string; end?: string }

export const api = {
  coverage: (o?: ApiOptions) => apiGet<Coverage>('/api/data/coverage', {}, o),

  models: (o?: ApiOptions) => apiGet<ModelsResponse>('/api/models/summary', {}, o),

  routes: (f: { group_id?: number; ungrouped?: boolean; saturday_service?: boolean; sunday_holiday_service?: boolean
                active_start?: string; active_end?: string } = {}, o?: ApiOptions) =>
    apiGet<RoutesResponse>('/api/routes', f, o),

  history: (route: string, r: { start?: string; end?: string } = {}, o?: ApiOptions) =>
    apiGet<HistoryResponse>(`/api/routes/${encodeURIComponent(route)}/history`, { mode: 'historical', ...r }, o),

  rankings: (q: { metric: RankingMetric; daytype: DayType; min_days?: number; group_id?: number } & PeriodChoice, o?: ApiOptions) =>
    apiGet<RankingResponse>('/api/rankings', q, o),

  overlap: (q: { geometry_version?: string } = {}, o?: ApiOptions) =>
    apiGet<OverlapResponse>('/api/rankings', { metric: 'route_overlap_review', ...q }, o),

  compare: (routes: string[], q: { daytype: DayType; geometry_version?: string; same_days?: boolean } & PeriodChoice, o?: ApiOptions) =>
    apiGet<CompareResponse>('/api/routes/compare', { routes: routes.join(','), ...q }, o),

  groups: (o?: ApiOptions) => apiGet<GroupsResponse>('/api/route-groups', {}, o),

  /** Network demand trend: default range is the analysis window; `start` may go back to 2001. */
  trend: (r: { start?: string; end?: string } = {}, o?: ApiOptions) => apiGet<TrendResponse>('/api/network/trend', r, o),

  /** Network map: default 10 m display simplification. Route detail and Compare pass simplify_m: 0 (exact). */
  mapLines: (q: { geometry_version?: string; date?: string; routes?: string[]; simplify_m?: number } = {}, o?: ApiOptions) =>
    apiGet<MapLinesResponse>('/api/map/lines', { ...q, routes: q.routes?.join(',') }, o),
}
