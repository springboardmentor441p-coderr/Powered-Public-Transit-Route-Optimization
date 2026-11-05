'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import {
  Train,
  Search,
  Filter,
  Plus,
  AlertTriangle,
  Loader2,
  Zap,
  Wrench,
  Circle,
} from 'lucide-react';
import { trainApi } from '@/lib/api';
import { useAuthStore } from '@/hooks/useAuthStore';

interface Train {
  id: string;
  train_number: string;
  line_id: string;
  capacity: number;
  status: string;
  current_station_id: string | null;
  current_station: {
    id: string;
    name: string;
    code: string;
  } | null;
  line: {
    id: string;
    name: string;
    code: string;
    color: string;
  };
}

export default function TrainsPage() {
  const { isAuthenticated } = useAuthStore();
  const [trains, setTrains] = useState<Train[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedLine, setSelectedLine] = useState<string>('all');
  const [selectedStatus, setSelectedStatus] = useState<string>('all');

  const lines = Array.from(new Set(trains.map(t => t.line.code)));
  const statuses = Array.from(new Set(trains.map(t => t.status)));

  useEffect(() => {
    fetchTrains();
    // Poll every 15 seconds
    const interval = setInterval(fetchTrains, 15000);
    return () => clearInterval(interval);
  }, []);

  const fetchTrains = async () => {
    try {
      const response = await trainApi.listTrains({ limit: 200 });
      setTrains(response.data);
    } catch (error) {
      console.error('Failed to fetch trains:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active': return 'bg-success-500';
      case 'delayed': return 'bg-warning-500';
      case 'maintenance': return 'bg-primary-500';
      case 'inactive': return 'bg-secondary-400';
      default: return 'bg-secondary-400';
    }
  };

  const getStatusLabel = (status: string) => {
    return status.charAt(0).toUpperCase() + status.slice(1);
  };

  const filteredTrains = trains.filter(train => {
    const matchesSearch = train.train_number.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesLine = selectedLine === 'all' || train.line.code === selectedLine;
    const matchesStatus = selectedStatus === 'all' || train.status === selectedStatus;
    return matchesSearch && matchesLine && matchesStatus;
  });

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-secondary-50">
        <Link href="/login" className="btn-primary">Please log in to view trains</Link>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-secondary-50 lg:ml-64">
      <header className="sticky top-0 z-40 bg-white border-b border-secondary-200">
        <div className="flex items-center justify-between h-16 px-6">
          <h1 className="text-2xl font-bold text-secondary-900">Trains</h1>
          <Link href="/trains/new" className="btn-primary">
            <Plus className="w-4 h-4 mr-2" />
            Add Train
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
                placeholder="Search trains..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="input pl-10"
              />
            </div>
            <div className="flex gap-2">
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
              <select
                value={selectedStatus}
                onChange={(e) => setSelectedStatus(e.target.value)}
                className="input w-40"
              >
                <option value="all">All Statuses</option>
                {statuses.map(status => (
                  <option key={status} value={status}>{getStatusLabel(status)}</option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* Train List */}
        <div className="card overflow-hidden">
          <div className="table-container">
            <table className="table">
              <thead className="table-header">
                <tr>
                  <th className="table-head">Train</th>
                  <th className="table-head">Line</th>
                  <th className="table-head">Status</th>
                  <th className="table-head">Current Station</th>
                  <th className="table-head">Capacity</th>
                  <th className="table-head">Actions</th>
                </tr>
              </thead>
              <tbody>
                {isLoading ? (
                  <tr>
                    <td className="table-cell" colSpan={6}>
                      <div className="flex justify-center py-8">
                        <Loader2 className="w-8 h-8 spinner" />
                      </div>
                    </td>
                  </tr>
                ) : filteredTrains.length === 0 ? (
                  <tr>
                    <td className="table-cell text-center text-secondary-500 py-8" colSpan={6}>
                      No trains found
                    </td>
                  </tr>
                ) : (
                  filteredTrains.map((train) => (
                    <tr key={train.id} className="table-row">
                      <td className="table-cell">
                        <Link href={`/trains/${train.id}`} className="font-mono font-medium text-secondary-900 hover:text-primary-600">
                          {train.train_number}
                        </Link>
                      </td>
                      <td className="table-cell">
                        <span
                          className="badge"
                          style={{ backgroundColor: train.line.color + '20', color: train.line.color }}
                        >
                          {train.line.code}
                        </span>
                      </td>
                      <td className="table-cell">
                        <div className="flex items-center gap-2">
                          <span
                            className={`w-2 h-2 rounded-full ${getStatusColor(train.status)}`}
                          />
                          <span className="text-sm font-medium capitalize">{getStatusLabel(train.status)}</span>
                          {train.status === 'delayed' && (
                            <AlertTriangle className="w-4 h-4 text-warning-500" title="Delayed" />
                          )}
                          {train.status === 'maintenance' && (
                            <Wrench className="w-4 h-4 text-primary-500" title="Maintenance" />
                          )}
                          {train.status === 'active' && (
                            <Zap className="w-4 h-4 text-success-500" title="Active" />
                          )}
                        </div>
                      </td>
                      <td className="table-cell">
                        {train.current_station ? (
                          <Link href={`/stations/${train.current_station.id}`} className="text-secondary-900 hover:text-primary-600">
                            {train.current_station.name} ({train.current_station.code})
                          </Link>
                        ) : (
                          <span className="text-secondary-400">En route</span>
                        )}
                      </td>
                      <td className="table-cell">{train.capacity.toLocaleString()}</td>
                      <td className="table-cell">
                        <Link href={`/trains/${train.id}`} className="btn-ghost btn-sm">
                          View
                        </Link>
                      </td>
                    </tr>
                  ))}
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}