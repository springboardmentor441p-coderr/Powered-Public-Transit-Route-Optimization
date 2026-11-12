import React from 'react';
import { Database, Radio, Cpu, History } from 'lucide-react';

export default function DataSourceBadge({ source = 'HISTORICAL', className = '' }) {
  const s = (source || '').toUpperCase();

  if (s.includes('LIVE')) {
    return (
      <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-mono font-medium bg-emerald-500/10 text-emerald-300 border border-emerald-500/30 ${className}`}>
        <Radio className="w-3.5 h-3.5 text-emerald-400 animate-pulse" />
        <span>CTA Live API Feed</span>
      </span>
    );
  }

  if (s.includes('GTFS') || s.includes('SIMULATION') || s.includes('SCHEDULE')) {
    return (
      <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-mono font-medium bg-sky-500/10 text-sky-300 border border-sky-500/30 ${className}`}>
        <Database className="w-3.5 h-3.5 text-sky-400" />
        <span>GTFS Schedule Emulation</span>
      </span>
    );
  }

  if (s.includes('FORECAST') || s.includes('ML')) {
    return (
      <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-mono font-medium bg-purple-500/10 text-purple-300 border border-purple-500/30 ${className}`}>
        <Cpu className="w-3.5 h-3.5 text-purple-400" />
        <span>Random Forest Forecast (CTA ML)</span>
      </span>
    );
  }

  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-mono font-medium bg-slate-700/50 text-slate-300 border border-slate-600/50 ${className}`}>
      <History className="w-3.5 h-3.5 text-slate-400" />
      <span>Official CTA Historical Data</span>
    </span>
  );
}

