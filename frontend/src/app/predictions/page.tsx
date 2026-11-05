'use client';

import { useState, useEffect } from 'react';
import {
  Brain,
  TrendingUp,
  Loader2,
  Clock,
  MapPin,
  RefreshCw,
  BarChart3,
  ArrowUpRight,
  ArrowDownRight,
} from 'lucide-react';
import { predictionApi, stationApi } from '@/lib/api';
import { useAuthStore } from '@/hooks/useAuthStore';

interface CrowdPrediction {
  timestamp: string;
  predicted_entries: number;
  predicted_exits: number;
  predicted_occupancy: number;
  confidence_lower: number;
  confidence_upper: number;
}

interface DemandForecast {
  date: string;
  predicted_demand: number;
  confidence_lower: number;
  confidence_upper: number;
}

interface TrafficPattern {
  hour: number;
  avg_entries: number;
  avg_exits: number;
  peak_factor: number;
}

export default function PredictionsPage() {
  const { isAuthenticated } = useAuthStore();
  const [stations, setStations] = useState<any[]>([]);
  const [selectedStation, setSelectedStation] = useState<string>('');
  const [hoursAhead, setHoursAhead] = useState(24);
  const [crowdPrediction, setCrowdPrediction] = useState<CrowdPrediction[]>([]);
  const [demandForecast, setDemandForecast] = useState<DemandForecast[]>([]);
  const [trafficPatterns, setTrafficPatterns] = useState<TrafficPattern[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<'crowd' | 'demand' | 'traffic'>('crowd');

  useEffect(() => {
    fetchStations();
  }, []);

  useEffect(() => {
    if (selectedStation) {
      fetchCrowdPrediction();
      fetchTrafficPatterns();
    }
    fetchDemandForecast();
  }, [selectedStation, hoursAhead, activeTab]);

  const fetchStations = async () => {
    try {
      const response = await stationApi.listStations({ limit: 200 });
      setStations(response.data);
      if (response.data.length > 0 && !selectedStation) {
        setSelectedStation(response.data[0].id);
      }
    } catch (error) {
      console.error('Failed to fetch stations:', error);
    }
  };

  const fetchCrowdPrediction = async () => {
    setIsLoading(true);
    try {
      const response = await predictionApi.getCrowdPrediction(selectedStation, hoursAhead, 15);
      setCrowdPrediction(response.data.predictions);
    } catch (error) {
      console.error('Failed to fetch crowd prediction:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const fetchDemandForecast = async () => {
    try {
      const response = await predictionApi.forecastDemand(undefined, undefined, 7);
      setDemandForecast(response.data.forecasts);
    } catch (error) {
      console.error('Failed to fetch demand forecast:', error);
    }
  };

  const fetchTrafficPatterns = async () => {
    try {
      const response = await predictionApi.analyzeTrafficPatterns(selectedStation);
      setTrafficPatterns(response.data.patterns);
    } catch (error) {
      console.error('Failed to fetch traffic patterns:', error);
    }
  };

  const formatTime = (timestamp: string) => {
    return new Date(timestamp).toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('en-US', {
      weekday: 'short',
      month: 'short',
      day: 'numeric',
    });
  };

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-secondary-50">
        <a href="/login" className="btn-primary">Please log in to view predictions</a>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-secondary-50 lg:ml-64">
      <header className="sticky top-0 z-40 bg-white border-b border-secondary-200">
        <div className="flex items-center justify-between h-16 px-6">
          <h1 className="text-2xl font-bold text-secondary-900">AI Predictions</h1>
          <div className="flex items-center gap-3">
            <select
              value={selectedStation}
              onChange={(e) => setSelectedStation(e.target.value)}
              className="input w-64"
            >
              {stations.map(station => (
                <option key={station.id} value={station.id}>
                  {station.name} ({station.code})
                </option>
              ))}
            </select>
            <button onClick={fetchCrowdPrediction} className="btn-outline" disabled={isLoading}>
              <RefreshCw className="w-4 h-4 mr-2" />
              Refresh
            </button>
          </div>
        </div>
      </header>

      <div className="p-6">
        {/* Tab Navigation */}
        <div className="card mb-6">
          <div className="flex border-b border-secondary-200">
            {[
              { id: 'crowd', label: 'Crowd Forecast', icon: Brain },
              { id: 'demand', label: 'Demand Forecast', icon: TrendingUp },
              { id: 'traffic', label: 'Traffic Patterns', icon: BarChart3 },
            ].map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`flex items-center gap-2 px-6 py-4 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === tab.id
                    ? 'border-primary-500 text-primary-600'
                    : 'border-transparent text-secondary-500 hover:text-secondary-700'
                }`}
              >
                <tab.icon className="w-4 h-4" />
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        {/* Crowd Forecast Tab */}
        {activeTab === 'crowd' && (
          <div className="space-y-6">
            <div className="card p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold text-secondary-900">Crowd Prediction ({hoursAhead}h)</h2>
                <div className="flex items-center gap-2">
                  <label className="text-sm text-secondary-500">Hours ahead:</label>
                  <select
                    value={hoursAhead}
                    onChange={(e) => setHoursAhead(Number(e.target.value))}
                    className="input w-24"
                  >
                    <option value={6}>6</option>
                    <option value={12}>12</option>
                    <option value={24}>24</option>
                    <option value={48}>48</option>
                  </select>
                </div>
              </div>
              {isLoading ? (
                <div className="flex justify-center py-8">
                  <Loader2 className="w-8 h-8 spinner" />
                </div>
              ) : (
                <div className="table-container">
                  <table className="table">
                    <thead className="table-header">
                      <tr>
                        <th className="table-head">Time</th>
                        <th className="table-head">Predicted Entries</th>
                        <th className="table-head">Predicted Exits</th>
                        <th className="table-head">Predicted Occupancy</th>
                        <th className="table-head">Confidence Range</th>
                      </tr>
                    </thead>
                    <tbody>
                      {crowdPrediction.slice(0, 50).map((pred, i) => (
                        <tr key={i} className="table-row">
                          <td className="table-cell">{formatTime(pred.timestamp)}</td>
                          <td className="table-cell">{pred.predicted_entries.toLocaleString()}</td>
                          <td className="table-cell">{pred.predicted_exits.toLocaleString()}</td>
                          <td className="table-cell">{pred.predicted_occupancy.toLocaleString()}</td>
                          <td className="table-cell">
                            <div className="flex items-center gap-2">
                              <div className="flex-1 h-2 bg-secondary-200 rounded-full overflow-hidden">
                                <div
                                  className="h-full bg-primary-500"
                                  style={{
                                    left: `${(pred.confidence_lower / (pred.confidence_upper || 1)) * 100}%`,
                                    width: `${((pred.confidence_upper - pred.confidence_lower) / (pred.confidence_upper || 1)) * 100}%`,
                                  }}
                                />
                              </div>
                              <span className="text-sm text-secondary-500">
                                {pred.confidence_lower}-{pred.confidence_upper}
                              </span>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {/* Mini Chart */}
            <div className="card p-6">
              <h3 className="text-lg font-semibold text-secondary-900 mb-4">Occupancy Trend</h3>
              <div className="h-48 flex items-end justify-between px-2">
                {crowdPrediction.slice(0, 24).map((pred, i) => (
                  <div key={i} className="flex-1 flex items-end justify-center px-0.5">
                    <div
                      className="w-full bg-primary-500 rounded-t transition-all hover:bg-primary-600"
                      style={{
                        height: `${Math.min(100, (pred.predicted_occupancy / 500) * 100)}%`,
                      }}
                      title={`${formatTime(pred.timestamp)}: ${pred.predicted_occupancy}`}
                    />
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Demand Forecast Tab */}
        {activeTab === 'demand' && (
          <div className="card p-6">
            <h2 className="text-lg font-semibold text-secondary-900 mb-4">7-Day Demand Forecast</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              {demandForecast.map((forecast, i) => (
                <div key={i} className="p-4 bg-secondary-50 rounded-lg">
                  <p className="text-sm font-medium text-secondary-900">{formatDate(forecast.date)}</p>
                  <p className="text-3xl font-bold text-primary-600 mt-1">{forecast.predicted_demand.toLocaleString()}</p>
                  <p className="text-xs text-secondary-500 mt-1">
                    Range: {forecast.confidence_lower.toLocaleString()} - {forecast.confidence_upper.toLocaleString()}
                  </p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Traffic Patterns Tab */}
        {activeTab === 'traffic' && (
          <div className="card p-6">
            <h2 className="text-lg font-semibold text-secondary-900 mb-4">Hourly Traffic Patterns</h2>
            <div className="h-64 flex items-end justify-between px-2">
              {trafficPatterns.map((pattern, i) => (
                <div key={i} className="flex-1 flex flex-col items-center px-0.5">
                  <div
                    className="w-full bg-primary-500 rounded-t transition-all hover:bg-primary-600"
                    style={{ height: `${Math.min(100, pattern.peak_factor * 100)}%` }}
                    title={`${pattern.hour}:00 - Entries: ${pattern.avg_entries.toFixed(0)}, Exits: ${pattern.avg_exits.toFixed(0)}`}
                  />
                  <span className="text-xs text-secondary-500 mt-1">{pattern.hour}:00</span>
                </div>
              ))}
            </div>
            <div className="mt-6 grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
              <div className="p-4 bg-secondary-50 rounded-lg">
                <p className="text-2xl font-bold text-primary-600">
                  {trafficPatterns.reduce((max, p) => Math.max(max, p.avg_entries), 0).toFixed(0)}
                </p>
                <p className="text-sm text-secondary-500">Peak Entries</p>
              </div>
              <div className="p-4 bg-secondary-50 rounded-lg">
                <p className="text-2xl font-bold text-success-600">
                  {trafficPatterns.filter(p => p.peak_factor > 1.2).length}
                </p>
                <p className="text-sm text-secondary-500">Peak Hours</p>
              </div>
              <div className="p-4 bg-secondary-50 rounded-lg">
                <p className="text-2xl font-bold text-warning-600">
                  {trafficPatterns.reduce((sum, p) => sum + p.avg_entries, 0).toFixed(0)}
                </p>
                <p className="text-sm text-secondary-500">Avg Hourly Entries</p>
              </div>
              <div className="p-4 bg-secondary-50 rounded-lg">
                <p className="text-2xl font-bold text-secondary-900">
                  {trafficPatterns.length}
                </p>
                <p className="text-sm text-secondary-500">Hours Analyzed</p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}