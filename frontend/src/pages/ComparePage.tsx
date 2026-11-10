import { useCallback, useEffect, useMemo, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { ArrowLeftRight, Search, X } from 'lucide-react'
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { DataNotice, EmptyState, ErrorState, LoadingState, PageTitle, Panel, formatDuration, formatNumber } from '../components/ui'
import { useResource } from '../hooks/useResource'
import { api, explainApiError } from '../services/api'
import type { RouteFeature, RouteItem } from '../types/api'

interface ComparisonData {
  routes: RouteItem[]
  features: RouteFeature[]
}

export function ComparePage() {
  const location = useLocation()
  const initialIds = (location.state as { routeIds?: string[] } | null)?.routeIds ?? []
  const [selectedIds, setSelectedIds] = useState<string[]>(initialIds.slice(0, 20))
  const [searchInput, setSearchInput] = useState('')
  const [query, setQuery] = useState('')
  const [searchOffset, setSearchOffset] = useState(0)
  const [comparison, setComparison] = useState<ComparisonData | null>(null)
  const [comparing, setComparing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const timer = window.setTimeout(() => { setQuery(searchInput); setSearchOffset(0) }, 300)
    return () => window.clearTimeout(timer)
  }, [searchInput])
  useEffect(() => {
    const routeIds = (location.state as { routeIds?: string[] } | null)?.routeIds
    if (routeIds?.length) setSelectedIds(routeIds.slice(0, 20))
  }, [location.state])
  const loadRoutes = useCallback(() => api.listRoutes({ q: query || undefined, limit: 20, offset: searchOffset }), [query, searchOffset])
  const { data: searchResults, loading, error: searchError, reload } = useResource(loadRoutes, [loadRoutes])

  const runComparison = async () => {
    if (selectedIds.length < 2) return
    setComparing(true)
    setError(null)
    try {
      const response = await api.routeComparison(selectedIds)
      const features = await Promise.all(response.routes.map((route) => api.routeFeatures(route.route_id)))
      setComparison({ routes: response.routes, features })
    } catch (reason) {
      setError(explainApiError(reason))
    } finally {
      setComparing(false)
    }
  }

  const toggleRoute = (routeId: string) => {
    setSelectedIds((current) => current.includes(routeId) ? current.filter((id) => id !== routeId) : current.length < 20 ? [...current, routeId] : current)
    setComparison(null)
  }

  const labels = useMemo(() => comparison?.routes.map((route) => route.route_short_name || route.route_id) ?? [], [comparison])
  const tripChart = comparison?.routes.map((route) => ({ name: route.route_short_name || route.route_id, scheduledTrips: route.trip_count ?? 0, stops: route.stop_count ?? 0 })) ?? []
  const serviceChart = comparison?.features.map((feature) => ({
    name: feature.route_short_name || feature.route_id,
    peak: feature.peak_scheduled_departures_per_template_week ?? 0,
    offPeak: feature.off_peak_scheduled_departures_per_template_week ?? 0,
  })) ?? []
  const comparisonRows: { label: string; value: (index: number) => string }[] = comparison ? [
    { label: 'Scheduled trip records', value: (index) => formatNumber(comparison.features[index]?.total_scheduled_trip_records) },
    { label: 'Unique stops', value: (index) => formatNumber(comparison.features[index]?.unique_stop_count) },
    { label: 'Average first-stop headway', value: (index) => formatDuration(comparison.features[index]?.average_first_stop_headway_seconds) },
    { label: 'Scheduled service span', value: (index) => formatDuration(comparison.features[index]?.scheduled_service_span_seconds) },
    { label: 'Shared-stop ratio', value: (index) => { const value = comparison.features[index]?.shared_stop_ratio; return value == null ? '—' : `${(value * 100).toFixed(1)}%` } },
    { label: 'K-Means cluster', value: (index) => String(comparison.routes[index]?.kmeans_cluster_id ?? '—') },
    { label: 'DBSCAN assignment', value: (index) => comparison.routes[index]?.dbscan_cluster_id === -1 ? 'Noise' : String(comparison.routes[index]?.dbscan_cluster_id ?? '—') },
    { label: 'First / last service', value: (index) => `${comparison.features[index]?.first_scheduled_departure_time ?? '—'} / ${comparison.features[index]?.last_scheduled_departure_time ?? '—'}` },
  ] : []

  return (
    <>
      <PageTitle eyebrow="Side-by-side analysis" title="Route comparison" description="Compare scheduled service and stop-network features for two to twenty routes." />
      <div className="space-y-5">
        <DataNotice>Every comparison is based on supplied schedule and stop features. Scheduled trip counts and departure patterns are not actual operating performance or passenger demand.</DataNotice>
        <Panel title="Select routes" subtitle="Search route IDs or names, then choose two or more routes.">
          <label className="relative block max-w-xl"><Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" /><input value={searchInput} onChange={(event) => setSearchInput(event.target.value)} placeholder="Search routes to add" className="field pl-9" /></label>
          <div className="mt-3 flex flex-wrap gap-2">{selectedIds.map((id) => <button key={id} onClick={() => toggleRoute(id)} className="inline-flex items-center gap-1.5 rounded-lg bg-teal-50 px-2.5 py-1.5 text-xs font-semibold text-teal-800">{id}<X className="h-3 w-3" /></button>)}{selectedIds.length === 0 && <span className="text-xs text-slate-400">No routes selected yet.</span>}</div>
          <div className="mt-4 max-h-56 overflow-y-auto rounded-xl border border-slate-100">
            {loading && <LoadingState label="Searching routes…" />}{searchError && <ErrorState message={searchError} onRetry={reload} />}
            {!loading && !searchError && searchResults && (searchResults.items.length ? searchResults.items.map((route) => <button key={route.route_id} onClick={() => toggleRoute(route.route_id)} className={`flex w-full items-center justify-between border-b border-slate-50 px-4 py-3 text-left last:border-0 hover:bg-slate-50 ${selectedIds.includes(route.route_id) ? 'bg-teal-50/70' : ''}`}><span><strong className="text-sm text-slate-900">{route.route_short_name || route.route_id}</strong><span className="ml-2 text-xs text-slate-500">{route.route_long_name}</span></span><span className="text-xs text-slate-400">{formatNumber(route.trip_count)} scheduled trips</span></button>) : <EmptyState title={query ? 'No matching routes' : 'Search for routes'} detail="Results come from the RouteRanker route API." />)}
            {!loading && !searchError && searchResults && <div className="flex items-center justify-between border-t border-slate-100 px-3 py-2"><span className="text-[10px] text-slate-400">{formatNumber(searchResults.total)} matching routes</span><div className="flex gap-1"><button disabled={searchOffset === 0} onClick={() => setSearchOffset((value) => Math.max(0, value - 20))} className="page-button !px-2 !py-1">Previous</button><button disabled={searchOffset + 20 >= searchResults.total} onClick={() => setSearchOffset((value) => value + 20)} className="page-button !px-2 !py-1">Next</button></div></div>}
          </div>
          <div className="mt-4 flex flex-wrap items-center justify-between gap-3"><p className="text-xs text-slate-500">{selectedIds.length}/20 selected{selectedIds.length === 20 ? ' · maximum reached' : ''}</p><button disabled={selectedIds.length < 2 || comparing} onClick={runComparison} className="inline-flex items-center gap-2 rounded-xl bg-ink px-4 py-2.5 text-sm font-semibold text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-40"><ArrowLeftRight className="h-4 w-4" />{comparing ? 'Comparing…' : 'Compare routes'}</button></div>
        </Panel>

        {comparing && <Panel><LoadingState label="Fetching route summaries and original features…" /></Panel>}
        {error && <ErrorState message={error} />}
        {comparison && <>
          <div className="grid gap-5 xl:grid-cols-2">
            <Panel title="Scheduled trip records & route stops" subtitle="Two charts retain their original units for easier interpretation.">
              <div className="grid gap-5 sm:grid-cols-2"><div><p className="mb-2 text-xs font-medium text-slate-500">Trip records</p><div className="h-[230px]"><ResponsiveContainer width="100%" height="100%"><BarChart data={tripChart} margin={{ left: -18, right: 5, bottom: 5 }}><CartesianGrid stroke="#e9eef3" vertical={false} /><XAxis dataKey="name" tickLine={false} axisLine={false} tick={{ fontSize: 10 }} /><YAxis tickLine={false} axisLine={false} tick={{ fontSize: 10 }} /><Tooltip formatter={(value) => [formatNumber(Number(value)), 'Scheduled trip records']} /><Bar dataKey="scheduledTrips" fill="#0f9b8e" radius={[5, 5, 0, 0]} /></BarChart></ResponsiveContainer></div></div><div><p className="mb-2 text-xs font-medium text-slate-500">Unique stops</p><div className="h-[230px]"><ResponsiveContainer width="100%" height="100%"><BarChart data={tripChart} margin={{ left: -18, right: 5, bottom: 5 }}><CartesianGrid stroke="#e9eef3" vertical={false} /><XAxis dataKey="name" tickLine={false} axisLine={false} tick={{ fontSize: 10 }} /><YAxis tickLine={false} axisLine={false} tick={{ fontSize: 10 }} /><Tooltip formatter={(value) => [formatNumber(Number(value)), 'Stops']} /><Bar dataKey="stops" fill="#5277d8" radius={[5, 5, 0, 0]} /></BarChart></ResponsiveContainer></div></div></div>
            </Panel>
            <Panel title="Template-week departures" subtitle="Peak and off-peak counts use the documented analysis windows.">
              <div className="h-[290px]"><ResponsiveContainer width="100%" height="100%"><BarChart data={serviceChart} margin={{ top: 8, left: -15, right: 8, bottom: 5 }}><CartesianGrid stroke="#e9eef3" vertical={false} /><XAxis dataKey="name" tickLine={false} axisLine={false} tick={{ fontSize: 10 }} /><YAxis tickLine={false} axisLine={false} tick={{ fontSize: 10 }} /><Tooltip formatter={(value, name) => [formatNumber(Number(value)), name === 'Peak' || name === 'peak' ? 'Peak-window scheduled departures' : 'Off-peak scheduled departures']} /><Legend /><Bar dataKey="peak" name="Peak" fill="#0f9b8e" radius={[4, 4, 0, 0]} /><Bar dataKey="offPeak" name="Off-peak" fill="#9cb7f6" radius={[4, 4, 0, 0]} /></BarChart></ResponsiveContainer></div>
              <p className="mt-2 text-[11px] text-slate-500">Peak windows: 07:00–10:00 and 16:00–19:00. These analysis windows are not official MTC classifications.</p>
            </Panel>
          </div>
          <Panel title="Comparison details" subtitle="Raw route features and saved cluster assignments.">
            <div className="overflow-x-auto"><table className="w-full min-w-[760px] text-left text-sm"><thead><tr className="border-b border-slate-100 text-xs font-semibold text-slate-500"><th className="pb-3">Characteristic</th>{comparison.routes.map((route) => <th key={route.route_id} className="pb-3">{route.route_short_name || route.route_id}<span className="mt-0.5 block text-[10px] font-normal text-slate-400">{route.route_long_name}</span></th>)}</tr></thead><tbody>{comparisonRows.map((row) => <tr key={row.label} className="border-b border-slate-50 last:border-0"><td className="py-3 font-medium text-slate-600">{row.label}</td>{comparison.routes.map((route, index) => <td key={route.route_id} className="py-3 text-slate-800">{row.value(index)}</td>)}</tr>)}</tbody></table></div>
          </Panel>
          <p className="text-xs text-slate-400">Compared routes: {labels.join(', ')}. {comparison.routes.length} records returned by the backend.</p>
        </>}
      </div>
    </>
  )
}
