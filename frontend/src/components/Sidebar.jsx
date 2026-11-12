import React from 'react';
import { 
  LayoutDashboard, 
  Radio, 
  Navigation, 
  TrendingUp, 
  Sliders, 
  BarChart3, 
  Layers,
  History,
  Info 
} from 'lucide-react';

const navItems = [
  { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { id: 'live', label: 'Live Monitoring', icon: Radio },
  { id: 'planner', label: 'Route Planner', icon: Navigation },
  { id: 'forecasting', label: 'Demand Forecasting', icon: TrendingUp },
  { id: 'replay', label: 'Historical Replay', icon: History },
  { id: 'clustering', label: 'Route Clusters', icon: Layers },
  { id: 'recommendations', label: 'Smart Scenarios', icon: Sliders },
  { id: 'analytics', label: 'Network Analytics', icon: BarChart3 },
  { id: 'about', label: 'About & Provenance', icon: Info },
];

export default function Sidebar({ currentTab, setTab }) {
  return (
    <aside className="w-64 border-r border-slate-800 bg-slate-900/50 flex flex-col justify-between p-4 flex-shrink-0">
      <div className="space-y-1">
        <div className="px-3 py-2 text-[11px] font-bold uppercase tracking-wider text-slate-400">
          Transit Operations
        </div>
        {navItems.map((item) => {
          const Icon = item.icon;
          const active = currentTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => setTab(item.id)}
              className={`w-full flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-sm font-medium transition-all ${
                active
                  ? 'bg-sky-500/15 text-sky-400 border border-sky-500/30 shadow-sm shadow-sky-500/10'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
              }`}
            >
              <Icon className={`w-4 h-4 ${active ? 'text-sky-400' : 'text-slate-500'}`} />
              <span>{item.label}</span>
            </button>
          );
        })}
      </div>

      {/* Footer Info Box */}
      <div className="p-3.5 rounded-xl bg-slate-800/60 border border-slate-700/60 text-xs text-slate-400 space-y-2">
        <div className="flex items-center justify-between font-semibold text-slate-300">
          <span>CTA Transit System</span>
          <span className="text-[10px] font-mono text-teal-400">v1.0.0</span>
        </div>
        <p className="text-[11px] leading-relaxed text-slate-400">
          Trained on official Chicago CTA daily ridership (2001–2026) and static GTFS schedule specifications.
        </p>
      </div>
    </aside>
  );
}

