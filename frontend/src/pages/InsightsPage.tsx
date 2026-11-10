import { useCallback } from 'react'
import { CircleHelp, Info, Layers3 } from 'lucide-react'
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { DataNotice, EmptyState, ErrorState, LoadingState, PageTitle, Panel, formatNumber } from '../components/ui'
import { useResource } from '../hooks/useResource'
import { api } from '../services/api'

export function InsightsPage() {
  const load = useCallback(async () => {
    const [clusters, metrics, models] = await Promise.all([api.clusters(), api.modelMetrics(), api.models()])
    return { clusters, metrics, models }
  }, [])
  const { data, loading, error, reload } = useResource(load)

  return (
    <>
      <PageTitle eyebrow="Unsupervised analysis" title="Machine learning insights" description="How K-Means and DBSCAN group routes with similar scheduled-service and stop-network features." />
      <div className="space-y-6">
        <DataNotice tone="amber"><strong>Interpretation:</strong> clusters summarize GTFS schedule characteristics. They do not predict passenger demand, overcrowding, efficiency, or actual operating performance. DBSCAN “noise” means a route falls outside a dense group in the selected feature space.</DataNotice>
        {loading && <LoadingState label="Loading saved models and profiles…" />}{error && <ErrorState message={error} onRetry={reload} />}
        {data && <>
          <div className="grid gap-5 lg:grid-cols-2">
            {data.models.map((model) => {
              const metric = data.metrics.find((item) => item.algorithm.toLowerCase() === model.model.toLowerCase())
              const groups = data.clusters.filter((item) => item.algorithm.toLowerCase() === model.model.toLowerCase())
              const color = model.model === 'kmeans' ? '#0f9b8e' : '#5277d8'
              return <Panel key={model.model} title={model.model === 'kmeans' ? 'K-Means' : 'DBSCAN'} subtitle={model.model === 'kmeans' ? `Saved model · k = ${model.selected_k ?? '—'}` : `Saved model · ε = ${model.eps?.toFixed(3) ?? '—'} · min samples = ${model.min_samples ?? '—'}`}>
                <div className="grid grid-cols-3 gap-2">
                  <div className="rounded-xl bg-slate-50 p-3"><p className="text-[10px] text-slate-500">Clusters</p><strong className="mt-1 block text-lg text-slate-900">{metric?.n_clusters ?? '—'}</strong></div>
                  <div className="rounded-xl bg-slate-50 p-3"><p className="text-[10px] text-slate-500">Silhouette</p><strong className="mt-1 block text-lg text-slate-900">{metric?.silhouette_score?.toFixed(3) ?? '—'}</strong><span className="text-[9px] text-slate-400">sample {formatNumber(metric?.silhouette_sample_size)}</span></div>
                  <div className="rounded-xl bg-slate-50 p-3"><p className="text-[10px] text-slate-500">Davies–Bouldin</p><strong className="mt-1 block text-lg text-slate-900">{metric?.davies_bouldin_index?.toFixed(3) ?? '—'}</strong></div>
                </div>
                <div className="mt-4 flex items-center justify-between text-xs text-slate-500"><span>Routes included in evaluation</span><strong className="text-slate-800">{formatNumber(metric?.inlier_count)}</strong></div>
                {model.model === 'dbscan' && <div className="mt-2 flex items-center justify-between text-xs text-slate-500"><span>Noise / outlier label count</span><strong className="text-slate-800">{formatNumber(metric?.noise_count)}</strong></div>}
                <div className="mt-5"><p className="mb-3 text-xs font-semibold text-slate-700">Cluster sizes</p><div className="h-[175px]">
                  <ResponsiveContainer width="100%" height="100%"><BarChart data={groups.map((cluster) => ({ name: cluster.is_noise ? 'Noise' : `Cluster ${cluster.cluster_id}`, count: cluster.route_count, noise: cluster.is_noise }))} margin={{ top: 4, right: 4, left: -24, bottom: 0 }}>
                    <CartesianGrid stroke="#e9eef3" vertical={false} /><XAxis dataKey="name" tickLine={false} axisLine={false} tick={{ fill: '#788697', fontSize: 10 }} /><YAxis tickLine={false} axisLine={false} tick={{ fill: '#788697', fontSize: 10 }} /><Tooltip formatter={(value) => [formatNumber(Number(value)), 'Routes']} /><Bar dataKey="count" radius={[5, 5, 0, 0]} maxBarSize={42}>{groups.map((cluster) => <Cell key={cluster.cluster_id} fill={cluster.is_noise ? '#94a3b8' : color} />)}</Bar>
                  </BarChart></ResponsiveContainer>
                </div></div>
              </Panel>
            })}
          </div>

          <Panel title="Cluster profiles" subtitle="Median values are calculated from the original, non-normalized route features.">
            {data.clusters.some((cluster) => cluster.profile) ? <div className="overflow-x-auto"><table className="w-full min-w-[900px] text-left text-sm"><thead><tr className="border-b border-slate-100 text-[10px] font-bold uppercase tracking-wide text-slate-400"><th className="pb-3">Model / cluster</th><th className="pb-3">Routes</th><th className="pb-3">Median trip records</th><th className="pb-3">Median stops</th><th className="pb-3">Median headway</th><th className="pb-3">Peak share</th><th className="pb-3">Schedule span</th><th className="pb-3">Evidence-based profile</th></tr></thead><tbody>{data.clusters.map((cluster) => {
              const profile = cluster.profile
              return <tr key={`${cluster.algorithm}-${cluster.cluster_id}`} className="border-b border-slate-50 align-top last:border-0"><td className="py-3"><span className={`cluster-pill ${cluster.algorithm === 'KMeans' ? 'bg-teal-50 text-teal-800' : 'bg-blue-50 text-blue-800'}`}>{cluster.algorithm}</span><span className="ml-2 text-xs font-semibold text-slate-700">{cluster.is_noise ? 'Noise' : cluster.cluster_id}</span></td><td className="py-3 font-semibold">{formatNumber(cluster.route_count)}</td><td className="py-3">{formatNumber(profile?.median_total_scheduled_trip_records, 1)}</td><td className="py-3">{formatNumber(profile?.median_unique_stop_count, 1)}</td><td className="py-3">{profile?.median_average_first_stop_headway_seconds == null ? '—' : `${formatNumber(profile.median_average_first_stop_headway_seconds / 60, 1)} min`}</td><td className="py-3">{profile?.median_peak_departure_share == null ? '—' : `${(profile.median_peak_departure_share * 100).toFixed(1)}%`}</td><td className="py-3">{profile?.median_scheduled_service_span_hours == null ? '—' : `${formatNumber(profile.median_scheduled_service_span_hours, 1)} h`}</td><td className="max-w-sm py-3 text-xs leading-5 text-slate-600">{profile?.interpretation ?? 'No profile available.'}</td></tr>
            })}</tbody></table></div> : <EmptyState title="No cluster profiles available" />}
          </Panel>

          <Panel title="How to read these scores" subtitle="Evaluation is internal and has no external route labels for validation.">
            <div className="grid gap-4 md:grid-cols-3">
              <div className="rounded-xl bg-slate-50 p-4"><div className="mb-2 flex items-center gap-2 text-sm font-semibold text-slate-800"><Layers3 className="h-4 w-4 text-teal-700" />Silhouette score</div><p className="text-xs leading-5 text-slate-500">Measures how separated the assigned groups are within the fitted feature space. Reported on a 2,000-route sample for this feed.</p></div>
              <div className="rounded-xl bg-slate-50 p-4"><div className="mb-2 flex items-center gap-2 text-sm font-semibold text-slate-800"><CircleHelp className="h-4 w-4 text-blue-700" />Davies–Bouldin</div><p className="text-xs leading-5 text-slate-500">Compares within-cluster spread to separation between clusters. Scores are diagnostic and do not establish service quality.</p></div>
              <div className="rounded-xl bg-slate-50 p-4"><div className="mb-2 flex items-center gap-2 text-sm font-semibold text-slate-800"><Info className="h-4 w-4 text-amber-700" />Model limits</div><p className="text-xs leading-5 text-slate-500">Calendar exceptions, frequency-based service, and route shapes are absent. The backend does not expose PCA coordinates, so this page does not draw a PCA chart.</p></div>
            </div>
          </Panel>
        </>}
      </div>
    </>
  )
}
