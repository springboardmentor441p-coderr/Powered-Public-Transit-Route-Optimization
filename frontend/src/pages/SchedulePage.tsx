import { useMemo, useState } from 'react';
import { useApi } from '../hooks/useApi';
import { getFrequencyStats, getServiceStats } from '../services/api';
import { LoadingSpinner, ErrorAlert, PageHeader, Card, Badge } from '../components/ui';
import { ArrowUpDown } from 'lucide-react';
import type { FrequencyStats } from '../types';

export default function SchedulePage() {
  const [page, setPage] = useState(1);
  const [sortBy, setSortBy] = useState('trip_count');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const [highFrequencyOnly, setHighFrequencyOnly] = useState(false);
  const { data: freqData, loading: fLoad, error: fErr, refetch: fRefetch } = useApi(
    () => getFrequencyStats(page, 50, highFrequencyOnly),
    [page, highFrequencyOnly]
  );
  const { data: serviceData, loading: sLoad, error: sErr } = useApi(getServiceStats);

  const toggleSort = (field: string) => {
    if (sortBy === field) {
      setSortOrder(o => o === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(field);
      setSortOrder('desc');
    }
    setPage(1);
  };

  const sortedItems = useMemo(() => {
    const items = [...(freqData?.items ?? [])];
    return items.sort((a, b) => {
      const left = a[sortBy as keyof FrequencyStats];
      const right = b[sortBy as keyof FrequencyStats];
      const comparison = typeof left === 'number' && typeof right === 'number' ? left - right : String(left ?? '').localeCompare(String(right ?? ''));
      return sortOrder === 'asc' ? comparison : -comparison;
    });
  }, [freqData, sortBy, sortOrder]);

  return (
    <div>
      <PageHeader title="Schedule & Frequency Analysis" subtitle="Scheduled service frequency indicators derived from GTFS timetable data" />

      {/* Service calendars */}
      {sLoad ? null : sErr ? <ErrorAlert message={sErr} /> : serviceData && (
        <Card title="Service Calendars" className="mb-6">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {serviceData.filter(s => !s.service_id.includes('<')).map(s => (
              <div key={s.service_id} className="bg-slate-50 dark:bg-slate-800 rounded-lg p-4">
                <div className="flex items-center justify-between mb-2">
                  <h4 className="font-semibold text-slate-900 dark:text-white">{s.service_id}</h4>
                  <Badge color="blue">{s.trip_count} trips</Badge>
                </div>
                <div className="flex gap-1 mb-2">
                  {['Mon','Tue','Wed','Thu','Fri','Sat','Sun'].map(day => (
                    <span key={day} className={`w-8 h-8 rounded text-xs flex items-center justify-center font-medium ${
                      s.days.includes(day) ? 'bg-blue-600 text-white' : 'bg-slate-200 dark:bg-slate-700 text-slate-400'
                    }`}>{day[0]}</span>
                  ))}
                </div>
                <p className="text-xs text-slate-500">{s.route_count} routes • {s.start_date} – {s.end_date}</p>
              </div>
            ))}
          </div>
          <p className="text-xs text-slate-400 mt-3 italic">
            These are scheduled service calendars from the GTFS feed and may not reflect actual current operations.
          </p>
        </Card>
      )}

      {/* Frequency table */}
      {fLoad ? <LoadingSpinner text="Loading frequency data..." /> : fErr ? <ErrorAlert message={fErr} onRetry={fRefetch} /> : freqData && (
        <Card title="Route Frequency Statistics">
          <label className="mb-4 flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
            <input type="checkbox" checked={highFrequencyOnly} onChange={event => { setHighFrequencyOnly(event.target.checked); setPage(1); }} className="rounded border-slate-300 text-blue-600 focus:ring-blue-500" />
            Show only routes flagged high-frequency by the schedule-derived feature rule
          </label>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 dark:bg-slate-800">
                <tr>
                  <th className="text-left px-3 py-2 text-slate-600 dark:text-slate-400 font-medium">Route</th>
                  <th className="text-left px-3 py-2 text-slate-600 dark:text-slate-400 font-medium cursor-pointer hover:text-blue-600" onClick={() => toggleSort('trip_count')}>
                    <span className="flex items-center gap-1">Trips <ArrowUpDown className="w-3 h-3" /></span>
                  </th>
                  <th className="text-left px-3 py-2 text-slate-600 dark:text-slate-400 font-medium cursor-pointer hover:text-blue-600" onClick={() => toggleSort('avg_headway_minutes')}>
                    <span className="flex items-center gap-1">Avg Headway <ArrowUpDown className="w-3 h-3" /></span>
                  </th>
                  <th className="text-left px-3 py-2 text-slate-600 dark:text-slate-400 font-medium">Min/Max Headway</th>
                  <th className="text-left px-3 py-2 text-slate-600 dark:text-slate-400 font-medium">First Dep</th>
                  <th className="text-left px-3 py-2 text-slate-600 dark:text-slate-400 font-medium">Last Dep</th>
                  <th className="text-left px-3 py-2 text-slate-600 dark:text-slate-400 font-medium">Service Span</th>
                  <th className="text-left px-3 py-2 text-slate-600 dark:text-slate-400 font-medium">Trips/Hour</th>
                </tr>
              </thead>
              <tbody>
                  {sortedItems.map(r => (
                  <tr key={r.route_id} className="border-t border-slate-100 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/50">
                    <td className="px-3 py-2">
                      <span className="font-semibold text-slate-900 dark:text-white">{r.route_short_name}</span>
                    </td>
                    <td className="px-3 py-2 text-slate-700 dark:text-slate-300">{r.trip_count}</td>
                    <td className="px-3 py-2 text-slate-700 dark:text-slate-300">{r.avg_headway_minutes != null ? `${r.avg_headway_minutes.toFixed(1)} min` : '—'}</td>
                    <td className="px-3 py-2 text-slate-500">{r.min_headway_minutes != null ? `${r.min_headway_minutes.toFixed(0)}–${r.max_headway_minutes?.toFixed(0)} min` : '—'}</td>
                    <td className="px-3 py-2 text-slate-500">{r.first_departure || '—'}</td>
                    <td className="px-3 py-2 text-slate-500">{r.last_departure || '—'}</td>
                    <td className="px-3 py-2 text-slate-500">{r.service_span_hours != null ? `${r.service_span_hours.toFixed(1)}h` : '—'}</td>
                    <td className="px-3 py-2 text-slate-500">{r.trips_per_hour != null ? r.trips_per_hour.toFixed(1) : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex items-center justify-between mt-4 pt-3 border-t border-slate-200 dark:border-slate-700">
            <span className="text-xs text-slate-500">{freqData.total} routes total</span>
            <div className="flex gap-2">
              <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page <= 1} className="px-3 py-1 text-xs rounded bg-slate-100 dark:bg-slate-800 disabled:opacity-50">Prev</button>
              <span className="text-xs text-slate-500 py-1">{page}/{freqData.total_pages}</span>
              <button onClick={() => setPage(p => Math.min(freqData.total_pages, p + 1))} disabled={page >= freqData.total_pages} className="px-3 py-1 text-xs rounded bg-slate-100 dark:bg-slate-800 disabled:opacity-50">Next</button>
            </div>
          </div>
          {sortedItems.length === 0 && <p className="py-8 text-center text-sm text-slate-500">No frequency records are available for this filter.</p>}
          <p className="text-xs text-slate-400 mt-3 italic">
            Headways calculated from scheduled departure times at route origin stops. These are scheduled frequencies, not observed operating frequencies.
          </p>
        </Card>
      )}
    </div>
  );
}

