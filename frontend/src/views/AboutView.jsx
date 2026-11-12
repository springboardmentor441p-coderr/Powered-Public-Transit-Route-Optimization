import React, { useState, useEffect } from 'react';
import {
  ShieldCheck,
  Database,
  Cpu,
  GitFork,
  Layers,
  Code2,
  ExternalLink,
  FileCheck2,
  Fingerprint
} from 'lucide-react';
import DataSourceBadge from '../components/DataSourceBadge';
import { getSourceManifest } from '../api';

export default function AboutView() {
  const [manifest, setManifest] = useState(null);

  useEffect(() => {
    getSourceManifest()
      .then(setManifest)
      .catch((e) => console.warn('Could not load manifest on About view:', e));
  }, []);

  return (
    <div className="space-y-6 max-w-5xl">
      {/* Header */}
      <div className="p-6 rounded-2xl bg-gradient-to-r from-slate-900 via-sky-950/40 to-slate-900 border border-slate-800 space-y-2">
        <div className="flex items-center gap-2">
          <ShieldCheck className="w-5 h-5 text-teal-400" />
          <span className="text-xs uppercase tracking-wider font-semibold text-teal-400">
            System Architecture & Data Provenance
          </span>
        </div>
        <h2 className="text-2xl font-extrabold text-white tracking-tight">About RouteRanker</h2>
        <p className="text-sm text-slate-300 leading-relaxed">
          RouteRanker is an AI-powered public transit monitoring, passenger crowd forecasting, and multi-modal route optimization decision-support platform designed exclusively for the <strong>Chicago Transit Authority (CTA)</strong> in Chicago, Illinois, USA.
        </p>
      </div>

      {/* Strict City Rule Notice */}
      <div className="p-5 rounded-xl bg-slate-900/80 border border-slate-800 space-y-2">
        <h3 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
          Geographic Scope & Data Integrity Rule
        </h3>
        <p className="text-xs text-slate-300 leading-relaxed">
          In strict accordance with project requirements, RouteRanker uses <strong>Chicago Transit Authority (CTA) data exclusively</strong>. No data from Pune, Newark, New York, or any other metropolitan transit system is utilized. All historical ridership records, station catalogs, timetable blocks, and network graphs represent real-world Chicago public transportation infrastructure.
        </p>
      </div>

      {/* Verified Data Source Manifest (Live Backend) */}
      {manifest && (
        <div className="p-5 rounded-xl bg-slate-900/80 border border-slate-800 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
              <Fingerprint className="w-4 h-4 text-sky-400" />
              Verified Immutable Source Manifest (Technical Spec v3.8)
            </h3>
            <span className="text-[11px] font-mono text-emerald-400 bg-emerald-950/40 px-2.5 py-0.5 rounded border border-emerald-500/20">
              Version {manifest.manifest_version}
            </span>
          </div>

          <div className="space-y-2">
            {manifest.datasets?.map((ds, idx) => (
              <div key={idx} className="p-3 rounded-lg bg-slate-800/40 border border-slate-700/50 flex flex-col md:flex-row md:items-center justify-between gap-2 text-xs">
                <div>
                  <div className="font-bold text-white flex items-center gap-2">
                    <span>{ds.snapshot_id}</span>
                    <span className="text-[10px] text-slate-400">({ds.file_name})</span>
                  </div>
                  <div className="text-[11px] text-slate-400 mt-0.5">
                    Range: {ds.coverage_start} to {ds.coverage_end} • Timezone: {ds.agency_timezone}
                  </div>
                </div>
                <div className="font-mono text-[10px] text-sky-300 bg-slate-950 px-2 py-1 rounded truncate max-w-xs" title={ds.sha256}>
                  SHA: {ds.sha256?.slice(0, 20)}...
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Grid: 4 Core Pillars */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Pillar 1: Data Acquisition */}
        <div className="p-5 rounded-xl bg-slate-900/80 border border-slate-800 space-y-3">
          <div className="flex items-center gap-2 text-sky-400 font-bold text-sm">
            <Database className="w-4 h-4" />
            <span>1. Official Chicago Datasets</span>
          </div>
          <ul className="text-xs text-slate-400 space-y-2">
            <li>• <strong>System Daily Totals:</strong> 9,374 consecutive days (Jan 1, 2001 – Aug 31, 2026) from the Chicago Data Portal. Zero missing values.</li>
            <li>• <strong>Bus Route Ridership:</strong> 150,000 historical daily records matched against 124 active CTA corridors.</li>
            <li>• <strong>Rail Station Turnstile Entries:</strong> 150,000 daily entries across all 144 CTA 'L' rapid transit stations.</li>
            <li>• <strong>Static GTFS Archive:</strong> 65.55 MB schedule specification (`google_transit.zip`) containing trips, stops, calendar, and routes.</li>
          </ul>
        </div>

        {/* Pillar 2: Machine Learning */}
        <div className="p-5 rounded-xl bg-slate-900/80 border border-slate-800 space-y-3">
          <div className="flex items-center gap-2 text-purple-400 font-bold text-sm">
            <Cpu className="w-4 h-4" />
            <span>2. Machine Learning Demand Forecasting</span>
          </div>
          <ul className="text-xs text-slate-400 space-y-2">
            <li>• <strong>Rigorous Chronological Splits:</strong> Train (2001–2024), Validation (2025), and completely unseen Test Set (Jan 1 – Aug 31, 2026). Zero future lookahead leakage.</li>
            <li>• <strong>Feature Engineering:</strong> Lagged demand (1, 7, 14, 28 days), 7-day and 28-day rolling moving averages, day of week, day type, and seasonal cyclical harmonics.</li>
            <li>• <strong>Best Model:</strong> <strong>Random Forest Regressor</strong> achieving <strong>7.92% MAPE</strong>, MAE of ±70,053 rides/day, and R² of 0.79 on out-of-sample test dates.</li>
          </ul>
        </div>

        {/* Pillar 3: Network Graph & Routing */}
        <div className="p-5 rounded-xl bg-slate-900/80 border border-slate-800 space-y-3">
          <div className="flex items-center gap-2 text-teal-400 font-bold text-sm">
            <GitFork className="w-4 h-4" />
            <span>3. Multi-Modal Network Graph</span>
          </div>
          <ul className="text-xs text-slate-400 space-y-2">
            <li>• <strong>Directed Transit Graph:</strong> 182 nodes (144 rail stations + 38 key bus terminals) and 440 directed edges.</li>
            <li>• <strong>Track Connectivity:</strong> 322 track segments covering all 8 rail lines (Red, Blue, Brown, Green, Orange, Purple, Pink, Yellow).</li>
            <li>• <strong>Multi-Modal Transfers:</strong> 110 pedestrian walking transfer links within a 400-meter (0.25 mile) catchment radius.</li>
            <li>• <strong>Algorithms:</strong> Dijkstra shortest path with transfer penalties and Pareto alternative path generation.</li>
          </ul>
        </div>

        {/* Pillar 4: Real-time Integration & Fallback */}
        <div className="p-5 rounded-xl bg-slate-900/80 border border-slate-800 space-y-3">
          <div className="flex items-center gap-2 text-amber-400 font-bold text-sm">
            <Layers className="w-4 h-4" />
            <span>4. Real-Time CTA API & Simulation Fallback</span>
          </div>
          <ul className="text-xs text-slate-400 space-y-2">
            <li>• <strong>CTA Live Alerts:</strong> Fully integrated with the official CTA XML/JSON alerts API (`transitchicago.com/api/1.0/alerts.aspx`), requiring no key.</li>
            <li>• <strong>Bus & Train Trackers:</strong> Dedicated clients for Bus Tracker v2 and Train Tracker v1.0 with 30-second TTL in-memory caching.</li>
            <li>• <strong>Transparent Fallback:</strong> When developer API keys are unconfigured, RouteRanker automatically and transparently falls back to GTFS schedule trajectory simulation, prominently labeled with badges.</li>
          </ul>
        </div>
      </div>

      {/* Tech Stack Specs */}
      <div className="p-5 rounded-xl bg-slate-900/80 border border-slate-800 space-y-3">
        <div className="flex items-center gap-2 text-white font-bold text-sm">
          <Code2 className="w-4 h-4 text-sky-400" />
          <span>Technology Stack</span>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
          <div className="p-3 rounded-lg bg-slate-800/50 border border-slate-700/50">
            <div className="text-slate-400">Backend API</div>
            <div className="font-semibold text-white mt-0.5">FastAPI + Uvicorn</div>
          </div>
          <div className="p-3 rounded-lg bg-slate-800/50 border border-slate-700/50">
            <div className="text-slate-400">Machine Learning</div>
            <div className="font-semibold text-white mt-0.5">Scikit-Learn + Joblib</div>
          </div>
          <div className="p-3 rounded-lg bg-slate-800/50 border border-slate-700/50">
            <div className="text-slate-400">Graph Theory</div>
            <div className="font-semibold text-white mt-0.5">NetworkX (Directed Graph)</div>
          </div>
          <div className="p-3 rounded-lg bg-slate-800/50 border border-slate-700/50">
            <div className="text-slate-400">Frontend Web UI</div>
            <div className="font-semibold text-white mt-0.5">React 19 + Vite + Tailwind</div>
          </div>
        </div>
      </div>
    </div>
  );
}


