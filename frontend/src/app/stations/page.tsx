'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import {
  MapPin,
  Search,
  Filter,
  Plus,
  Map,
  AlertTriangle,
  TrendingUp,
  Loader2,
} from 'lucide-react';
import { stationApi } from '@/lib/api';
import { useAuthStore } from '@/hooks/useAuthStore';
import { useSocket } from '@/hooks/useSocket';

interface Station {
  id: string;
  line_id: string;
  name: string;
  code: string;
  order: number;
  latitude: number;
  longitude: number;
  capacity: number;
  zone: string | null;
  is_interchange: boolean;
  is_active: boolean;
  line: {
    id: string;
    name: string;
    code: string;
    color: string;
  };
}

interface CongestionStatus {
  station_id: string;
  station_name: string;
  line_code: string;
  current_occupancy: number;
  capacity: number;
  occupancy_rate: number;
  severity: string;
  trend: string;
  last_updated: string;
  predicted_severity: string | null;
}

export default function StationsPage() {
  const { isAuthenticated } = useAuthStore();
  const [stations, setStations] = useState<Station[]>([]);
  const [congestionStatuses, setCongestionStatuses] = useState<Record<string, CongestionStatus>>({});
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedLine, setSelectedLine] = useState<string>('all');
  const [selectedSeverity, setSelectedSeverity] = useState<string>('all');
  const [viewMode, setViewMode] = useState<'list' | 'map'>('list');

  const lines = Array.from(new Set(stations.map(s => s.line.code)));

  useEffect(() => {
    fetchStations();
  }, []);

  useEffect(() => {
    fetchCongestionStatuses();
    // Poll every 30 seconds
    const interval = setInterval(fetchCongestionStatuses, 30000);
    return () => clearInterval(interval);
  }, []);

  const { subscribe, unsubscribe } = useSocket({
    channels: ['congestion', 'station_updates'],
    onMessage: (message) => {
      if (message.type === 'congestion_update' || message.type === 'station_update') {
        fetchCongestionStatuses();
      }
    },
  });

  useEffect(() => {
    subscribe('congestion');
    subscribe('station_updates');
    return () => {
      unsubscribe('congestion');
      unsubscribe('station_updates');
    };
  }, [subscribe, unsubscribe]);

  const fetchStations = async () => {
    try {
      const response = await stationApi.listStations({ limit: 200 });
      setStations(response.data);
    } catch (error) {
      console.error('Failed to fetch stations:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const fetchCongestionStatuses = async () => {
    try {
      const response = await stationApi.getStationCongestion('');
      // This would need a proper endpoint, for now using congestion API
    } catch (error) {
      console.error('Failed to fetch congestion:', error);
    }
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'critical': return 'bg-danger-500';
      case 'high': return 'bg-danger-500';
      case 'medium': return 'bg-warning-500';
      case 'low': return 'bg-success-500';
      default: return 'bg-secondary-300';
    }
  };

  const getSeverityLabel = (severity: string) => {
    return severity.charAt(0).toUpperCase() + severity.slice(1);
  };

  const filteredStations = stations.filter(station => {
    const matchesSearch = station.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      station.code.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesLine = selectedLine === 'all' || station.line.code === selectedLine;
    const status = congestionStatuses[station.id];
    const matchesSeverity = selectedSeverity === 'all' ||
      (status && status.severity === selectedSeverity);
    return matchesSearch && matchesLine && matchesSeverity;
  });

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-secondary-50">
        <Link href="/login" className="btn-primary">Please log in to view stations</Link>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-secondary-50 lg:ml-64">
      <header className="sticky top-0 z-40 bg-white border-b border-secondary-200">
        <div className="flex items-center justify-between h-16 px-6">
          <h1 className="text-2xl font-bold text-secondary-900">Stations</h1>
          <Link href="/stations/new" className="btn-primary">
            <Plus className="w-4 h-4 mr-2" />
            Add Station
          </Link>
        </div>
      </header>

      <div className="p-6">
        {/* Filters */}
        <div className="card p-4 mb-6">
          <div className="flex flex-col md:flex-row gap-4">
            <div className="relative flex-1 max-md:w-full">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-secondary-400" />
              <input
                type="text"
                placeholder="Search stations..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="input pl-10"
              />
            </div>
            <div className="flex gap-2">
              <select
                value={selectedLine}
                onChange={(e) => setSelectedLine(e.target.value)}
                className="input w-48"
              >
                <option value="all">All Lines</option>
                {lines.map(line => (
                  <option key={line} value={line}>{line} Line</option>
                ))}
              </select>
              <select
                value={selectedSeverity}
                onChange={(e) => setSelectedSeverity(e.target.value)}
                className="input w-40"
              >
                <option value="all">All Severities</option>
                <option value="critical">Critical</option>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
              </select>
              <div className="flex gap-2 ml-auto">
                <button
                  onClick={() => setViewMode('list')}
                  className={`btn ${viewMode === 'list' ? 'btn-primary' : 'btn-outline'}`}
                >
                  <MapPin className="w-4 h-4" />
                </button>
                <button
                  onClick={() => setViewMode('map')}
                  className={`btn ${viewMode === 'map' ? 'btn-primary' : 'btn-outline'}`}
                >
                  <Map className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Station List/Map */}
        {viewMode === 'list' ? (
          <div className="card overflow-hidden">
            <div className="table-container">
              <table className="table">
                <thead className="table-header">
                  <tr>
                    <th className="table-head">Station</th>
                    <th className="table-head">Line</th>
                    <th className="table-head">Zone</th>
                    <th className="table-head">Capacity</th>
                    <th className="table-head">Occupancy</th>
                    <th className="table-head">Severity</th>
                    <th className="table-head">Trend</th>
                    <th className="table-head">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {isLoading ? (
                    <tr>
                      <td className="table-cell" colSpan={8}>
                        <div className="flex justify-center py-8">
                          <Loader2 className="w-8 h-8 spinner" />
                        </div>
                      </td>
                    </tr>
                  ) : filteredStations.length === 0 ? (
                    <tr>
                      <td className="table-cell text-center text-secondary-500 py-8" colSpan={8}>
                        No stations found
                      </td>
                    </tr>
                  ) : (
                    filteredStations.map((station) => {
                      const status = congestionStatuses[station.id];
                      const occupancyRate = status?.occupancy_rate ?? 0;
                      const severity = status?.severity ?? 'low';

                      return (
                        <tr key={station.id} className="table-row">
                          <td className="table-cell">
                            <Link href={`/stations/${station.id}`} className="font-medium text-secondary-900 hover:text-primary-600">
                              {station.name}
                            </Link>
                            <p className="text-sm text-secondary-500">{station.code}</p>
                          </td>
                          <td className="table-cell">
                            <span
                              className="badge"
                              style={{ backgroundColor: station.line.color + '20', color: station.line.color }}
                            >
                              {station.line.code}
                            </span>
                          </td>
                          <td className="table-cell">{station.zone || '-'}</td>
                          <td className="table-cell">{station.capacity.toLocaleString()}</td>
                          <td className="table-cell">
                            <div className="flex items-center gap-2">
                              <div className="flex-1 h-2 bg-secondary-200 rounded-full overflow-hidden">
                                <div
                                  className="h-full bg-primary-500 transition-all"
                                  style={{ width: `${occupancyRate}%` }}
                                />
                              </div>
                              <span className="text-sm font-medium w-16">{occupancyRate.toFixed(0)}%</span>
                            </div>
                          </td>
                          <td className="table-cell">
                            <span className={`badge ${getSeverityColor(severity).replace('bg-', 'bg-').replace('500', '100').replace('bg-', 'badge-').replace('500', '800')}`}>
                              {getSeverityLabel(severity)}
                            </span>
                          </td>
                          <td className="table-cell">
                            {status?.trend === 'increasing' && (
                              <TrendingUp className="w-4 h-4 text-danger-500" title="Increasing" />
                            )}
                            {status?.trend === 'decreasing' && (
                              <TrendingUp className="w-4 h-4 text-success-500 rotate-180" title="Decreasing" />
                            )}
                            {!status?.trend || status?.trend === 'stable' && (
                              <span className="text-secondary-400">Stable</span>
                            )}
                          </td>
                          <td className="table-cell">
                            <div className="flex items-center gap-2">
                              <Link href={`/stations/${station.id}`} className="btn-ghost btn-sm">
                                View
                              </Link>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  )}
                </tbody>
              </table>
            </div>
          </div>
        ) : (
          <div className="card">
            <div className="h-96 rounded-lg bg-secondary-100 flex items-center justify-center">
              <div className="text-center text-secondary-500">
                <Map className="w-12 h-12 mx-auto mb-2 opacity-50" />
                <p>Interactive Map View</p>
                <p className="text-sm">(Leaflet integration with congestion markers)</p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}