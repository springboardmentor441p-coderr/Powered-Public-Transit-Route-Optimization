import { useCallback } from 'react'
import { Activity, BusFront, Clock3, Route, ShieldCheck, TrendingUp } from 'lucide-react'
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { DataNotice, ErrorState, LoadingState, MetricCard, PageTitle, Panel, formatDuration, formatNumber } from '../components/ui'
import { useResource } from '../hooks/useResource'
import { api } from '../services/api'

export function OverviewPage() {
  const load = useCallback(async () => {
    const [dataset, routes, stops, hours, headways, clusters] = await Promise.all([
      api.datasetStatistics(), api.routeStatistics(), api.stopStatistics(), api.scheduledTripsByHour(), api.headways(), api.clusters(),
    ])
    return { dataset, routes, stops, hours, headways, clusters }
  }, [])
  const { data, loading, error, reload } = useResource(load)

  return (
    <>
      <PageTitle eyebrow="Network overview" title="Good morning, Chennai" description="A data-led view of scheduled public transport service across the MTC network." />
      {loading && <LoadingState label="Loading network summaries…" />}
      {error && <ErrorState message={error} onRetry={reload} />}
      {data && <div className="space-y-6">
        <DataNotice tone="teal">Every figure describes scheduled GTFS service. This dataset does not contain passenger demand, occupancy, traffic conditions, or live vehicle operations.</DataNotice>
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <MetricCard label="Routes in feed" value={formatNumber(data.routes.route_count)} detail={`${formatNumber(data.routes.routes_with_trips)} have scheduled trip records`} icon={Route} accent="teal" />
          <MetricCard label="Stops in feed" value={formatNumber(data.stops.stop_count)} detail={`${formatNumber(data.stops.stops_with_scheduled_trips)} referenced by scheduled service`} icon={BusFront} accent="blue" />
          <MetricCard label="Scheduled trip records" value={formatNumber(data.routes.scheduled_trip_records)} detail="Trip definitions present in the supplied GTFS feed" icon={Activity} accent="violet" />
          <MetricCard label="Median estimated headway" value={formatDuration(data.headways.median_of_group_medians_seconds)} detail={`${formatNumber(data.headways.groups_with_estimates)} route/service/direction groups with estimates`} icon={Clock3} accent="amber" />
        </div>

        <div className="grid gap-6 xl:grid-cols-[1.45fr_1fr]">
          <Panel title="Scheduled trip starts by hour" subtitle="Trip records grouped by scheduled service-hour start. Counts are not passenger volumes.">
            <div className="h-[290px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={data.hours} margin={{ top: 8, right: 8, left: -18, bottom: 4 }}>
                  <CartesianGrid stroke="#e9eef3" vertical={false} />
                  <XAxis dataKey="service_hour" tickFormatter={(hour: number) => `${String(hour).padStart(2, '0')}:00`} tickLine={false} axisLine={false} tick={{ fill: '#788697', fontSize: 11 }} interval={2} />
                  <YAxis tickLine={false} axisLine={false} tick={{ fill: '#788697', fontSize: 11 }} />
                  <Tooltip labelFormatter={(hour) => `Service hour ${String(hour).padStart(2, '0')}:00`} formatter={(value) => [formatNumber(Number(value)), 'Scheduled trip records']} contentStyle={{ borderRadius: 12, borderColor: '#e2e8f0', boxShadow: '0 8px 24px #0f172a14' }} />
                  <Bar dataKey="scheduled_trip_records" fill="#0f9b8e" radius={[5, 5, 0, 0]} maxBarSize={22} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Panel>
          <Panel title="Route cluster distribution" subtitle="Route counts in the saved Phase 4 unsupervised models.">
            <div className="h-[290px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={data.clusters.map((cluster) => ({ name: `${cluster.algorithm === 'KMeans' ? 'K' : 'D'} · ${cluster.cluster_id === -1 ? 'Noise' : cluster.cluster_id}`, count: cluster.route_count, algorithm: cluster.algorithm, noise: cluster.is_noise }))} margin={{ top: 8, right: 2, left: -22, bottom: 4 }}>
                  <CartesianGrid stroke="#e9eef3" vertical={false} />
                  <XAxis dataKey="name" tickLine={false} axisLine={false} tick={{ fill: '#788697', fontSize: 10 }} interval={0} angle={-35} textAnchor="end" height={54} />
                  <YAxis tickLine={false} axisLine={false} tick={{ fill: '#788697', fontSize: 11 }} />
                  <Tooltip formatter={(value) => [formatNumber(Number(value)), 'Routes']} contentStyle={{ borderRadius: 12, borderColor: '#e2e8f0' }} />
                  <Bar dataKey="count" radius={[5, 5, 0, 0]} maxBarSize={28}>{data.clusters.map((cluster, index) => <Cell key={`${cluster.algorithm}-${cluster.cluster_id}`} fill={cluster.is_noise ? '#94a3b8' : cluster.algorithm === 'KMeans' ? '#0f9b8e' : '#5277d8'} opacity={index % 2 ? 0.72 : 1} />)}</Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            <p className="mt-2 text-[11px] leading-5 text-slate-500">K-Means and DBSCAN counts come from separate models and should not be added together. DBSCAN noise is a feature-space label, not a service judgment.</p>
          </Panel>
        </div>

        <div className="grid gap-6 xl:grid-cols-[1fr_1.45fr]">
          <Panel title="Schedule coverage" subtitle="Records included in the feed and analysis.">
            <div className="space-y-4">
              <div className="flex items-start justify-between gap-3 border-b border-slate-100 pb-3"><div><p className="text-sm font-medium text-slate-700">Routes with trip records</p><p className="mt-1 text-xs text-slate-500">Routes without trips remain in the source catalogue.</p></div><strong className="text-lg text-slate-900">{formatNumber(data.routes.routes_with_trips)}</strong></div>
              <div className="flex items-start justify-between gap-3 border-b border-slate-100 pb-3"><div><p className="text-sm font-medium text-slate-700">Stops served</p><p className="mt-1 text-xs text-slate-500">Stops referenced in scheduled stop times.</p></div><strong className="text-lg text-slate-900">{formatNumber(data.stops.stops_served_by_routes)}</strong></div>
              <div className="flex items-start justify-between gap-3"><div><p className="text-sm font-medium text-slate-700">Feed validation</p><p className="mt-1 text-xs text-slate-500">Phase 1 structure and relationship checks.</p></div><span className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2.5 py-1 text-xs font-semibold text-amber-700"><ShieldCheck className="h-3.5 w-3.5" />{data.dataset.gtfs_quality_status?.replaceAll('_', ' ') ?? 'Unavailable'}</span></div>
            </div>
          </Panel>
          <Panel title="Data scope & limitations" subtitle="Important context for interpreting these summaries.">
            <div className="grid gap-3 sm:grid-cols-2">
              {(data.dataset.limitations.notes ?? []).map((note) => <div key={note} className="rounded-xl bg-slate-50 p-3 text-xs leading-5 text-slate-600">{note}</div>)}
            </div>
            <div className="mt-4 flex items-center gap-2 text-xs text-slate-500"><TrendingUp className="h-4 w-4 text-teal-600" />Median stops per route: <span className="font-semibold text-slate-700">{formatNumber(data.routes.median_stops_per_route, 1)}</span></div>
          </Panel>
        </div>
      </div>}
    </>
  )
}
