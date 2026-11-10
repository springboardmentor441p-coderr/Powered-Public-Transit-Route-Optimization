import { useState } from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import { useApi } from '../hooks/useApi';
import { getOverlap, getRouteOverlap } from '../services/api';
import { LoadingSpinner, ErrorAlert, PageHeader, Card, Badge } from '../components/ui';
import { GitBranch, Search } from 'lucide-react';
import type { OverlapPair, RouteOverlap } from '../types';

export default function OverlapPage() {
  const [minSimilarity, setMinSimilarity] = useState(0.3);
  const [routeSearch, setRouteSearch] = useState('');
  const [selectedOverlap, setSelectedOverlap] = useState<RouteOverlap | null>(null);
  const [overlapLoading, setOverlapLoading] = useState(false);
  const { data: pairs, loading, error, refetch } = useApi(
    () => getOverlap(minSimilarity, 100),
    [minSimilarity]
  );

  const searchRouteOverlap = async () => {
    if (!routeSearch.trim()) return;
    setOverlapLoading(true);
    try {
      const data = await getRouteOverlap(routeSearch.trim());
      setSelectedOverlap(data);
    } catch (e) {
      console.error(e);
    }
    setOverlapLoading(false);
  };

  return (
    <div>
      <PageHeader title="Route Overlap Detection" subtitle="Identify routes sharing common bus stops using Jaccard similarity" />

      {/* Explanation */}
      <Card className="mb-6">
        <div className="flex items-start gap-3">
          <GitBranch className="w-5 h-5 text-blue-600 mt-0.5 flex-shrink-0" />
          <div className="text-sm text-slate-600 dark:text-slate-400">
            <p className="mb-1"><strong>Jaccard Similarity:</strong> J(A,B) = |A ∩ B| / |A ∪ B|</p>
            <p>Where A and B are the sets of stops served by routes A and B. Higher similarity means more shared stops.
            Note: shared stops do not automatically indicate that routes should be merged — they may serve different purposes, schedules, or directions.</p>
          </div>
        </div>
      </Card>

      {/* Controls */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <Card title="Filter Overlapping Pairs">
          <div className="flex items-center gap-4">
            <label className="text-sm text-slate-600 dark:text-slate-400">Min Jaccard similarity:</label>
            <input
              type="range"
              min="0.1"
              max="0.9"
              step="0.05"
              value={minSimilarity}
              onChange={e => setMinSimilarity(Number(e.target.value))}
              className="flex-1"
            />
            <span className="text-sm font-semibold text-blue-600 w-12">{(minSimilarity * 100).toFixed(0)}%</span>
          </div>
        </Card>

        <Card title="Compare Specific Route">
          <div className="flex gap-2">
            <input
              type="text"
              value={routeSearch}
              onChange={e => setRouteSearch(e.target.value)}
              placeholder="Enter route ID..."
              className="flex-1 px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm dark:text-white"
              onKeyDown={e => e.key === 'Enter' && searchRouteOverlap()}
            />
            <button
              onClick={searchRouteOverlap}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors flex items-center gap-1"
            >
              <Search className="w-4 h-4" /> Compare
            </button>
          </div>
        </Card>
      </div>

      {/* Selected route overlap */}
      {overlapLoading ? <LoadingSpinner text="Finding overlapping routes..." /> : selectedOverlap && (
        <Card title={`Routes overlapping with ${selectedOverlap.route_name} (ID: ${selectedOverlap.route_id})`} className="mb-6">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 dark:bg-slate-800">
                <tr>
                  <th className="text-left px-3 py-2 font-medium text-slate-600 dark:text-slate-400">Route</th>
                  <th className="text-left px-3 py-2 font-medium text-slate-600 dark:text-slate-400">Shared Stops</th>
                  <th className="text-left px-3 py-2 font-medium text-slate-600 dark:text-slate-400">Total Stops</th>
                  <th className="text-left px-3 py-2 font-medium text-slate-600 dark:text-slate-400">Jaccard Similarity</th>
                </tr>
              </thead>
              <tbody>
                {selectedOverlap.overlapping_routes.map(pair => (
                  <tr key={pair.route_b_id} className="border-t border-slate-100 dark:border-slate-800">
                    <td className="px-3 py-2 font-medium text-slate-900 dark:text-white">{pair.route_b_name} ({pair.route_b_id})</td>
                    <td className="px-3 py-2">{pair.shared_stops}</td>
                    <td className="px-3 py-2">{pair.total_stops}</td>
                    <td className="px-3 py-2">
                      <div className="flex items-center gap-2">
                        <div className="w-24 bg-slate-200 dark:bg-slate-700 rounded-full h-2">
                          <div className="bg-blue-600 rounded-full h-2" style={{ width: `${pair.jaccard_similarity * 100}%` }} />
                        </div>
                        <span className="text-slate-700 dark:text-slate-300 font-medium">{(pair.jaccard_similarity * 100).toFixed(1)}%</span>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {selectedOverlap.overlapping_routes.length === 0 && (
              <p className="py-4 text-center text-slate-500">No overlapping routes found for this route.</p>
            )}
          </div>
        </Card>
      )}

      {/* All pairs */}
      {loading ? <LoadingSpinner text="Calculating route overlap..." /> : error ? <ErrorAlert message={error} onRetry={refetch} /> : pairs && (
        <>
          <Card title={`Highly Overlapping Route Pairs (Jaccard ≥ ${(minSimilarity * 100).toFixed(0)}%)`}>
            {pairs.length > 0 ? (
              <>
                <div className="h-80 mb-4">
                  <ResponsiveContainer>
                    <BarChart data={pairs.slice(0, 20)} margin={{ left: 80, right: 20, top: 5, bottom: 5 }}>
                      <XAxis dataKey="jaccard_similarity" tickFormatter={v => `${(v * 100).toFixed(0)}%`} type="number" domain={[0, 1]} />
                      <YAxis dataKey={(d: OverlapPair) => `${d.route_a_name}–${d.route_b_name}`} type="category" width={75} tick={{ fontSize: 10 }} />
                      <Tooltip formatter={v => [`${(Number(v ?? 0) * 100).toFixed(1)}%`, 'Jaccard Similarity']} />
                      <Bar dataKey="jaccard_similarity" fill="#2563eb" radius={[0, 4, 4, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-slate-50 dark:bg-slate-800">
                      <tr>
                        <th className="text-left px-3 py-2 font-medium text-slate-600 dark:text-slate-400">Route A</th>
                        <th className="text-left px-3 py-2 font-medium text-slate-600 dark:text-slate-400">Route B</th>
                        <th className="text-left px-3 py-2 font-medium text-slate-600 dark:text-slate-400">Shared</th>
                        <th className="text-left px-3 py-2 font-medium text-slate-600 dark:text-slate-400">Union</th>
                        <th className="text-left px-3 py-2 font-medium text-slate-600 dark:text-slate-400">Similarity</th>
                      </tr>
                    </thead>
                    <tbody>
                      {pairs.map((pair, i) => (
                        <tr key={i} className="border-t border-slate-100 dark:border-slate-800">
                          <td className="px-3 py-2 font-medium text-slate-900 dark:text-white">{pair.route_a_name}</td>
                          <td className="px-3 py-2 font-medium text-slate-900 dark:text-white">{pair.route_b_name}</td>
                          <td className="px-3 py-2">{pair.shared_stops}</td>
                          <td className="px-3 py-2">{pair.total_stops}</td>
                          <td className="px-3 py-2">
                            <Badge color={pair.jaccard_similarity >= 0.7 ? 'red' : pair.jaccard_similarity >= 0.5 ? 'amber' : 'blue'}>
                              {(pair.jaccard_similarity * 100).toFixed(1)}%
                            </Badge>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            ) : (
              <p className="text-center py-8 text-slate-500">No route pairs found with Jaccard similarity ≥ {(minSimilarity * 100).toFixed(0)}%</p>
            )}
          </Card>
        </>
      )}
    </div>
  );
}

