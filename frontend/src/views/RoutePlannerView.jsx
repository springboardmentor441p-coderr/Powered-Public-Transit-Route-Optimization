import React, { useState, useEffect } from 'react';
import { 
  Navigation, 
  MapPin, 
  ArrowRight, 
  Clock, 
  Shuffle, 
  Footprints, 
  CheckCircle, 
  Train, 
  Bus, 
  SlidersHorizontal 
} from 'lucide-react';
import { planRoute, searchLocations } from '../api';
import DataSourceBadge from '../components/DataSourceBadge';
import LoadingSpinner from '../components/LoadingSpinner';

const PRESETS = [
  { label: "Belmont → Jackson", from: "Belmont", to: "Jackson" },
  { label: "O'Hare → Loop (Clark/Lake)", from: "O'Hare", to: "Clark/Lake" },
  { label: "Midway → Jackson", from: "Midway", to: "Jackson" },
  { label: "Howard → 95th/Dan Ryan", from: "Howard", to: "95th/Dan Ryan" },
  { label: "Logan Square → Monroe", from: "Logan Square", to: "Monroe" },
];

export default function RoutePlannerView() {
  const [origin, setOrigin] = useState("Belmont");
  const [destination, setDestination] = useState("Jackson");
  const [optimizeFor, setOptimizeFor] = useState("duration");
  const [maxTransfers, setMaxTransfers] = useState(3);
  const [loading, setLoading] = useState(false);
  const [planResult, setPlanResult] = useState(null);
  const [error, setError] = useState(null);

  // Suggestions
  const [originSuggestions, setOriginSuggestions] = useState([]);
  const [destSuggestions, setDestSuggestions] = useState([]);

  const handleSearchOrigin = async (val) => {
    setOrigin(val);
    if (val.length >= 2) {
      try {
        const res = await searchLocations(val);
        setOriginSuggestions(res.locations || []);
      } catch (e) {}
    } else {
      setOriginSuggestions([]);
    }
  };

  const handleSearchDest = async (val) => {
    setDestination(val);
    if (val.length >= 2) {
      try {
        const res = await searchLocations(val);
        setDestSuggestions(res.locations || []);
      } catch (e) {}
    } else {
      setDestSuggestions([]);
    }
  };

  const executePlan = async (from = origin, to = destination) => {
    if (!from || !to) return;
    setLoading(true);
    setError(null);
    try {
      const res = await planRoute(from, to, optimizeFor, maxTransfers);
      if (res.error) {
        setError(res.error);
        setPlanResult(null);
      } else {
        setPlanResult(res);
      }
    } catch (e) {
      setError(e.message || "Failed to calculate CTA route itinerary.");
      setPlanResult(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // Initial plan with default preset
    executePlan("Belmont", "Jackson");
  }, []);

  const handlePreset = (p) => {
    setOrigin(p.from);
    setDestination(p.to);
    executePlan(p.from, p.to);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="p-6 rounded-2xl bg-gradient-to-r from-slate-900 via-sky-950/40 to-slate-900 border border-slate-800 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="w-2.5 h-2.5 rounded-full bg-teal-400"></span>
            <span className="text-xs uppercase tracking-wider font-semibold text-teal-400">Network Routing Engine</span>
          </div>
          <h2 className="text-2xl font-extrabold text-white tracking-tight">Multi-Modal CTA Trip Planner</h2>
          <p className="text-sm text-slate-400 mt-1">
            Dijkstra shortest path algorithm with realistic walking transfers across 182 CTA transit nodes and 440 directed edges.
          </p>
        </div>
        <DataSourceBadge source="HISTORICAL" />
      </div>

      {/* Preset Quick Buttons */}
      <div className="flex items-center gap-2 flex-wrap text-xs">
        <span className="text-slate-400 font-semibold uppercase tracking-wider">Quick Presets:</span>
        {PRESETS.map((p, i) => (
          <button
            key={i}
            onClick={() => handlePreset(p)}
            className="px-3 py-1.5 rounded-lg bg-slate-800/80 hover:bg-slate-700 text-slate-300 border border-slate-700 transition"
          >
            {p.label}
          </button>
        ))}
      </div>

      {/* Form & Controls Grid */}
      <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Origin Input */}
          <div className="relative">
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5">
              Origin (CTA Station / Stop)
            </label>
            <div className="relative">
              <MapPin className="w-4 h-4 text-emerald-400 absolute left-3.5 top-3.5" />
              <input
                type="text"
                value={origin}
                onChange={(e) => handleSearchOrigin(e.target.value)}
                placeholder="e.g. Belmont, O'Hare, Midway"
                className="w-full bg-slate-800 border border-slate-700 rounded-xl pl-10 pr-4 py-2.5 text-sm text-white focus:outline-none focus:border-sky-500"
              />
            </div>
            {originSuggestions.length > 0 && (
              <div className="absolute left-0 right-0 mt-1 bg-slate-800 border border-slate-700 rounded-xl shadow-xl z-30 max-h-48 overflow-y-auto">
                {originSuggestions.map((s, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => {
                      setOrigin(s.name);
                      setOriginSuggestions([]);
                    }}
                    className="w-full text-left px-4 py-2 text-xs text-slate-200 hover:bg-slate-700 border-b border-slate-700/50 flex items-center justify-between"
                  >
                    <span>{s.name}</span>
                    <span className="text-[10px] font-mono text-slate-400">{s.mode}</span>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Destination Input */}
          <div className="relative">
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5">
              Destination (CTA Station / Stop)
            </label>
            <div className="relative">
              <MapPin className="w-4 h-4 text-rose-400 absolute left-3.5 top-3.5" />
              <input
                type="text"
                value={destination}
                onChange={(e) => handleSearchDest(e.target.value)}
                placeholder="e.g. Jackson, Clark/Lake, 95th/Dan Ryan"
                className="w-full bg-slate-800 border border-slate-700 rounded-xl pl-10 pr-4 py-2.5 text-sm text-white focus:outline-none focus:border-sky-500"
              />
            </div>
            {destSuggestions.length > 0 && (
              <div className="absolute left-0 right-0 mt-1 bg-slate-800 border border-slate-700 rounded-xl shadow-xl z-30 max-h-48 overflow-y-auto">
                {destSuggestions.map((s, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => {
                      setDestination(s.name);
                      setDestSuggestions([]);
                    }}
                    className="w-full text-left px-4 py-2 text-xs text-slate-200 hover:bg-slate-700 border-b border-slate-700/50 flex items-center justify-between"
                  >
                    <span>{s.name}</span>
                    <span className="text-[10px] font-mono text-slate-400">{s.mode}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Filters and Plan Button */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pt-2 border-t border-slate-800">
          <div className="flex items-center gap-4 text-xs text-slate-400">
            <div className="flex items-center gap-2">
              <span>Optimization:</span>
              <select
                value={optimizeFor}
                onChange={(e) => setOptimizeFor(e.target.value)}
                className="bg-slate-800 border border-slate-700 rounded-lg px-2.5 py-1.5 text-white text-xs"
              >
                <option value="duration">Fastest Duration</option>
                <option value="transfers">Minimum Transfers</option>
              </select>
            </div>

            <div className="flex items-center gap-2">
              <span>Max Transfers:</span>
              <select
                value={maxTransfers}
                onChange={(e) => setMaxTransfers(Number(e.target.value))}
                className="bg-slate-800 border border-slate-700 rounded-lg px-2.5 py-1.5 text-white text-xs"
              >
                <option value="1">1 Transfer</option>
                <option value="2">2 Transfers</option>
                <option value="3">3 Transfers</option>
              </select>
            </div>
          </div>

          <button
            onClick={() => executePlan()}
            disabled={loading}
            className="flex items-center justify-center gap-2 px-6 py-2.5 rounded-xl bg-gradient-to-r from-sky-500 to-teal-400 text-slate-950 font-bold text-sm shadow-lg shadow-sky-500/20 hover:opacity-95 transition disabled:opacity-50"
          >
            <Navigation className="w-4 h-4" />
            <span>{loading ? "Computing Path..." : "Calculate Route"}</span>
          </button>
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-sm">
          <strong>Routing Notice:</strong> {error}
        </div>
      )}

      {loading && <LoadingSpinner message="Evaluating multi-modal network paths..." />}

      {/* Results View */}
      {planResult && !loading && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main Recommended Itinerary (2 Cols) */}
          <div className="lg:col-span-2 p-6 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-slate-800 gap-2">
              <div>
                <span className="text-xs uppercase tracking-wider font-bold text-teal-400">Recommended Itinerary</span>
                <h3 className="text-xl font-bold text-white flex items-center gap-2 mt-0.5">
                  <span>{planResult.origin?.name}</span>
                  <ArrowRight className="w-4 h-4 text-slate-500" />
                  <span>{planResult.destination?.name}</span>
                </h3>
              </div>

              <div className="flex items-center gap-3">
                <div className="p-2.5 rounded-xl bg-slate-800/80 border border-slate-700 text-center">
                  <div className="text-lg font-extrabold text-sky-400">
                    {planResult.recommended_itinerary?.total_duration_minutes} min
                  </div>
                  <div className="text-[10px] text-slate-400 uppercase">Total Time</div>
                </div>

                <div className="p-2.5 rounded-xl bg-slate-800/80 border border-slate-700 text-center">
                  <div className="text-lg font-extrabold text-teal-400">
                    {planResult.recommended_itinerary?.transfers_count}
                  </div>
                  <div className="text-[10px] text-slate-400 uppercase">Transfers</div>
                </div>
              </div>
            </div>

            {/* Step-by-Step Leg Breakdown */}
            <div className="space-y-4">
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400">
                Turn-by-Turn Transit Directions
              </h4>

              <div className="relative pl-6 space-y-6 before:absolute before:left-2 before:top-2 before:bottom-2 before:w-0.5 before:bg-slate-700">
                {planResult.recommended_itinerary?.itinerary_legs?.map((leg, idx) => {
                  const isWalk = leg.mode?.toUpperCase() === 'WALK' || leg.mode?.toUpperCase() === 'TRANSFER' || leg.action?.includes('Transfer');
                  const duration = leg.duration_minutes ?? leg.estimated_minutes ?? 0;
                  const fromStation = leg.from_stop ?? leg.from_node ?? 'Boarding Stop';
                  const toStation = leg.to_stop ?? leg.to_node ?? 'Alighting Stop';

                  return (
                    <div key={idx} className="relative">
                      {/* Step Circle */}
                      <span className={`absolute -left-6 top-1 w-4 h-4 rounded-full border-2 border-slate-900 ${
                        isWalk ? 'bg-amber-400' : 'bg-sky-400'
                      }`}></span>

                      <div className="p-4 rounded-xl bg-slate-800/50 border border-slate-700/60 space-y-2">
                        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1">
                          <div className="font-semibold text-sm text-white flex items-center gap-2">
                            {isWalk ? <Footprints className="w-4 h-4 text-amber-400 flex-shrink-0" /> : <Train className="w-4 h-4 text-sky-400 flex-shrink-0" />}
                            <span>{leg.instruction}</span>
                          </div>
                          <span className="text-xs font-mono text-sky-400 font-bold">
                            {duration} min
                          </span>
                        </div>

                        <div className="flex flex-wrap items-center gap-3 text-xs text-slate-400 pt-1 border-t border-slate-700/40">
                          <div>
                            From: <strong className="text-slate-200">{fromStation}</strong>
                          </div>
                          <span>→</span>
                          <div>
                            To: <strong className="text-slate-200">{toStation}</strong>
                          </div>
                          {leg.stops_count && (
                            <span className="px-2 py-0.5 rounded bg-slate-700/60 text-slate-300 text-[10px] font-mono">
                              {leg.stops_count} stop{leg.stops_count > 1 ? 's' : ''}
                            </span>
                          )}
                          {leg.line && !isWalk && (
                            <span className="px-2 py-0.5 rounded bg-sky-500/20 text-sky-300 text-[10px] font-bold">
                              {leg.line} Line
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Alternative Routes Panel */}
          <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-4">
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-2">
              <Shuffle className="w-3.5 h-3.5 text-sky-400" /> Alternative Itineraries
            </h4>

            {(!planResult.alternative_itineraries || planResult.alternative_itineraries.length === 0) ? (
              <div className="text-xs text-slate-500 py-6 text-center">
                Optimal path is the single dominant direct route on the network.
              </div>
            ) : (
              planResult.alternative_itineraries.map((alt, idx) => (
                <div key={idx} className="p-3.5 rounded-xl bg-slate-800/40 border border-slate-700 text-xs space-y-2">
                  <div className="flex items-center justify-between font-semibold text-white">
                    <span>{alt.label || `Option #${idx + 2}`}</span>
                    <span className="text-sky-400 font-mono font-bold">{alt.total_duration_minutes} min</span>
                  </div>
                  <div className="text-slate-400 flex items-center gap-3">
                    <span>{alt.transfers_count} transfer(s)</span>
                    <span>•</span>
                    <span>{alt.total_stops} stop(s)</span>
                  </div>
                  {alt.itinerary_legs && (
                    <div className="text-[11px] text-slate-400 space-y-1 pt-1 border-t border-slate-700/40">
                      {alt.itinerary_legs.map((l, lidx) => (
                        <div key={lidx} className="truncate">• {l.instruction} ({l.duration_minutes}m)</div>
                      ))}
                    </div>
                  )}
                </div>
              ))
            )}

            {/* Model Architecture Note */}
            <div className="pt-4 border-t border-slate-800 text-[11px] text-slate-500 space-y-1">
              <div className="font-semibold text-slate-400">Routing Methodology</div>
              <p>
                Calculated on static CTA GTFS network topology with transfer penalties (5-min walk/wait penalty per connection).
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

