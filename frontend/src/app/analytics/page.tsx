'use client';

import { useState, useEffect } from 'react';
import {
  BarChart3,
  TrendingUp,
  Train,
  MapPin,
  Users,
  Clock,
  Loader2,
  Calendar,
  ChevronLeft,
  ChevronRight,
  Download,
} from 'lucide-react';
import { analyticsApi } from '@/lib/api';
import { useAuthStore } from '@/hooks/useAuthStore';

interface TrafficAnalytics {
  period_start: string;
  period_end: string;
  total_ridership: number;
  avg_daily_ridership: number;
  peak_hour: number;
  peak_ridership: number;
  by_line: Record<string, number>;
  by_station: Record<string, number>;
  trends: Array<{ date: string; ridership: number }>;
}

interface StationPerformance {
  station_id: string;
  station_name: string;
  line_code: string;
  total_entries: number;
  total_exits: number;
  avg_occupancy_rate: number;
  congestion_events: number;
  avg_delay_minutes: number;
  on_time_performance: number;
}

interface OperationalMonitoring {
  current: {
    active_trains: number;
    total_capacity: number;
    current_occupancy: number;
    system_occupancy_rate: number;
    delays: number;
    alerts_active: number;
    congestion_stations: number;
  };
  history: Array<{
    timestamp: string;
    system_occupancy_rate: number;
    active_trains: number;
  }>;
  alerts_summary: Record<string, number>;
}

export default function AnalyticsPage() {
  const { isAuthenticated } = useAuthStore();
  const [trafficData, setTrafficData] = useState<TrafficAnalytics | null>(null);
  const [stationPerformance, setStationPerformance] = useState<StationPerformance[]>([]);
  const [operationalData, setOperationalData] = useState<OperationalMonitoring | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [timeRange, setTimeRange] = useState<'7d' | '30d' | '90d'>('7d');
  const [selectedLine, setSelectedLine] = useState<string>('all');

  useEffect(() => {
    fetchAllData();
  }, [timeRange, selectedLine]);

  const fetchAllData = async () => {
    setIsLoading(true);
    try {
      const endTime = new Date().toISOString();
      const startTime = new Date(
        Date.now() - (timeRange === '7d' ? 7 : timeRange === '30d' ? 30 : 90) * 24 * 60 * 60 * 1000
      ).toISOString();

      const [trafficRes, performanceRes, operationalRes] = await Promise.all([
        analyticsApi.getTrafficAnalytics(startTime, endTime, selectedLine !== 'all' ? selectedLine : undefined),
        analyticsApi.getStationPerformance(startTime, endTime, selectedLine !== 'all' ? selectedLine : undefined),
        analyticsApi.getOperationalMonitoring(),
      ]);

      setTrafficData(trafficRes.data);
      setStationPerformance(performanceRes.data.stations);
      setOperationalData(operationalRes.data);
    } catch (error) {
      console.error('Failed to fetch analytics:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const formatNumber = (num: number) => {
    if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
    if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
    return num.toLocaleString();
  };

  const lines = trafficData ? Object.keys(trafficData.by_line) : [];

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-secondary-50">
        <a href="/login" className="btn-primary">Please log in to view analytics</a>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-secondary-50 lg:ml-64">
      <header className="sticky top-0 z-40 bg-white border-b border-secondary-200">
        <div className="flex items-center justify-between h-16 px-6">
          <h1 className="text-2xl font-bold text-secondary-900">Analytics</h1>
          <div className="flex items-center gap-3">
            <div className="flex gap-1 bg-secondary-100 rounded-lg p-1">
              {['7d', '30d', '90d'].map(range => (
                <button
                  key={range}
                  onClick={() => setTimeRange(range as any)}
                  className={`px-3 py-1.5 text-sm rounded-md transition-colors ${
                    timeRange === range
                      ? 'bg-white text-secondary-900 shadow-sm'
                      : 'text-secondary-600 hover:text-secondary-900'
                  }`}
                >
                  {range === '7d' ? '7 Days' : range === '30d' ? '30 Days' : '90 Days'}
                </button>
              ))}
            </div>
            <select
              value={selectedLine}
              onChange={(e) => setSelectedLine(e.target.value)}
              className="input w-40"
            >
              <option value="all">All Lines</option>
              {lines.map(line => (
                <option key={line} value={line}>{line} Line</option>
              ))}
            </select>
            <button className="btn-outline btn-sm">
              <Download className="w-4 h-4 mr-2" />
              Export
            </button>
          </div>
        </div>
      </header>

      <div className="p-6">
        {/* KPI Cards */}
        {trafficData && operationalData && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4 mb-6">
            <div className="card p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-secondary-500">Total Ridership</p>
                  <p className="text-3xl font-bold text-secondary-900 mt-1">{formatNumber(trafficData.total_ridership)}</p>
                </div>
                <div className="p-3 bg-primary-100 rounded-xl">
                  <BarChart3 className="w-6 h-6 text-primary-600" />
                </div>
              </div>
            </div>
            <div className="card p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-secondary-500">Avg Daily</p>
                  <p className="text-3xl font-bold text-secondary-900 mt-1">{formatNumber(Math.round(trafficData.avg_daily_ridership))}</p>
                </div>
                <div className="p-3 bg-success-100 rounded-xl">
                  <TrendingUp className="w-6 h-6 text-success-600" />
                </div>
              </div>
            </div>
            <div className="card p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-secondary-500">Active Trains</p>
                  <p className="text-3xl font-bold text-secondary-900 mt-1">{operationalData.current.active_trains}</p>
                </div>
                <div className="p-3 bg-warning-100 rounded-xl">
                  <Train className="w-6 h-6 text-warning-600" />
                </div>
              </div>
            </div>
            <div className="card p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-secondary-500">System Occupancy</p>
                  <p className="text-3xl font-bold text-secondary-900 mt-1">{operationalData.current.system_occupancy_rate.toFixed(1)}%</p>
                </div>
                <div className="p-3 bg-secondary-100 rounded-xl">
                  <Users className="w-6 h-6 text-secondary-600" />
                </div>
              </div>
            </div>
            <div className="card p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-secondary-500">Active Alerts</p>
                  <p className="text-3xl font-bold text-secondary-900 mt-1">{operationalData.current.alerts_active}</p>
                </div>
                <div className="p-3 bg-danger-100 rounded-xl">
                  <Clock className="w-6 h-6 text-danger-600" />
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Charts Row */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          {/* Ridership Trend */}
          <div className="card p-6">
            <h2 className="text-lg font-semibold text-secondary-900 mb-4">Ridership Trend</h2>
            <div className="h-64 flex items-end justify-between px-2">
              {trafficData?.trends?.slice(-30).map((trend, i) => (
                <div key={i} className="flex-1 flex items-end justify-center px-0.5">
                  <div
                    className="w-full bg-primary-500 rounded-t transition-all hover:bg-primary-600"
                    style={{ height: `${Math.min(100, (trend.ridership / (trafficData?.peak_ridership || 1)) * 100)}%` }}
                    title={`${trend.date}: ${trend.ridership.toLocaleString()}`}
                  />
                </div>
              ))}
            </div>
            <div className="flex justify-between text-xs text-secondary-500 mt-2">
              <span>{trafficData?.trends?.[0]?.date || ''}</span>
              <span>{trafficData?.trends?.[trafficData.trends.length - 1]?.date || ''}</span>
            </div>
          </div>

          {/* Ridership by Line */}
          <div className="card p-6">
            <h2 className="text-lg font-semibold text-secondary-900 mb-4">Ridership by Line</h2>
            <div className="space-y-3">
              {Object.entries(trafficData?.by_line || {}).map(([line, count]) => (
                <div key={line} className="flex items-center gap-4">
                  <span className="w-24 text-sm font-medium text-secondary-600">{line}</span>
                  <div className="flex-1 h-3 bg-secondary-200 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-primary-500"
                      style={{ width: `${(count / (trafficData?.peak_ridership || 1)) * 100}%` }}
                    />
                  </div>
                  <span className="w-20 text-sm text-secondary-500 text-right">{formatNumber(count)}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Peak Hours & Station Performance */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          {/* Peak Hours */}
          <div className="card p-6">
            <h2 className="text-lg font-semibold text-secondary-900 mb-4">Peak Hour Analysis</h2>
            <div className="flex items-center gap-4">
              <div className="flex-1">
                <p className="text-4xl font-bold text-primary-600">{trafficData?.peak_hour || 0}:00</p>
                <p className="text-sm text-secondary-500">Peak Hour</p>
              </div>
              <div className="flex-1">
                <p className="text-4xl font-bold text-warning-600">{formatNumber(trafficData?.peak_ridership || 0)}</p>
                <p className="text-sm text-secondary-500">Peak Ridership</p>
              </div>
            </div>
            <div className="mt-6 h-32 flex items-end justify-between px-2">
              {Array.from({ length: 24 }).map((_, hour) => {
                const isPeak = hour >= 7 && hour <= 9 || hour >= 17 && hour <= 19;
                return (
                  <div key={hour} className="flex-1 flex items-end justify-center px-0.5">
                    <div
                      className={`w-full rounded-t transition-all ${isPeak ? 'bg-danger-500' : 'bg-primary-500'}`}
                      style={{ height: `${isPeak ? 80 + Math.random() * 20 : 20 + Math.random() * 40}%` }}
                      title={`${hour}:00`}
                    />
                  </div>
                );
              })}
            </div>
          </div>

          {/* Top Stations */}
          <div className="card p-6">
            <h2 className="text-lg font-semibold text-secondary-900 mb-4">Top Stations by Ridership</h2>
            <div className="table-container">
              <table className="table">
                <thead className="table-header">
                  <tr>
                    <th className="table-head">Station</th>
                    <th className="table-head">Line</th>
                    <th className="table-head">Entries</th>
                    <th className="table-head">Exits</th>
                    <th className="table-head">Avg Occupancy</th>
                    <th className="table-head">Congestion Events</th>
                  </tr>
                </thead>
                <tbody>
                  {stationPerformance.slice(0, 10).map((station, i) => (
                    <tr key={station.station_id} className="table-row">
                      <td className="table-cell font-medium">{station.station_name}</td>
                      <td className="table-cell">
                        <span className="badge badge-info">{station.line_code}</span>
                      </td>
                      <td className="table-cell">{formatNumber(station.total_entries)}</td>
                      <td className="table-cell">{formatNumber(station.total_exits)}</td>
                      <td className="table-cell">{station.avg_occupancy_rate.toFixed(1)}%</td>
                      <td className="table-cell">
                        <span className={`badge ${station.congestion_events > 5 ? 'badge-warning' : 'badge-success'}`}>
                          {station.congestion_events}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Operational Monitoring History */}
        <div className="card p-6">
          <h2 className="text-lg font-semibold text-secondary-900 mb-4">System Occupancy (Last Hour)</h2>
          <div className="h-48 flex items-end justify-between px-2">
            {operationalData?.history?.map((point, i) => (
              <div key={i} className="flex-1 flex items-end justify-center px-0.5">
                <div
                  className="w-full bg-primary-500 rounded-t transition-all hover:bg-primary-600"
                  style={{ height: `${point.system_occupancy_rate}%` }}
                  title={`${new Date(point.timestamp).toLocaleTimeString()}: ${point.system_occupancy_rate.toFixed(1)}%`}
                />
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}