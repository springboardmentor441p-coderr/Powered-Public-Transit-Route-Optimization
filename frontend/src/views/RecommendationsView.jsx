import React, { useState, useEffect } from 'react';
import { 
  Sliders, 
  Bus, 
  ArrowRight, 
  TrendingUp, 
  TrendingDown, 
  AlertCircle, 
  CheckCircle2, 
  Lightbulb, 
  RotateCcw 
} from 'lucide-react';
import { simulateScenario } from '../api';
import DataSourceBadge from '../components/DataSourceBadge';
import LoadingSpinner from '../components/LoadingSpinner';

const CORRIDORS = [
  { id: '79', name: 'Route 79 (79th)', defaultTrips: 160 },
  { id: '9', name: 'Route 9 (Ashland)', defaultTrips: 155 },
  { id: '66', name: 'Route 66 (Chicago)', defaultTrips: 140 },
  { id: '4', name: 'Route 4 (Cottage Grove)', defaultTrips: 130 },
  { id: '49', name: 'Route 49 (Western)', defaultTrips: 145 },
  { id: 'X9', name: 'Route X9 (Ashland Express)', defaultTrips: 65 },
];

export default function RecommendationsView() {
  const [selectedRoute, setSelectedRoute] = useState('79');
  const [proposedTrips, setProposedTrips] = useState(160);
  const [simulation, setSimulation] = useState(null);
  const [loading, setLoading] = useState(true);

  const runSimulation = async (routeId, trips) => {
    setLoading(true);
    try {
      const res = await simulateScenario(routeId, trips);
      setSimulation(res);
    } catch (e) {
      console.error('Simulation failed', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    runSimulation(selectedRoute, proposedTrips);
  }, [selectedRoute]);

  const handleRouteSelect = (routeId) => {
    setSelectedRoute(routeId);
    const def = CORRIDORS.find(c => c.id === routeId)?.defaultTrips || 140;
    setProposedTrips(def);
  };

  const handleSliderChange = (val) => {
    const num = Number(val);
    setProposedTrips(num);
  };

  const handleApply = () => {
    runSimulation(selectedRoute, proposedTrips);
  };

  const handleQuickAdjust = (pct) => {
    const base = simulation?.baseline?.scheduled_daily_trips || proposedTrips;
    const adjusted = Math.round(base * (1 + pct));
    const clamped = Math.max(10, Math.min(400, adjusted));
    setProposedTrips(clamped);
    runSimulation(selectedRoute, clamped);
  };

  const handleReset = () => {
    const base = simulation?.baseline?.scheduled_daily_trips || 149;
    setProposedTrips(base);
    runSimulation(selectedRoute, base);
  };

  const deltaTrips = simulation?.impact?.trips_delta || 0;
  const deltaHeadway = simulation?.impact?.headway_minutes_delta || 0;
  const deltaCap = simulation?.impact?.capacity_delta || 0;

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="p-6 rounded-2xl bg-gradient-to-r from-slate-900 via-sky-950/40 to-slate-900 border border-slate-800 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="w-2.5 h-2.5 rounded-full bg-teal-400"></span>
            <span className="text-xs uppercase tracking-wider font-semibold text-teal-400">Transit Operations Decision Support</span>
          </div>
          <h2 className="text-2xl font-extrabold text-white tracking-tight">Smart Service Frequency Simulator</h2>
          <p className="text-sm text-slate-400 mt-1 max-w-2xl">
            Simulate timetable and vehicle frequency adjustments against forecasted CTA passenger demand to optimize headway and prevent overcrowding.
          </p>
        </div>
        <DataSourceBadge source="GTFS_SIMULATION" />
      </div>

      {/* Simulator Control Card */}
      <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Corridor Selection */}
          <div className="space-y-2">
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400">
              Select Bus Corridor
            </label>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
              {CORRIDORS.map((c) => {
                const active = selectedRoute === c.id;
                return (
                  <button
                    key={c.id}
                    onClick={() => handleRouteSelect(c.id)}
                    className={`p-3 rounded-xl text-left border transition ${
                      active
                        ? 'bg-sky-500/15 border-sky-500/40 text-white font-semibold shadow-sm'
                        : 'bg-slate-800/60 border-slate-700/60 text-slate-400 hover:text-white'
                    }`}
                  >
                    <div className="text-xs">{c.name}</div>
                    <div className="text-[10px] text-slate-500 mt-0.5">Base: ~{c.defaultTrips} trips</div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Interactive Trip Frequency Slider */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <label className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                Proposed Scheduled Daily Trips
              </label>
              <div className="text-2xl font-extrabold text-sky-400 font-mono">
                {proposedTrips} <span className="text-xs font-normal text-slate-400">trips/day</span>
              </div>
            </div>

            <input
              type="range"
              min="10"
              max="400"
              step="5"
              value={proposedTrips}
              onChange={(e) => handleSliderChange(e.target.value)}
              onMouseUp={handleApply}
              onTouchEnd={handleApply}
              className="w-full accent-sky-400 cursor-pointer h-2 bg-slate-700 rounded-lg"
            />

            {/* Quick Adjustment Buttons */}
            <div className="flex items-center gap-2 flex-wrap text-xs">
              <span className="text-slate-500 text-[11px]">Quick adjustments:</span>
              <button
                onClick={() => handleQuickAdjust(-0.15)}
                className="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700"
              >
                -15% Trips
              </button>
              <button
                onClick={() => handleQuickAdjust(-0.05)}
                className="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700"
              >
                -5% Trips
              </button>
              <button
                onClick={() => handleQuickAdjust(0.10)}
                className="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700"
              >
                +10% Trips
              </button>
              <button
                onClick={() => handleQuickAdjust(0.20)}
                className="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700"
              >
                +20% Trips
              </button>
              <button
                onClick={handleReset}
                className="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 flex items-center gap-1"
                title="Reset to GTFS baseline"
              >
                <RotateCcw className="w-3 h-3" /> Reset
              </button>
            </div>
          </div>
        </div>
      </div>

      {loading && <LoadingSpinner message="Simulating timetable headway and capacity dynamics..." />}

      {simulation && !loading && (
        <div className="space-y-6">
          {/* Comparison KPI Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Scheduled Trips */}
            <div className="p-5 rounded-xl bg-slate-900/80 border border-slate-800 space-y-2">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">Scheduled Trips</span>
              <div className="flex items-baseline justify-between">
                <span className="text-2xl font-extrabold text-white">{simulation.simulation?.proposed_trips}</span>
                <span className={`text-xs font-mono font-semibold ${deltaTrips >= 0 ? 'text-teal-400' : 'text-amber-400'}`}>
                  {deltaTrips >= 0 ? `+${deltaTrips}` : deltaTrips} trips
                </span>
              </div>
              <div className="text-[11px] text-slate-500">Baseline GTFS: {simulation.baseline?.scheduled_daily_trips} trips</div>
            </div>

            {/* Operating Headway */}
            <div className="p-5 rounded-xl bg-slate-900/80 border border-slate-800 space-y-2">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">Average Headway</span>
              <div className="flex items-baseline justify-between">
                <span className="text-2xl font-extrabold text-sky-400 font-mono">
                  {simulation.simulation?.operating_headway_minutes} min
                </span>
                <span className={`text-xs font-mono font-semibold ${deltaHeadway <= 0 ? 'text-teal-400' : 'text-rose-400'}`}>
                  {deltaHeadway <= 0 ? `${deltaHeadway}m` : `+${deltaHeadway}m`}
                </span>
              </div>
              <div className="text-[11px] text-slate-500">Baseline GTFS: {simulation.baseline?.baseline_headway_minutes} min</div>
            </div>

            {/* Daily Capacity */}
            <div className="p-5 rounded-xl bg-slate-900/80 border border-slate-800 space-y-2">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">Nominal Daily Trip Capacity</span>
              <div className="flex items-baseline justify-between">
                <span className="text-2xl font-extrabold text-white">
                  {simulation.simulation?.total_daily_capacity?.toLocaleString()}
                </span>
                <span className={`text-xs font-mono font-semibold ${deltaCap >= 0 ? 'text-teal-400' : 'text-amber-400'}`}>
                  {deltaCap >= 0 ? `+${deltaCap?.toLocaleString()}` : deltaCap?.toLocaleString()}
                </span>
              </div>
              <div className="text-[11px] text-slate-500">Baseline Nominal: {simulation.baseline?.baseline_daily_capacity?.toLocaleString()} spaces (60/bus)</div>
            </div>

            {/* Estimated Boardings per Trip */}
            <div className="p-5 rounded-xl bg-slate-900/80 border border-slate-800 space-y-2">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">Est. Boardings Per Trip</span>
              <div className="flex items-baseline justify-between">
                <span className="text-2xl font-extrabold text-white font-mono">
                  {simulation.simulation?.estimated_boardings_per_trip || simulation.metrics_comparison?.passenger_loading_intensity?.proposed_boardings_per_trip}
                </span>
                <span className="text-xs text-slate-400">
                  {simulation.simulation?.estimated_boarding_ratio || simulation.metrics_comparison?.passenger_loading_intensity?.proposed_boarding_ratio_pct}% nominal
                </span>
              </div>
              <div className="text-[11px] text-slate-500">
                Baseline: {simulation.baseline?.baseline_boardings_per_trip || simulation.metrics_comparison?.passenger_loading_intensity?.current_boardings_per_trip} boardings/trip
              </div>
            </div>
          </div>

          {/* AI Recommendation Card */}
          <div className="p-6 rounded-2xl bg-gradient-to-r from-slate-900 via-teal-950/30 to-slate-900 border border-teal-500/30 space-y-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-teal-500/20 border border-teal-500/40 flex items-center justify-center text-teal-400">
                <Lightbulb className="w-5 h-5" />
              </div>
              <div>
                <span className="text-xs uppercase tracking-wider font-bold text-teal-400">
                  Automated Recommendation Rationale
                </span>
                <h3 className="text-lg font-bold text-white">
                  {simulation.recommendation?.title || "Operational Recommendation"}
                </h3>
              </div>
            </div>

            <p className="text-sm text-slate-300 leading-relaxed max-w-3xl">
              {simulation.recommendation?.explanation}
            </p>

            <div className="pt-3 border-t border-slate-800 flex flex-wrap items-center gap-6 text-xs text-slate-400">
              <div>
                Target Action: <strong className="text-white">{simulation.recommendation?.action_category}</strong>
              </div>
              <div>
                Corridor: <strong className="text-white">{simulation.route?.route_long_name} ({selectedRoute})</strong>
              </div>
              <div>
                Vehicle Type: <strong className="text-white">Standard 40ft/60ft Low-Floor Bus</strong>
              </div>
            </div>
          </div>

          {/* Capacity and Data Transparency Disclosure */}
          <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 text-xs text-slate-400 space-y-1">
            <div className="font-semibold text-slate-300 flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-teal-400"></span>
              Capacity & Occupancy Disclosure
            </div>
            <p className="leading-relaxed">
              {simulation.occupancy_disclaimer || "Bus capacity represents nominal standard 40ft bus volume (40 seated + 20 standing). Real-time Automated Passenger Counter (APC) occupancy is not public on CTA tracker feeds."}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

