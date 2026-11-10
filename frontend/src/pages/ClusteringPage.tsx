import { useState, useMemo } from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, LineChart, Line } from 'recharts';
import { useApi } from '../hooks/useApi';
import { getClusters, runClustering } from '../services/api';
import { LoadingSpinner, ErrorAlert, PageHeader, Card, Badge, StatCard } from '../components/ui';
import { Brain, Play, Layers } from 'lucide-react';
import type { ClusterResult } from '../types';

const CLUSTER_COLORS = ['#2563eb', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4', '#84cc16', '#f97316', '#6366f1'];

export default function ClusteringPage() {
  const [nClusters, setNClusters] = useState<number | undefined>(undefined);
  const [clusterResult, setClusterResult] = useState<ClusterResult | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Try to load existing results
  const { data: existingClusters, loading: existingLoading } = useApi(getClusters);

  const result = clusterResult || existingClusters;

  const handleRun = async () => {
    setRunning(true);
    setError(null);
    try {
      const res = await runClustering(nClusters);
      setClusterResult(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Clustering failed');
    }
    setRunning(false);
  };

  const featureNames = useMemo(() => {
    if (!result || result.clusters.length === 0) return [];
    return Object.keys(result.clusters[0].avg_features);
  }, [result]);

  return (
    <div>
      <PageHeader title="AI Route Clustering" subtitle="Group similar routes using unsupervised machine learning based on schedule characteristics" />

      {/* Controls */}
      <Card className="mb-6">
        <div className="flex flex-wrap items-center gap-4">
          <Brain className="w-6 h-6 text-purple-600" />
          <div className="flex-1">
            <p className="text-sm text-slate-600 dark:text-slate-400">
              Routes are grouped using K-Means clustering on schedule-derived features (trip count, headway, stops, service span, etc.).
              Cluster labels are based on statistical characteristics — they are <strong>schedule-based route groups</strong>, not demand or efficiency labels.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <label className="text-sm text-slate-600 dark:text-slate-400">Clusters:</label>
            <select
              value={nClusters || 'auto'}
              onChange={e => setNClusters(e.target.value === 'auto' ? undefined : Number(e.target.value))}
              className="rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm px-3 py-1.5 dark:text-white"
            >
              <option value="auto">Auto (Elbow method)</option>
              {[2, 3, 4, 5, 6, 7, 8].map(k => (
                <option key={k} value={k}>{k} clusters</option>
              ))}
            </select>
            <button
              onClick={handleRun}
              disabled={running}
              className="px-4 py-2 bg-purple-600 text-white rounded-lg text-sm font-medium hover:bg-purple-700 transition-colors flex items-center gap-2 disabled:opacity-50"
            >
              {running ? <LoadingSpinner text="" /> : <Play className="w-4 h-4" />}
              {running ? 'Running...' : 'Run Clustering'}
            </button>
          </div>
        </div>
        {error && <ErrorAlert message={error} />}
      </Card>

      {existingLoading && !result ? <LoadingSpinner text="Loading existing cluster results..." /> : result && (
        <>
          {/* Summary stats */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
            <StatCard title="Number of Clusters" value={result.n_clusters} icon={Layers} color="purple" />
            <StatCard title="Silhouette Score" value={result.silhouette_score.toFixed(3)} icon={Brain} color="blue" subtitle="Higher = better separation (-1 to 1)" />
            <StatCard title="Routes Clustered" value={result.route_assignments.length} color="green" />
          </div>

          {/* Elbow chart */}
          {result.elbow_data.length > 0 && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
              <Card title="Elbow Method (Inertia)">
                <div className="h-64">
                  <ResponsiveContainer>
                    <LineChart data={result.elbow_data}>
                      <XAxis dataKey="k" label={{ value: 'K (clusters)', position: 'bottom', offset: -5, fontSize: 12 }} />
                      <YAxis tick={{ fontSize: 11 }} />
                      <Tooltip formatter={v => [Number(v ?? 0).toFixed(1), 'Inertia']} />
                      <Line type="monotone" dataKey="inertia" stroke="#2563eb" strokeWidth={2} dot />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </Card>
              <Card title="Silhouette Scores by K">
                <div className="h-64">
                  <ResponsiveContainer>
                    <BarChart data={result.elbow_data}>
                      <XAxis dataKey="k" />
                      <YAxis domain={[-1, 1]} tick={{ fontSize: 11 }} />
                      <Tooltip formatter={v => [Number(v ?? 0).toFixed(3), 'Silhouette Score']} />
                      <Bar dataKey="silhouette" fill="#10b981" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </Card>
            </div>
          )}

          {/* Cluster details */}
          <Card title="Cluster Characteristics" className="mb-6">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {result.clusters.map(cluster => (
                <div key={cluster.cluster_id} className="bg-slate-50 dark:bg-slate-800 rounded-lg p-4 border-l-4" style={{ borderLeftColor: CLUSTER_COLORS[cluster.cluster_id % CLUSTER_COLORS.length] }}>
                  <div className="flex items-center justify-between mb-3">
                    <h4 className="font-semibold text-slate-900 dark:text-white">Cluster {cluster.cluster_id}</h4>
                    <Badge color="blue">{cluster.size} routes</Badge>
                  </div>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mb-3 italic">{cluster.label}</p>
                  <div className="space-y-1.5">
                    {featureNames.map(feat => (
                      <div key={feat} className="flex justify-between text-xs">
                        <span className="text-slate-500 dark:text-slate-400">{feat.replace(/_/g, ' ')}</span>
                        <span className="font-medium text-slate-700 dark:text-slate-300">{cluster.avg_features[feat]?.toFixed(1)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </Card>

          {/* Route assignments */}
          <Card title="Route Assignments">
            <div className="overflow-x-auto max-h-96 overflow-y-auto">
              <table className="w-full text-sm">
                <thead className="bg-slate-50 dark:bg-slate-800 sticky top-0">
                  <tr>
                    <th className="text-left px-3 py-2 font-medium text-slate-600 dark:text-slate-400">Route</th>
                    <th className="text-left px-3 py-2 font-medium text-slate-600 dark:text-slate-400">Cluster</th>
                    {featureNames.slice(0, 5).map(feat => (
                      <th key={feat} className="text-left px-3 py-2 font-medium text-slate-600 dark:text-slate-400 text-xs">{feat.replace(/_/g, ' ')}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {result.route_assignments.map(ra => (
                    <tr key={ra.route_id} className="border-t border-slate-100 dark:border-slate-800">
                      <td className="px-3 py-2 font-medium text-slate-900 dark:text-white">{ra.route_short_name}</td>
                      <td className="px-3 py-2">
                        <span className="inline-flex items-center gap-1.5">
                          <span className="w-3 h-3 rounded-full" style={{ backgroundColor: CLUSTER_COLORS[ra.cluster % CLUSTER_COLORS.length] }} />
                          {ra.cluster}
                        </span>
                      </td>
                      {featureNames.slice(0, 5).map(feat => (
                        <td key={feat} className="px-3 py-2 text-slate-500 text-xs">{ra.features[feat]?.toFixed(1)}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      )}
    </div>
  );
}

