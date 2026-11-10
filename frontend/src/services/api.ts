import axios from 'axios';
import type {
  DashboardSummary, Route, RouteDetail, RouteStop, Trip,
  ScheduleEntry, CoverageSummary, CoverageStop, OverlapPair,
  RouteOverlap, FrequencyStats, ServiceStats, ClusterResult,
  SimulationRequest, SimulationResult, DataQuality, DataStatus,
  Insight, PaginatedResponse
} from '../types';

const api = axios.create({
  baseURL: '/api',
  timeout: 60000,
});

api.interceptors.response.use(undefined, (error: unknown) => {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    const message = typeof detail === 'string' ? detail : error.response?.statusText || error.message;
    return Promise.reject(new Error(message));
  }
  return Promise.reject(error);
});

// Dashboard
export const getDashboardSummary = () =>
  api.get<DashboardSummary>('/dashboard/summary').then(r => r.data);

// Routes
export const getRoutes = (page = 1, pageSize = 50, search = '', minTrips?: number) =>
  api.get<PaginatedResponse<Route>>('/routes', { params: { page, page_size: pageSize, search: search || undefined, min_trips: minTrips, sort_by: 'total_trips', sort_order: 'desc' } }).then(r => r.data);

export const getRouteDetail = (routeId: string) =>
  api.get<RouteDetail>(`/routes/${routeId}`).then(r => r.data);

export const getRouteStops = (routeId: string) =>
  api.get<RouteStop[]>(`/routes/${routeId}/stops`).then(r => r.data);

export const getRouteTrips = (routeId: string) =>
  api.get<Trip[]>(`/routes/${routeId}/trips`).then(r => r.data);

export const getRouteSchedule = (routeId: string) =>
  api.get<ScheduleEntry[]>(`/routes/${routeId}/schedule`).then(r => r.data);

// Coverage
export const getCoverageSummary = () =>
  api.get<CoverageSummary>('/coverage/summary').then(r => r.data);

export const getCoverageStops = (page = 1, pageSize = 100, hubOnly = false, search = '') =>
  api.get<PaginatedResponse<CoverageStop>>('/coverage/stops', { params: { page, page_size: pageSize, is_hub_only: hubOnly, search: search || undefined } }).then(r => r.data);

// Overlap
export const getOverlap = (minSimilarity = 0.3, limit = 50) =>
  api.get<OverlapPair[]>('/overlap', { params: { min_overlap_pct: minSimilarity * 100, limit } }).then(r => r.data);

export const getRouteOverlap = (routeId: string) =>
  api.get<RouteOverlap>(`/overlap/${routeId}`).then(r => r.data);

// Analytics
export const getFrequencyStats = (page = 1, pageSize = 50, highFrequencyOnly = false) =>
  api.get<PaginatedResponse<FrequencyStats>>('/analytics/frequency', { params: { page, page_size: pageSize, high_frequency_only: highFrequencyOnly } }).then(r => r.data);

export const getServiceStats = () =>
  api.get<ServiceStats[]>('/analytics/service').then(r => r.data);

// ML
export const runClustering = (nClusters?: number) =>
  api.post<ClusterResult>('/ml/cluster', nClusters ? { n_clusters: nClusters, algorithm: 'kmeans' } : { algorithm: 'kmeans' }).then(r => r.data);

export const getClusters = () =>
  api.get<ClusterResult>('/ml/clusters').then(r => r.data);

// Optimization
export const runSimulation = (data: SimulationRequest) =>
  api.post<SimulationResult>('/optimization/simulate', data).then(r => r.data);

// Data
export const getDataQuality = () =>
  api.get<DataQuality>('/data/quality').then(r => r.data);

export const getDataStatus = () =>
  api.get<DataStatus>('/data/status').then(r => r.data);

// Insights
export const getInsights = () =>
  api.get<Insight[]>('/insights').then(r => r.data);

// Health
export const getHealth = () =>
  api.get('/health').then(r => r.data);

