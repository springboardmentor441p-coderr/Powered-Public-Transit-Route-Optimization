import { useState, type ReactNode } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { TABS } from '../screens'
import { Drawer } from './Drawer'

/** The page frame: a slate top bar with the tabs, the mode in plain words, the data status and a Sources
 *  drawer (data details). No sidebar: the page gets the full width for tables and maps.
 *  z-index: Leaflet panes reach 700 and its controls 1000, so the bar sits at 1100 (drawers at 1200).
 *  On narrow windows the bar wraps onto a second row instead of pushing text off the right edge. */
export function TopBar({ modeLabel, dataThrough, sources }: {
  modeLabel: string; dataThrough: ReactNode; sources: ReactNode
}) {
  const [open, setOpen] = useState(false)
  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-[1100] bg-brand text-brand-text [--focus-ring:#FFFFFF]">
        <div className="mx-auto flex min-h-12 max-w-[1440px] flex-wrap items-stretch gap-x-5 px-6">
          <NavLink to="/" className="flex items-center text-md font-bold tracking-tight text-white no-underline">
            RouteRanker
          </NavLink>
          <nav aria-label="Main" className="flex flex-wrap items-stretch">
            {TABS.map(t => (
              <NavLink key={t.to} to={t.to} end={'end' in t ? t.end : undefined} title={t.question}
                       className={({ isActive }) =>
                         `flex min-h-12 items-center whitespace-nowrap border-b-[3px] px-2.5 text-sm no-underline ${
                           isActive ? 'border-white font-semibold text-white' : 'border-transparent hover:text-white'}`}>
                {t.label}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto flex min-w-0 flex-wrap items-center justify-end gap-x-4 gap-y-1 py-2 text-sm">
            <span className="whitespace-nowrap" title="Replay arrives with Stage 7">
              <span className="text-white">{modeLabel}</span>
              <span className="hidden text-xs xl:inline"> · Replay: Stage 7</span>
            </span>
            <span className="whitespace-nowrap">Data to <span className="num text-white">{dataThrough}</span></span>
            <button type="button" onClick={() => setOpen(true)} aria-expanded={open}
                    className="h-7 whitespace-nowrap border border-brand-text px-2.5 text-sm text-white hover:bg-white/10">Sources</button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-[1440px] px-6 pb-12 pt-6"><Outlet /></main>
      {open && <Drawer eyebrow="Data details" title="Where every number comes from" onClose={() => setOpen(false)}>{sources}</Drawer>}
    </div>
  )
}
