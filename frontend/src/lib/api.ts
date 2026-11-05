import axios, { AxiosInstance, InternalAxiosRequestConfig } from 'axios';

// API base URL
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
const WS_BASE_URL = process.env.NEXT_PUBLIC_WS_URL || 'http://localhost:8000';

// Create axios instance
export const api: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true,
});

// Request interceptor to add auth token
api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    if (typeof window !== 'undefined') {
      const token = localStorage.getItem('access_token');
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor for token refresh
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      try {
        const refreshToken = localStorage.getItem('refresh_token');
        if (refreshToken) {
          const response = await axios.post(`${API_BASE_URL}/auth/refresh`, {
            refresh_token: refreshToken,
          });

          const { access_token, refresh_token: newRefreshToken } = response.data;
          localStorage.setItem('access_token', access_token);
          localStorage.setItem('refresh_token', newRefreshToken);

          originalRequest.headers.Authorization = `Bearer ${access_token}`;
          return api(originalRequest);
        }
      } catch (refreshError) {
        // Refresh failed, redirect to login
        if (typeof window !== 'undefined') {
          localStorage.removeItem('access_token');
          localStorage.removeItem('refresh_token');
          window.location.href = '/login';
        }
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);

// API endpoints
export const authApi = {
  login: (email: string, password: string) =>
    api.post('/auth/login', { email, password }),
  register: (data: { email: string; password: string; full_name: string; role?: string }) =>
    api.post('/auth/register', data),
  refresh: (refreshToken: string) =>
    api.post('/auth/refresh', { refresh_token: refreshToken }),
  logout: (refreshToken: string) =>
    api.post('/auth/logout', { refresh_token: refreshToken }),
  me: () => api.get('/auth/me'),
  updateMe: (data: Partial<{ email: string; full_name: string; role: string }>) =>
    api.put('/auth/me', data),
  listUsers: (skip?: number, limit?: number) =>
    api.get('/auth/users', { params: { skip, limit } }),
  getUser: (userId: string) => api.get(`/auth/users/${userId}`),
  updateUser: (userId: string, data: Partial<{ email: string; full_name: string; role: string; is_active: boolean }>) =>
    api.put(`/auth/users/${userId}`, data),
  deleteUser: (userId: string) => api.delete(`/auth/users/${userId}`),
};

export const stationApi = {
  listLines: (activeOnly = true, skip = 0, limit = 100) =>
    api.get('/stations/lines', { params: { active_only: activeOnly, skip, limit } }),
  getLine: (lineId: string) => api.get(`/stations/lines/${lineId}`),
  createLine: (data: { name: string; code: string; color: string; description?: string }) =>
    api.post('/stations/lines', data),
  updateLine: (lineId: string, data: Partial<{ name: string; color: string; description: string; is_active: boolean }>) =>
    api.put(`/stations/lines/${lineId}`, data),
  deleteLine: (lineId: string) => api.delete(`/stations/lines/${lineId}`),

  listStations: (params?: { line_id?: string; active_only?: boolean; skip?: number; limit?: number }) =>
    api.get('/stations', { params }),
  getStation: (stationId: string) => api.get(`/stations/${stationId}`),
  getStationByCode: (code: string) => api.get(`/stations/code/${code}`),
  getStationsByLine: (lineId: string) => api.get(`/stations/line/${lineId}`),
  createStation: (data: {
    line_id: string;
    name: string;
    code: string;
    order: number;
    latitude: number;
    longitude: number;
    capacity?: number;
    zone?: string;
    is_interchange?: boolean;
  }) => api.post('/stations', data),
  updateStation: (stationId: string, data: Partial<{
    name: string;
    order: number;
    latitude: number;
    longitude: number;
    capacity: number;
    zone: string;
    is_interchange: boolean;
    is_active: boolean;
  }>) => api.put(`/stations/${stationId}`, data),
  deleteStation: (stationId: string) => api.delete(`/stations/${stationId}`),

  // Congestion
  getStationCongestion: (stationId: string) => api.get(`/stations/${stationId}/congestion`),
  getStationHeatmap: (stationId: string) => api.get(`/stations/${stationId}/heatmap`),
};

export const trainApi = {
  listTrains: (params?: { line_id?: string; status?: string; active_only?: boolean; skip?: number; limit?: number }) =>
    api.get('/trains', { params }),
  getTrain: (trainId: string) => api.get(`/trains/${trainId}`),
  createTrain: (data: { train_number: string; line_id: string; capacity?: number }) =>
    api.post('/trains', data),
  updateTrain: (trainId: string, data: Partial<{ line_id: string; capacity: number; status: string; current_station_id: string }>) =>
    api.put(`/trains/${trainId}`, data),
  deleteTrain: (trainId: string) => api.delete(`/trains/${trainId}`),
  getTrainOccupancy: (trainId: string) => api.get(`/trains/${trainId}/occupancy`),
};

export const scheduleApi = {
  listSchedules: (params?: { train_id?: string; station_id?: string; day_type?: string; active_only?: boolean; skip?: number; limit?: number }) =>
    api.get('/schedules', { params }),
  getSchedule: (scheduleId: string) => api.get(`/schedules/${scheduleId}`),
  getTrainSchedule: (trainId: string, dayType?: string) =>
    api.get(`/schedules/train/${trainId}`, { params: { day_type: dayType } }),
  getStationSchedule: (stationId: string, dayType?: string) =>
    api.get(`/schedules/station/${stationId}`, { params: { day_type: dayType } }),
  createSchedule: (data: {
    train_id: string;
    station_id: string;
    arrival_time?: string;
    departure_time?: string;
    day_type?: string;
    sequence: number;
  }) => api.post('/schedules', data),
  updateSchedule: (scheduleId: string, data: Partial<{
    arrival_time: string;
    departure_time: string;
    day_type: string;
    sequence: number;
    is_active: boolean;
  }>) => api.put(`/schedules/${scheduleId}`, data),
  deleteSchedule: (scheduleId: string) => api.delete(`/schedules/${scheduleId}`),
  optimizeSchedule: (data: { line_id: string; day_type?: string; target_headway_minutes?: number; max_trains?: number }) =>
    api.post('/schedules/optimize', data),
};

export const ridershipApi = {
  createRecord: (data: {
    station_id: string;
    entry_count: number;
    exit_count: number;
    timestamp: string;
    source?: string;
  }) => api.post('/ridership', data),
  bulkCreateRecords: (records: Array<{
    station_id: string;
    entry_count: number;
    exit_count: number;
    timestamp: string;
    source?: string;
  }>) => api.post('/ridership/bulk', records),
  getStationRidership: (stationId: string, startTime: string, endTime: string, source?: string) =>
    api.get(`/ridership/station/${stationId}`, { params: { start_time: startTime, end_time: endTime, source } }),
  getLatestRidership: (stationId: string) => api.get(`/ridership/station/${stationId}/latest`),
  getRidershipSummary: (stationId: string, startTime: string, endTime: string) =>
    api.get(`/ridership/station/${stationId}/summary`, { params: { start_time: startTime, end_time: endTime } }),

  createOccupancy: (data: {
    train_id: string;
    station_id: string;
    occupancy_count: number;
    capacity: number;
    timestamp: string;
  }) => api.post('/ridership/occupancy', data),
  bulkCreateOccupancy: (records: Array<{
    train_id: string;
    station_id: string;
    occupancy_count: number;
    capacity: number;
    timestamp: string;
  }>) => api.post('/ridership/occupancy/bulk', records),
  getTrainOccupancy: (trainId: string, startTime: string, endTime: string) =>
    api.get(`/ridership/occupancy/train/${trainId}`, { params: { start_time: startTime, end_time: endTime } }),
  getStationOccupancy: (stationId: string, startTime: string, endTime: string) =>
    api.get(`/ridership/occupancy/station/${stationId}`, { params: { start_time: startTime, end_time: endTime } }),
  getLatestTrainOccupancy: (trainId: string) => api.get(`/ridership/occupancy/train/${trainId}/latest`),
  getSystemOccupancy: () => api.get('/ridership/occupancy/system/current'),
};

export const congestionApi = {
  getStationCongestion: (stationId: string, hours?: number) =>
    api.get(`/congestion/station/${stationId}`, { params: { hours } }),
  getCurrentCongestion: (stationId: string) => api.get(`/congestion/station/${stationId}/current`),
  getAllCurrentCongestion: () => api.get('/congestion/current'),
  getHeatmap: () => api.get('/congestion/heatmap'),
  getAllStationStatuses: () => api.get('/congestion/status/all'),
  createEvent: (data: { station_id: string; passenger_count: number; capacity: number; predicted?: boolean }) =>
    api.post('/congestion/event', data),
  resolveEvent: (eventId: string) => api.put(`/congestion/event/${eventId}/resolve`),
};

export const alertApi = {
  listAlerts: (params?: {
    type?: string;
    severity?: string;
    station_id?: string;
    train_id?: string;
    unread_only?: boolean;
    active_only?: boolean;
    skip?: number;
    limit?: number;
  }) => api.get('/alerts', { params }),
  getAlertSummary: () => api.get('/alerts/summary'),
  getAlert: (alertId: string) => api.get(`/alerts/${alertId}`),
  updateAlert: (alertId: string, data: Partial<{ is_read: boolean; is_dismissed: boolean; dismissed_by: string }>) =>
    api.put(`/alerts/${alertId}`, data),
  markRead: (alertId: string) => api.post(`/alerts/${alertId}/read`),
  dismiss: (alertId: string) => api.post(`/alerts/${alertId}/dismiss`),
  markAllRead: () => api.post('/alerts/read-all'),
  cleanup: () => api.post('/alerts/cleanup'),
};

export const predictionApi = {
  predictCrowd: (data: { station_id: string; hours_ahead?: number; interval_minutes?: number }) =>
    api.post('/predictions/crowd', data),
  getCrowdPrediction: (stationId: string, hoursAhead?: number, intervalMinutes?: number) =>
    api.get(`/predictions/crowd/station/${stationId}`, { params: { hours_ahead: hoursAhead, interval_minutes: intervalMinutes } }),
  forecastDemand: (params?: { line_id?: string; station_id?: string; days?: number }) =>
    api.get('/predictions/demand', { params }),
  analyzeTrafficPatterns: (stationId: string) => api.get(`/predictions/traffic/station/${stationId}`),
  retrainModels: (data: { model_type: string; force?: boolean }) =>
    api.post('/predictions/retrain', data),
};

export const analyticsApi = {
  getTrafficAnalytics: (startTime: string, endTime: string, lineId?: string) =>
    api.get('/analytics/traffic', { params: { start_time: startTime, end_time: endTime, line_id: lineId } }),
  getTrafficLast7Days: (lineId?: string) =>
    api.get('/analytics/traffic/last-7-days', { params: { line_id: lineId } }),
  getTrafficLast30Days: (lineId?: string) =>
    api.get('/analytics/traffic/last-30-days', { params: { line_id: lineId } }),
  getStationPerformance: (startTime: string, endTime: string, lineId?: string) =>
    api.get('/analytics/station-performance', { params: { start_time: startTime, end_time: endTime, line_id: lineId } }),
  getStationPerformanceLast7Days: (lineId?: string) =>
    api.get('/analytics/station-performance/last-7-days', { params: { line_id: lineId } }),
  getOperationalMonitoring: () => api.get('/analytics/operational'),
};

// WebSocket URL helper
export const getWebSocketUrl = (channel?: string) => {
  const url = new URL('/ws/client', WS_BASE_URL);
  if (channel) {
    url.searchParams.set('channel', channel);
  }
  return url.toString();
};

export const getSocketIoUrl = () => WS_BASE_URL;

export default api;