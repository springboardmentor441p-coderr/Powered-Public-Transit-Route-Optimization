import { useCallback, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { Activity, BarChart3, BusFront, ChevronRight, GitCompareArrows, Map, Menu, Network, Route, X } from 'lucide-react'
import { useResource } from '../hooks/useResource'
import { api } from '../services/api'

const navigation = [
  { to: '/', label: 'Overview', icon: BarChart3, end: true },
  { to: '/routes', label: 'Route explorer', icon: Route },
  { to: '/stops', label: 'Stop explorer', icon: BusFront },
  { to: '/map', label: 'Transit network map', icon: Map },
  { to: '/insights', label: 'ML insights', icon: Network },
  { to: '/compare', label: 'Route comparison', icon: GitCompareArrows },
]

export function AppShell() {
  const [mobileOpen, setMobileOpen] = useState(false)
  const location = useLocation()
  const current = navigation.find((item) => item.end ? location.pathname === item.to : location.pathname.startsWith(item.to))
  const loadHealth = useCallback(() => api.health(), [])
  const health = useResource(loadHealth)

  const sidebar = (
    <div className="flex h-full flex-col bg-ink text-white">
      <div className="flex h-[76px] items-center justify-between border-b border-white/10 px-6">
        <NavLink to="/" onClick={() => setMobileOpen(false)} className="flex items-center gap-3">
          <span className="grid h-10 w-10 place-items-center rounded-xl bg-teal-400 text-ink"><Activity className="h-5 w-5" /></span>
          <span><span className="block text-lg font-bold tracking-tight">RouteRanker</span><span className="block text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-400">Transit intelligence</span></span>
        </NavLink>
        <button className="rounded-lg p-2 text-slate-400 hover:bg-white/10 md:hidden" onClick={() => setMobileOpen(false)} aria-label="Close navigation"><X className="h-5 w-5" /></button>
      </div>
      <div className="px-4 pt-7">
        <p className="mb-3 px-3 text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">Workspace</p>
        <nav className="space-y-1">
          {navigation.map(({ to, label, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end} onClick={() => setMobileOpen(false)} className={({ isActive }) =>
              `group flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition ${isActive ? 'bg-white/10 text-white' : 'text-slate-400 hover:bg-white/5 hover:text-white'}`
            }>
              {({ isActive }) => <><Icon className={`h-[18px] w-[18px] ${isActive ? 'text-teal-300' : 'text-slate-500 group-hover:text-slate-300'}`} /><span className="flex-1">{label}</span>{isActive && <ChevronRight className="h-4 w-4 text-teal-300" />}</>}
            </NavLink>
          ))}
        </nav>
      </div>
      <div className="mt-auto p-4">
        <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4">
          <div className="mb-2 flex items-center gap-2"><span className="h-2 w-2 rounded-full bg-teal-400" /><span className="text-xs font-semibold text-slate-200">Chennai MTC · GTFS</span></div>
          <p className="text-[11px] leading-5 text-slate-500">Scheduled service analysis. No passenger or live operations data.</p>
        </div>
        <p className="mt-4 px-1 text-[10px] text-slate-600">RouteRanker · Internship project</p>
      </div>
    </div>
  )

  return (
    <div className="min-h-screen bg-canvas">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-[252px] md:block">{sidebar}</aside>
      {mobileOpen && <div className="fixed inset-0 z-40 flex md:hidden"><button className="absolute inset-0 bg-slate-950/40" onClick={() => setMobileOpen(false)} aria-label="Close navigation overlay" /><aside className="relative z-10 w-[280px] max-w-[85vw] shadow-2xl">{sidebar}</aside></div>}
      <div className="md:pl-[252px]">
        <header className="sticky top-0 z-20 flex h-[68px] items-center justify-between border-b border-slate-200/80 bg-white/90 px-4 backdrop-blur-md sm:px-7">
          <div className="flex items-center gap-3">
            <button onClick={() => setMobileOpen(true)} className="rounded-lg border border-slate-200 p-2 text-slate-600 md:hidden" aria-label="Open navigation"><Menu className="h-5 w-5" /></button>
            <div className="hidden items-center gap-2 text-xs text-slate-400 sm:flex"><span>RouteRanker</span><ChevronRight className="h-3.5 w-3.5" /><span className="font-semibold text-slate-700">{current?.label ?? 'Analytics'}</span></div>
            <div className="font-semibold text-slate-800 sm:hidden">{current?.label ?? 'Analytics'}</div>
          </div>
          <div className="flex items-center gap-2.5" title={health.error ?? 'Backend health endpoint responded'}><span className={`h-2 w-2 rounded-full ${health.error ? 'bg-rose-500' : health.loading ? 'bg-amber-400' : 'bg-teal-500'}`} /><span className="text-xs font-medium text-slate-500">{health.error ? 'API unavailable' : health.loading ? 'Connecting…' : 'API connected'}</span></div>
        </header>
        <main className="mx-auto max-w-[1600px] px-4 py-6 sm:px-7 sm:py-8 lg:px-9"><Outlet /></main>
      </div>
    </div>
  )
}
