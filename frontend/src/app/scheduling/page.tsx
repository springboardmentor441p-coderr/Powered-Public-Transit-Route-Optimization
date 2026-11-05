'use client';

import { useState, useEffect } from 'react';
import {
  Calendar,
  Train,
  MapPin,
  Plus,
  Loader2,
  RotateCcw,
  Clock,
  AlertTriangle,
  Zap,
} from 'lucide-react';
import { scheduleApi, trainApi, stationApi } from '@/lib/api';
import { useAuthStore } from '@/hooks/useAuthStore';

interface Schedule {
  id: string;
  train_id: string;
  station_id: string;
  arrival_time: string | null;
  departure_time: string | null;
  day_type: string;
  sequence: number;
  is_active: boolean;
  train: {
    id: string;
    train_number: string;
    line: { code: string; color: string };
  };
  station: {
    id: string;
    name: string;
    code: string;
  };
}

export default function SchedulingPage() {
  const { isAuthenticated } = useAuthStore();
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [trains, setTrains] = useState<any[]>([]);
  const [stations, setStations] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedTrain, setSelectedTrain] = useState<string>('all');
  const [selectedStation, setSelectedStation] = useState<string>('all');
  const [selectedDayType, setSelectedDayType] = useState<string>('weekday');
  const [showOptimize, setShowOptimize] = useState(false);
  const [optimizeLine, setOptimizeLine] = useState<string>('');

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [trainsRes, stationsRes] = await Promise.all([
        trainApi.listTrains({ limit: 200 }),
        stationApi.listStations({ limit: 200 }),
      ]);
      setTrains(trainsRes.data);
      setStations(stationsRes.data);
      fetchSchedules();
    } catch (error) {
      console.error('Failed to fetch data:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const fetchSchedules = async () => {
    try {
      const response = await scheduleApi.listSchedules({
        train_id: selectedTrain !== 'all' ? selectedTrain : undefined,
        station_id: selectedStation !== 'all' ? selectedStation : undefined,
        day_type: selectedDayType,
        limit: 200,
      });
      setSchedules(response.data);
    } catch (error) {
      console.error('Failed to fetch schedules:', error);
    }
  };

  const handleOptimize = async () => {
    if (!optimizeLine) return;
    try {
      const response = await scheduleApi.optimizeSchedule({
        line_id: optimizeLine,
        day_type: selectedDayType,
        target_headway_minutes: 5,
        max_trains: 20,
      });
      alert(`Optimization complete: ${response.data.message}`);
      fetchSchedules();
    } catch (error) {
      console.error('Optimization failed:', error);
      alert('Optimization failed');
    }
  };

  const formatTime = (time: string | null) => {
    if (!time) return '-';
    return time.slice(0, 5);
  };

  const dayTypes = ['weekday', 'saturday', 'sunday', 'holiday'];

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-secondary-50">
        <a href="/login" className="btn-primary">Please log in to view scheduling</a>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-secondary-50 lg:ml-64">
      <header className="sticky top-0 z-40 bg-white border-b border-secondary-200">
        <div className="flex items-center justify-between h-16 px-6">
          <h1 className="text-2xl font-bold text-secondary-900">Scheduling</h1>
          <div className="flex items-center gap-3">
            <button
              onClick={() => setShowOptimize(true)}
              className="btn-primary"
            >
              <RotateCcw className="w-4 h-4 mr-2" />
              Optimize Schedule
            </button>
          </div>
        </div>
      </header>

      <div className="p-6">
        {/* Filters */}
        <div className="card p-4 mb-6">
          <div className="flex flex-col md:flex-row gap-4">
            <div className="flex gap-4">
              <div>
                <label className="label block mb-1">Day Type</label>
                <select
                  value={selectedDayType}
                  onChange={(e) => setSelectedDayType(e.target.value)}
                  className="input w-40"
                >
                  {dayTypes.map(dt => (
                    <option key={dt} value={dt}>{dt.charAt(0).toUpperCase() + dt.slice(1)}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="label block mb-1">Train</label>
                <select
                  value={selectedTrain}
                  onChange={(e) => setSelectedTrain(e.target.value)}
                  className="input w-56"
                >
                  <option value="all">All Trains</option>
                  {trains.map(train => (
                    <option key={train.id} value={train.id}>{train.train_number}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="label block mb-1">Station</label>
                <select
                  value={selectedStation}
                  onChange={(e) => setSelectedStation(e.target.value)}
                  className="input w-56"
                >
                  <option value="all">All Stations</option>
                  {stations.map(station => (
                    <option key={station.id} value={station.id}>{station.name} ({station.code})</option>
                  ))}
                </select>
              </div>
            </div>
          </div>
        </div>

        {/* Schedule Table */}
        <div className="card overflow-hidden">
          <div className="table-container">
            <table className="table">
              <thead className="table-header">
                <tr>
                  <th className="table-head">Train</th>
                  <th className="table-head">Line</th>
                  <th className="table-head">Station</th>
                  <th className="table-head">Arrival</th>
                  <th className="table-head">Departure</th>
                  <th className="table-head">Sequence</th>
                  <th className="table-head">Day Type</th>
                  <th className="table-head">Status</th>
                  <th className="table-head">Actions</th>
                </tr>
              </thead>
              <tbody>
                {isLoading ? (
                  <tr>
                    <td className="table-cell" colSpan={9}>
                      <div className="flex justify-center py-8">
                        <Loader2 className="w-8 h-8 spinner" />
                      </div>
                    </td>
                  </tr>
                ) : schedules.length === 0 ? (
                  <tr>
                    <td className="table-cell text-center text-secondary-500 py-8" colSpan={9}>
                      No schedules found
                    </td>
                  </tr>
                ) : (
                  schedules.map(schedule => (
                    <tr key={schedule.id} className="table-row">
                      <td className="table-cell">
                        <Link href={`/trains/${schedule.train.id}`} className="font-mono font-medium text-secondary-900 hover:text-primary-600">
                          {schedule.train.train_number}
                        </Link>
                      </td>
                      <td className="table-cell">
                        <span
                          className="badge"
                          style={{ backgroundColor: schedule.train.line.color + '20', color: schedule.train.line.color }}
                        >
                          {schedule.train.line.code}
                        </span>
                      </td>
                      <td className="table-cell">
                        <Link href={`/stations/${schedule.station.id}`} className="text-secondary-900 hover:text-primary-600">
                          {schedule.station.name} ({schedule.station.code})
                        </Link>
                      </td>
                      <td className="table-cell">{formatTime(schedule.arrival_time)}</td>
                      <td className="table-cell">{formatTime(schedule.departure_time)}</td>
                      <td className="table-cell font-mono text-sm">{schedule.sequence}</td>
                      <td className="table-cell capitalize">{schedule.day_type}</td>
                      <td className="table-cell">
                        <span className={`badge ${schedule.is_active ? 'badge-success' : 'badge-secondary'}`}>
                          {schedule.is_active ? 'Active' : 'Inactive'}
                        </span>
                      </td>
                      <td className="table-cell">
                        <div className="flex items-center gap-1">
                          <button className="btn-ghost btn-sm" title="Edit">
                            <Clock className="w-4 h-4" />
                          </button>
                          <button className="btn-ghost btn-sm" title="Delete">
                            <AlertTriangle className="w-4 h-4 text-danger-500" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Optimize Modal */}
        {showOptimize && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
            <div className="card w-full max-w-md mx-4 p-6">
              <h2 className="text-xl font-bold text-secondary-900 mb-4">Optimize Schedule</h2>
              <div className="space-y-4">
                <div>
                  <label className="label block mb-1">Line</label>
                  <select
                    value={optimizeLine}
                    onChange={(e) => setOptimizeLine(e.target.value)}
                    className="input"
                  >
                    <option value="">Select Line</option>
                    {Array.from(new Set(stations.map(s => s.line))).map(line => (
                      <option key={line.id} value={line.id}>{line.name} ({line.code})</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="label block mb-1">Day Type</label>
                  <select
                    value={selectedDayType}
                    onChange={(e) => setSelectedDayType(e.target.value)}
                    className="input"
                  >
                    {dayTypes.map(dt => (
                      <option key={dt} value={dt}>{dt.charAt(0).toUpperCase() + dt.slice(1)}</option>
                    ))}
                  </select>
                </div>
                <div className="flex justify-end gap-3 pt-4">
                  <button onClick={() => setShowOptimize(false)} className="btn-outline">Cancel</button>
                  <button onClick={handleOptimize} className="btn-primary" disabled={!optimizeLine}>
                    <Zap className="w-4 h-4 mr-2" />
                    Optimize
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}