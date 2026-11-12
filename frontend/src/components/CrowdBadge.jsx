import React from 'react';

export default function CrowdBadge({ tier }) {
  const normalized = (tier || '').toLowerCase();
  
  if (normalized.includes('low')) {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
        Low Demand
      </span>
    );
  }
  
  if (normalized.includes('moderate')) {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-sky-500/15 text-sky-400 border border-sky-500/30">
        <span className="w-1.5 h-1.5 rounded-full bg-sky-400"></span>
        Moderate Demand
      </span>
    );
  }
  
  if (normalized.includes('high')) {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-500/15 text-amber-400 border border-amber-500/30">
        <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse"></span>
        High Demand
      </span>
    );
  }
  
  // Potentially Overcrowded or Severe
  return (
    <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-500/15 text-rose-400 border border-rose-500/30">
      <span className="w-1.5 h-1.5 rounded-full bg-rose-400 animate-ping"></span>
      Potentially Overcrowded
    </span>
  );
}

