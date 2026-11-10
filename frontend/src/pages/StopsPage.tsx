import { useCallback, useEffect, useState } from 'react'
import { ChevronLeft, ChevronRight, MapPin, Search, X } from 'lucide-react'
import { DataNotice, EmptyState, ErrorState, LoadingState, PageTitle, Panel, formatNumber } from '../components/ui'
import { useResource } from '../hooks/useResource'
import { api } from '../services/api'
import type { StopItem } from '../types/api'

const PAGE_SIZE = 50

export function StopsPage() {
  const [searchInput, setSearchInput] = useState('')
  const [query, setQuery] = useState('')
  const [offset, setOffset] = useState(0)
  const [selected, setSelected] = useState<StopItem | null>(null)
  useEffect(() => {
    const timer = window.setTimeout(() => { setQuery(searchInput); setOffset(0) }, 300)
    return () => window.clearTimeout(timer)
  }, [searchInput])

  const loadStops = useCallback(() => api.listStops({ limit: PAGE_SIZE, offset, ...(query ? { q: query } : {}) }), [offset, query])
  const { data, loading, error, reload } = useResource(loadStops, [loadStops])
  const loadRoutes = useCallback(() => selected ? api.routesAtStop(selected.stop_id) : Promise.resolve([]), [selected])
  const routes = useResource(loadRoutes, [loadRoutes])

  return (
    <>
      <PageTitle eyebrow="Places & service" title="Stop explorer" description="Explore stop locations and the scheduled routes and trip records associated with each stop." />
      <div className="space-y-5">
        <DataNotice>Stop trip counts are scheduled GTFS stop-time references. They are not boardings, passenger counts, or service delivered in real time.</DataNotice>
        <Panel className="!p-4">
          <label className="relative block max-w-xl"><Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" /><input value={searchInput} onChange={(event) => setSearchInput(event.target.value)} placeholder="Search by stop ID or stop name" className="field pl-9" /></label>
        </Panel>
        <Panel title="Stops" subtitle={data ? `${formatNumber(data.total)} stops in the current result` : 'Search available GTFS stops.'}>
          {loading && <LoadingState label="Loading stops…" />}{error && <ErrorState message={error} onRetry={reload} />}
          {!loading && !error && data && (data.items.length ? <>
            <div className="space-y-2">{data.items.map((stop) => <button key={stop.stop_id} onClick={() => setSelected(stop)} className={`flex w-full items-center justify-between gap-4 rounded-xl border p-4 text-left transition ${selected?.stop_id === stop.stop_id ? 'border-teal-300 bg-teal-50/60' : 'border-slate-100 hover:border-slate-200 hover:bg-slate-50'}`}>
              <span className="flex min-w-0 items-center gap-3"><span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-blue-50 text-blue-700"><MapPin className="h-4 w-4" /></span><span className="min-w-0"><span className="block truncate text-sm font-semibold text-slate-900">{stop.stop_name || 'Unnamed stop'}</span><span className="mt-0.5 block text-xs text-slate-500">Stop ID {stop.stop_id} · {stop.stop_lat_value?.toFixed(4) ?? '—'}, {stop.stop_lon_value?.toFixed(4) ?? '—'}</span></span></span>
              <span className="flex shrink-0 gap-4 text-right"><span><strong className="block text-sm text-slate-800">{formatNumber(stop.route_count)}</strong><small className="text-[10px] text-slate-500">routes</small></span><span className="hidden sm:block"><strong className="block text-sm text-slate-800">{formatNumber(stop.trip_count)}</strong><small className="text-[10px] text-slate-500">scheduled trips</small></span></span>
            </button>)}</div>
            <div className="mt-5 flex items-center justify-between border-t border-slate-100 pt-4"><p className="text-xs text-slate-500">Showing {formatNumber(offset + 1)}–{formatNumber(Math.min(offset + data.items.length, data.total))} of {formatNumber(data.total)}</p><div className="flex gap-2"><button disabled={offset === 0} onClick={() => setOffset((value) => Math.max(0, value - PAGE_SIZE))} className="page-button"><ChevronLeft className="h-4 w-4" />Previous</button><button disabled={offset + PAGE_SIZE >= data.total} onClick={() => setOffset((value) => value + PAGE_SIZE)} className="page-button">Next<ChevronRight className="h-4 w-4" /></button></div></div>
          </> : <EmptyState />)}
        </Panel>
      </div>
      {selected && <div className="fixed inset-0 z-40 flex justify-end bg-slate-950/35" onMouseDown={(event) => { if (event.target === event.currentTarget) setSelected(null) }}>
        <aside className="h-full w-full max-w-lg overflow-y-auto bg-white p-5 shadow-2xl sm:p-7">
          <div className="flex items-start justify-between"><div><p className="text-xs font-bold uppercase tracking-wider text-blue-700">Stop profile</p><h2 className="mt-1 text-xl font-bold text-slate-900">{selected.stop_name || 'Unnamed stop'}</h2><p className="mt-1 text-sm text-slate-500">GTFS stop ID {selected.stop_id}</p></div><button onClick={() => setSelected(null)} className="rounded-lg p-2 text-slate-500 hover:bg-slate-100" aria-label="Close stop details"><X className="h-5 w-5" /></button></div>
          <div className="mt-6 grid grid-cols-2 gap-3"><div className="rounded-xl bg-slate-50 p-4"><p className="text-xs text-slate-500">Routes serving stop</p><strong className="mt-1 block text-2xl text-slate-900">{formatNumber(selected.route_count)}</strong></div><div className="rounded-xl bg-slate-50 p-4"><p className="text-xs text-slate-500">Scheduled stop-time references</p><strong className="mt-1 block text-2xl text-slate-900">{formatNumber(selected.trip_count)}</strong></div></div>
          <p className="mt-4 rounded-xl bg-slate-50 p-4 text-xs text-slate-600">Coordinates: {selected.stop_lat_value ?? '—'}, {selected.stop_lon_value ?? '—'}</p>
          <div className="mt-7"><h3 className="font-semibold text-slate-900">Routes serving this stop</h3><p className="mt-1 text-xs text-slate-500">Route membership from scheduled route-stop coverage.</p>
            {routes.loading && <LoadingState label="Loading routes…" />}{routes.error && <ErrorState message={routes.error} onRetry={routes.reload} />}
            {routes.data && (routes.data.length ? <div className="mt-4 space-y-2">{routes.data.map((route) => <div key={route.route_id} className="rounded-xl border border-slate-100 p-3"><p className="text-sm font-semibold text-slate-900">{route.route_short_name || route.route_id}</p><p className="mt-0.5 text-xs text-slate-500">{route.route_long_name}</p><p className="mt-1 text-[10px] text-slate-400">Route ID {route.route_id}</p></div>)}</div> : <EmptyState title="No route links available" detail="No route-stop coverage records were returned." />)}
          </div>
        </aside>
      </div>}
    </>
  )
}
