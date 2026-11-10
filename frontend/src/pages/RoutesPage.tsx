import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeftRight, ChevronLeft, ChevronRight, Search, X } from 'lucide-react'
import { DataNotice, EmptyState, ErrorState, LoadingState, PageTitle, Panel, formatDuration, formatNumber } from '../components/ui'
import { useResource } from '../hooks/useResource'
import { api, type RouteQuery } from '../services/api'

const PAGE_SIZE = 50

export function RoutesPage() {
  const navigate = useNavigate()
  const [searchInput, setSearchInput] = useState('')
  const [query, setQuery] = useState('')
  const [minTrips, setMinTrips] = useState('')
  const [minStops, setMinStops] = useState('')
  const [maxHeadway, setMaxHeadway] = useState('')
  const [algorithm, setAlgorithm] = useState<'kmeans' | 'dbscan'>('kmeans')
  const [clusterId, setClusterId] = useState('')
  const [offset, setOffset] = useState(0)
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const [detailId, setDetailId] = useState<string | null>(null)

  useEffect(() => {
    const timer = window.setTimeout(() => { setQuery(searchInput); setOffset(0) }, 300)
    return () => window.clearTimeout(timer)
  }, [searchInput])

  const filters = useMemo<RouteQuery>(() => ({
    limit: PAGE_SIZE, offset, ...(query ? { q: query } : {}),
    ...(minTrips ? { min_trips: Number(minTrips) } : {}),
    ...(minStops ? { min_stops: Number(minStops) } : {}),
    ...(maxHeadway ? { max_headway_seconds: Number(maxHeadway) } : {}),
    ...(clusterId ? { algorithm, cluster_id: Number(clusterId) } : {}),
  }), [offset, query, minTrips, minStops, maxHeadway, algorithm, clusterId])
  const loadRoutes = useCallback(() => api.listRoutes(filters), [filters])
  const { data, loading, error, reload } = useResource(loadRoutes, [loadRoutes])

  const loadDetail = useCallback(async () => {
    if (!detailId) return null
    const [route, features, cluster] = await Promise.all([api.route(detailId), api.routeFeatures(detailId), api.routeCluster(detailId)])
    return { route, features, cluster }
  }, [detailId])
  const detail = useResource(loadDetail, [loadDetail])

  const toggleSelection = (routeId: string) => setSelectedIds((current) => {
    if (current.includes(routeId)) return current.filter((id) => id !== routeId)
    return current.length < 20 ? [...current, routeId] : current
  })
  const togglePage = () => {
    const pageIds = data?.items.map((route) => route.route_id) ?? []
    const allSelected = pageIds.length > 0 && pageIds.every((id) => selectedIds.includes(id))
    setSelectedIds((current) => allSelected
      ? current.filter((id) => !pageIds.includes(id))
      : [...new Set([...current, ...pageIds])].slice(0, 20))
  }

  return (
    <>
      <PageTitle eyebrow="Network catalogue" title="Route explorer" description="Search scheduled routes, inspect their service features, and compare their network characteristics." action={<button disabled={selectedIds.length < 2} onClick={() => navigate('/compare', { state: { routeIds: selectedIds } })} className="inline-flex items-center gap-2 rounded-xl bg-ink px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-40"><ArrowLeftRight className="h-4 w-4" />Compare selected <span className="rounded-md bg-white/15 px-1.5 py-0.5 text-xs">{selectedIds.length}</span></button>} />
      <div className="space-y-5">
        <DataNotice>{selectedIds.length >= 20 ? 'Comparison selection limit reached (20 routes). Remove a selection to add another. ' : ''}Trip records and headways are scheduled GTFS indicators. They do not measure passenger demand, actual waiting time, or delivered operations.</DataNotice>
        <Panel className="!p-4">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-[minmax(220px,1.5fr)_repeat(3,minmax(125px,0.7fr))_minmax(160px,0.8fr)_minmax(130px,0.65fr)]">
            <label className="relative"><Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" /><input value={searchInput} onChange={(event) => setSearchInput(event.target.value)} placeholder="Search route ID or name" className="field pl-9" /></label>
            <input type="number" min="0" value={minTrips} onChange={(event) => { setMinTrips(event.target.value); setOffset(0) }} placeholder="Min trip records" className="field" />
            <input type="number" min="0" value={minStops} onChange={(event) => { setMinStops(event.target.value); setOffset(0) }} placeholder="Min stops" className="field" />
            <input type="number" min="0" value={maxHeadway} onChange={(event) => { setMaxHeadway(event.target.value); setOffset(0) }} placeholder="Max headway (sec)" className="field" />
            <div className="flex gap-2"><select value={algorithm} onChange={(event) => setAlgorithm(event.target.value as 'kmeans' | 'dbscan')} className="field min-w-0 flex-1"><option value="kmeans">K-Means</option><option value="dbscan">DBSCAN</option></select><input type="number" value={clusterId} onChange={(event) => { setClusterId(event.target.value); setOffset(0) }} placeholder="Cluster" className="field w-24" /></div>
            <button onClick={() => { setSearchInput(''); setQuery(''); setMinTrips(''); setMinStops(''); setMaxHeadway(''); setClusterId(''); setOffset(0) }} className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-200 px-3 text-sm font-medium text-slate-600 hover:bg-slate-50"><X className="h-4 w-4" />Clear filters</button>
          </div>
        </Panel>
        <Panel title="Routes" subtitle={data ? `${formatNumber(data.total)} matching route records` : 'Search and filter the GTFS route catalogue.'} action={<span className="rounded-lg bg-slate-100 px-2.5 py-1.5 text-xs font-semibold text-slate-600">Page size {PAGE_SIZE}</span>}>
          {loading && <LoadingState label="Loading routes…" />}
          {error && <ErrorState message={error} onRetry={reload} />}
          {!loading && !error && data && (data.items.length ? <>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[930px] text-left text-sm">
                <thead><tr className="border-b border-slate-100 text-[11px] font-semibold uppercase tracking-wide text-slate-400"><th className="w-10 pb-3"><input type="checkbox" aria-label="Select all routes on this page" checked={data.items.length > 0 && data.items.every((route) => selectedIds.includes(route.route_id))} disabled={selectedIds.length >= 20 && !data.items.every((route) => selectedIds.includes(route.route_id))} onChange={togglePage} className="check" /></th><th className="pb-3">Route</th><th className="pb-3">Scheduled trips</th><th className="pb-3">Stops</th><th className="pb-3">Avg first-stop headway</th><th className="pb-3">First service</th><th className="pb-3">Clusters</th><th className="pb-3" /></tr></thead>
                <tbody>{data.items.map((route) => <tr key={route.route_id} className="border-b border-slate-50 last:border-0 hover:bg-slate-50/70">
                  <td className="py-3.5"><input type="checkbox" aria-label={`Select route ${route.route_id}`} checked={selectedIds.includes(route.route_id)} disabled={!selectedIds.includes(route.route_id) && selectedIds.length >= 20} onChange={() => toggleSelection(route.route_id)} className="check" /></td>
                  <td className="py-3.5"><button className="text-left" onClick={() => setDetailId(route.route_id)}><span className="font-semibold text-slate-900 hover:text-teal-700">{route.route_short_name || route.route_id}</span><span className="mt-0.5 block max-w-[280px] truncate text-xs text-slate-500">{route.route_long_name || `Route ${route.route_id}`}</span></button></td>
                  <td className="py-3.5 font-medium tabular-nums text-slate-700">{formatNumber(route.trip_count)}</td>
                  <td className="py-3.5 tabular-nums text-slate-600">{formatNumber(route.stop_count)}</td>
                  <td className="py-3.5 text-slate-600">{formatDuration(route.average_first_stop_headway_seconds)}</td>
                  <td className="py-3.5 text-slate-600">{route.first_service_time ?? '—'}</td>
                  <td className="py-3.5"><div className="flex gap-1"><span className="cluster-pill bg-teal-50 text-teal-800">K {route.kmeans_cluster_id ?? '—'}</span><span className="cluster-pill bg-blue-50 text-blue-800">D {route.dbscan_cluster_id === -1 ? 'noise' : route.dbscan_cluster_id ?? '—'}</span></div></td>
                  <td className="py-3.5 text-right"><button onClick={() => setDetailId(route.route_id)} className="rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs font-semibold text-slate-600 hover:border-teal-300 hover:text-teal-700">Details</button></td>
                </tr>)}</tbody>
              </table>
            </div>
            <div className="mt-5 flex flex-col gap-3 border-t border-slate-100 pt-4 sm:flex-row sm:items-center sm:justify-between"><p className="text-xs text-slate-500">Showing {formatNumber(offset + 1)}–{formatNumber(Math.min(offset + data.items.length, data.total))} of {formatNumber(data.total)}</p><div className="flex gap-2"><button disabled={offset === 0} onClick={() => setOffset((value) => Math.max(0, value - PAGE_SIZE))} className="page-button"><ChevronLeft className="h-4 w-4" />Previous</button><button disabled={offset + PAGE_SIZE >= data.total} onClick={() => setOffset((value) => value + PAGE_SIZE)} className="page-button">Next<ChevronRight className="h-4 w-4" /></button></div></div>
          </> : <EmptyState title="No routes match these filters" />)}
        </Panel>
      </div>

      {detailId && <div className="fixed inset-0 z-40 flex justify-end bg-slate-950/35" onMouseDown={(event) => { if (event.target === event.currentTarget) setDetailId(null) }}>
        <aside className="h-full w-full max-w-xl overflow-y-auto bg-white p-5 shadow-2xl sm:p-7">
          <div className="mb-6 flex items-start justify-between"><div><p className="text-xs font-bold uppercase tracking-wider text-teal-700">Route profile</p><h2 className="mt-1 text-xl font-bold text-slate-900">{detail.data?.route.route_short_name || detailId}</h2><p className="mt-1 text-sm text-slate-500">{detail.data?.route.route_long_name}</p></div><button onClick={() => setDetailId(null)} className="rounded-lg p-2 text-slate-500 hover:bg-slate-100" aria-label="Close route details"><X className="h-5 w-5" /></button></div>
          {detail.loading && <LoadingState />}{detail.error && <ErrorState message={detail.error} onRetry={detail.reload} />}
          {detail.data && <div className="space-y-5">
            <div className="grid grid-cols-2 gap-3">{[
              ['Scheduled trips', formatNumber(detail.data.features.total_scheduled_trip_records)], ['Unique stops', formatNumber(detail.data.features.unique_stop_count)],
              ['Mean first-stop headway', formatDuration(detail.data.features.average_first_stop_headway_seconds)], ['Scheduled span', formatDuration(detail.data.features.scheduled_service_span_seconds)],
              ['Peak-window departures / template week', formatNumber(detail.data.features.peak_scheduled_departures_per_template_week)], ['Off-peak departures / template week', formatNumber(detail.data.features.off_peak_scheduled_departures_per_template_week)],
              ['Shared-stop ratio', detail.data.features.shared_stop_ratio == null ? '—' : `${(detail.data.features.shared_stop_ratio * 100).toFixed(1)}%`], ['First / last service', `${detail.data.features.first_scheduled_departure_time ?? '—'} / ${detail.data.features.last_scheduled_departure_time ?? '—'}`],
            ].map(([label, value]) => <div key={label} className="rounded-xl bg-slate-50 p-3"><p className="text-[11px] font-medium text-slate-500">{label}</p><p className="mt-1 font-semibold text-slate-900">{value}</p></div>)}</div>
            <div className="rounded-xl border border-slate-200 p-4"><p className="mb-3 text-sm font-semibold text-slate-800">Saved cluster assignments</p><div className="flex flex-wrap gap-2"><span className="cluster-pill bg-teal-50 text-teal-800">K-Means · {detail.data.cluster.kmeans_cluster_id ?? 'not assigned'}</span><span className="cluster-pill bg-blue-50 text-blue-800">DBSCAN · {detail.data.cluster.dbscan_cluster_id === -1 ? 'noise' : detail.data.cluster.dbscan_cluster_id ?? 'not assigned'}</span></div><p className="mt-3 text-xs leading-5 text-slate-500">Assignments group routes by GTFS schedule and stop-network features; they do not assess service quality or demand.</p></div>
            <DataNotice tone="amber">{detail.data.features.headway_missing ? 'A scheduled first-stop headway could not be estimated for this route.' : 'Headways are timetable estimates, not actual service regularity or waiting time.'} Peak windows are the analysis-defined 07:00–10:00 and 16:00–19:00 periods.</DataNotice>
          </div>}
        </aside>
      </div>}
    </>
  )
}

