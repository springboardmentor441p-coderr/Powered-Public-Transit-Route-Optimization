import React, { useState, useEffect } from 'react';
import { Bus, Train, AlertTriangle, ShieldCheck, Activity } from 'lucide-react';
import { getTransitStatus, getActiveAlerts } from '../api';

export default function Navbar() {
  const [status, setStatus] = useState(null);
  const [alertCount, setAlertCount] = useState(0);

  useEffect(() => {
    getTransitStatus()
      .then(setStatus)
      .catch((e) => console.error('Status fetch failed', e));

    getActiveAlerts()
      .then((data) => setAlertCount(data.total_alerts ?? data.count ?? data.alerts?.length ?? 0))
      .catch((e) => console.error('Alerts fetch failed', e));
  }, []);

  const isLive = status?.alerts_api_active || status?.live_apis?.cta_alerts === 'CONNECTED';

  return (
    <header className="h-16 border-b border-slate-800 bg-slate-900/90 backdrop-blur sticky top-0 z-40 px-6 flex items-center justify-between">
      {/* Brand */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-sky-500 to-teal-400 flex items-center justify-center shadow-lg shadow-sky-500/20 text-slate-950 font-black text-xl tracking-tighter">
          RR
        </div>
        <div>
          <div className="flex items-center gap-2">
            <h1 className="font-bold text-lg text-white tracking-tight">RouteRanker</h1>
            <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded bg-sky-500/20 text-sky-400 border border-sky-500/30">
              Chicago CTA
            </span>
          </div>
          <p className="text-xs text-slate-400 hidden sm:block">AI-Powered Monitoring, Crowd Forecasting & Route Optimization</p>
        </div>
      </div>

      {/* Real-time system indicators */}
      <div className="flex items-center gap-3">
        {/* Alerts Pill */}
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs font-medium">
          <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
          <span>{alertCount} Active CTA Alerts</span>
        </div>

        {/* Live CTA Feed status */}
        <div className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-800/80 border border-slate-700 text-xs">
          <span className="relative flex h-2 w-2">
            <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${isLive ? 'bg-emerald-400' : 'bg-sky-400'}`}></span>
            <span className={`relative inline-flex rounded-full h-2 w-2 ${isLive ? 'bg-emerald-500' : 'bg-sky-500'}`}></span>
          </span>
          <span className="text-slate-300 font-medium">
            {isLive ? 'CTA Feeds Active' : 'GTFS Emulation'}
          </span>
        </div>

        {/* System badge */}
        <div className="hidden lg:flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 text-slate-400 text-xs font-mono">
          <ShieldCheck className="w-3.5 h-3.5 text-teal-400" />
          <span>Chicago, IL (USA)</span>
        </div>
      </div>
    </header>
  );
}

