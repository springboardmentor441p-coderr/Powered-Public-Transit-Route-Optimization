import { useState } from 'react';
import { Outlet, NavLink } from 'react-router-dom';
import {
  LayoutDashboard, MapPin, Route, Calendar, GitBranch,
  Brain, Sliders, ShieldCheck, Menu, X, Bus, Moon, Sun
} from 'lucide-react';
import { ThemeContext } from './ThemeContext';

const navItems = [
  { to: '/', icon: LayoutDashboard, label: 'Overview' },
  { to: '/routes', icon: Route, label: 'Route Explorer' },
  { to: '/schedule', icon: Calendar, label: 'Schedule Analytics' },
  { to: '/coverage', icon: MapPin, label: 'Stop Coverage' },
  { to: '/overlap', icon: GitBranch, label: 'Route Overlap' },
  { to: '/clustering', icon: Brain, label: 'ML Clustering' },
  { to: '/optimization', icon: Sliders, label: 'Schedule Optimization' },
  { to: '/data-quality', icon: ShieldCheck, label: 'Data Quality' },
];

export default function MainLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [dark, setDark] = useState(false);

  const toggle = () => {
    setDark(d => !d);
    document.documentElement.classList.toggle('dark');
  };

  return (
    <ThemeContext.Provider value={{ dark, toggle }}>
      <div className={`flex h-screen ${dark ? 'dark' : ''}`}>
        {/* Sidebar */}
        <aside className={`
          fixed inset-y-0 left-0 z-50 w-[260px] bg-white dark:bg-slate-900 border-r border-slate-200 dark:border-slate-700
          transform transition-transform duration-200 lg:translate-x-0 lg:static lg:inset-auto
          ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
          flex flex-col shadow-lg lg:shadow-none
        `}>
          {/* Logo */}
          <div className="flex items-center gap-3 px-5 py-5 border-b border-slate-200 dark:border-slate-700">
            <div className="w-10 h-10 rounded-xl bg-blue-600 flex items-center justify-center">
              <Bus className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="text-lg font-bold text-slate-900 dark:text-white">RouteRanker</h1>
              <p className="text-xs text-slate-500 dark:text-slate-400">Chennai MTC Analytics</p>
            </div>
            <button type="button" aria-label="Close navigation" title="Close navigation" onClick={() => setSidebarOpen(false)} className="lg:hidden ml-auto text-slate-400 hover:text-slate-600">
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Nav */}
          <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
            {navItems.map(item => (
              <NavLink
                key={item.to}
                to={item.to}
                onClick={() => setSidebarOpen(false)}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                    isActive
                      ? 'bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400'
                      : 'text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800'
                  }`
                }
              >
                <item.icon className="w-5 h-5 flex-shrink-0" />
                {item.label}
              </NavLink>
            ))}
          </nav>

          {/* Theme toggle */}
          <div className="px-4 py-3 border-t border-slate-200 dark:border-slate-700">
            <button onClick={toggle} className="flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-300 w-full px-3 py-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors">
              {dark ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
              {dark ? 'Light Mode' : 'Dark Mode'}
            </button>
          </div>
        </aside>

        {/* Overlay */}
        {sidebarOpen && (
          <div className="fixed inset-0 bg-black/50 z-40 lg:hidden" onClick={() => setSidebarOpen(false)} />
        )}

        {/* Main */}
        <main className="flex-1 flex flex-col min-h-0 bg-slate-50 dark:bg-slate-950">
          {/* Top bar */}
          <header className="h-14 flex items-center px-4 border-b border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 lg:hidden">
            <button type="button" aria-label="Open navigation" title="Open navigation" onClick={() => setSidebarOpen(true)} className="text-slate-600 dark:text-slate-400">
              <Menu className="w-6 h-6" />
            </button>
            <div className="flex items-center gap-2 ml-3">
              <Bus className="w-5 h-5 text-blue-600" />
              <span className="font-semibold text-slate-900 dark:text-white">RouteRanker</span>
            </div>
          </header>

          {/* Content */}
          <div className="flex-1 overflow-y-auto p-4 lg:p-8">
            <Outlet />
            <footer className="mt-8 border-t border-slate-200 pt-4 text-xs text-slate-500 dark:border-slate-800 dark:text-slate-400">
              RouteRanker · Chennai MTC GTFS schedule analytics · Estimates are schedule-derived, not live operations data.
            </footer>
          </div>
        </main>
      </div>
    </ThemeContext.Provider>
  );
}

