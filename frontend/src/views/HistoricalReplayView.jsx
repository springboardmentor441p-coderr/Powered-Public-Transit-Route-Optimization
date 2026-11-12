import React, { useState, useEffect } from 'react';
import { 
  History, 
  Play, 
  Pause, 
  RotateCcw, 
  SkipForward, 
  Calendar, 
  ShieldAlert, 
  Sparkles, 
  TrendingUp, 
  Clock, 
  AlertCircle 
} from 'lucide-react';
import { createReplaySession, getReplayState, controlReplaySession } from '../api';
import DataSourceBadge from '../components/DataSourceBadge';
import LoadingSpinner from '../components/LoadingSpinner';

export default function HistoricalReplayView() {
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(true);
  const [focusRoute, setFocusRoute] = useState('79');
  const [selectedDate, setSelectedDate] = useState('2026-06-01');

  // Initialize or fetch active session
  useEffect(() => {
    async function initSession() {
      setLoading(true);
      try {
        const savedId = localStorage.getItem('routeranker_replay_session');
        let state = null;
        if (savedId) {
          try {
            state = await getReplayState(savedId, focusRoute);
          } catch (e) {
            console.warn('Session expired or not found on backend, creating fresh one.');
          }
        }
        if (!state) {
          const fresh = await createReplaySession(1, 5);
          localStorage.setItem('routeranker_replay_session', fresh.session_id);
          state = await getReplayState(fresh.session_id, focusRoute);
        }
        setSession(state);
        setSelectedDate(state.current_virtual_date);
      } catch (err) {
        console.error('Failed to init replay session:', err);
      } finally {
        setLoading(false);
      }
    }
    initSession();
  }, [focusRoute]);

  const handleAction = async (action, dateParam = null) => {
    if (!session) return;
    try {
      const updated = await controlReplaySession(session.session_id, action, dateParam);
      setSession(updated);
      setSelectedDate(updated.current_virtual_date);
    } catch (e) {
      console.error(`Replay action ${action} failed:`, e);
    }
  };

  if (loading) return <LoadingSpinner message="Initializing Historical Replay Controller..." />;

  const focus = session?.focus_route;
  const sys = session?.system_summary;

  return (
    <div className="space-y-6 max-w-7xl">
      {/* Top Banner */}
      <div className="p-6 rounded-2xl bg-gradient-to-r from-slate-900 via-indigo-950/40 to-slate-900 border border-slate-800 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="w-2.5 h-2.5 rounded-full bg-indigo-400 animate-pulse"></span>
            <span className="text-xs uppercase tracking-wider font-semibold text-indigo-400">
              Technical Specification v3.8 Section 11
            </span>
          </div>
          <h2 className="text-2xl font-extrabold text-white tracking-tight flex items-center gap-3">
            <History className="w-6 h-6 text-indigo-400" />
            Historical Replay Controller
          </h2>
          <p className="text-sm text-slate-400 mt-1 max-w-3xl">
            Controlled chronological simulation over the held-out test period (<strong>2026-06-01 through 2026-07-31</strong>). 
            Enforces retrospective data-leakage protection: future actuals are revealed strictly according to the configured reporting delay.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <DataSourceBadge source="HISTORICAL_ARCHIVE" />
          <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
            Frozen Model Test Partition
          </span>
        </div>
      </div>

      {/* Control Console */}
      <div className="p-5 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          {/* Virtual Clock Display */}
          <div className="flex items-center gap-3">
            <div className="p-3 rounded-xl bg-slate-800/80 border border-slate-700/80 flex items-center gap-3">
              <Calendar className="w-5 h-5 text-indigo-400" />
              <div>
                <div className="text-[10px] uppercase font-bold text-slate-400">Virtual Simulation Date</div>
                <div className="text-lg font-mono font-extrabold text-white">
                  {session?.current_virtual_date} <span className="text-xs font-normal text-slate-400">({session?.day_of_week})</span>
                </div>
              </div>
            </div>

            {/* Delay notice */}
            <div className="p-3 rounded-xl bg-slate-800/80 border border-slate-700/80 hidden md:block">
              <div className="text-[10px] uppercase font-bold text-slate-400">Reporting Delay Gating</div>
              <div className="text-xs font-mono text-indigo-300 mt-1">
                Data permitted through: <strong>{session?.latest_permitted_actual_date}</strong>
              </div>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => handleAction(session?.status === 'PLAYING' ? 'PAUSE' : 'START')}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition shadow-sm ${
                session?.status === 'PLAYING'
                  ? 'bg-amber-600 hover:bg-amber-500 text-white'
                  : 'bg-emerald-600 hover:bg-emerald-500 text-white'
              }`}
            >
              {session?.status === 'PLAYING' ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
              <span>{session?.status === 'PLAYING' ? 'Pause Replay' : 'Start Playback'}</span>
            </button>

            <button
              onClick={() => handleAction('ADVANCE')}
              className="flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-semibold bg-slate-800 text-slate-200 hover:bg-slate-700 border border-slate-700 transition"
              title="Advance exactly one virtual day"
            >
              <SkipForward className="w-3.5 h-3.5 text-sky-400" />
              <span>Advance +1 Day</span>
            </button>

            <button
              onClick={() => handleAction('RESET')}
              className="flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-semibold bg-slate-800 text-slate-400 hover:text-white border border-slate-700 transition"
              title="Reset replay to 2026-06-01"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>Reset</span>
            </button>
          </div>
        </div>

        {/* Date jumper and Focus selector */}
        <div className="flex flex-wrap items-center gap-4 pt-2 border-t border-slate-800/80 text-xs">
          <div className="flex items-center gap-2">
            <label className="text-slate-400 font-semibold uppercase tracking-wider text-[11px]">Direct Date Jump:</label>
            <input
              type="date"
              min="2026-06-01"
              max="2026-07-31"
              value={selectedDate}
              onChange={(e) => {
                setSelectedDate(e.target.value);
                handleAction('SET_DATE', e.target.value);
              }}
              className="bg-slate-800 border border-slate-700 text-white rounded-lg px-2.5 py-1 text-xs focus:outline-none focus:border-indigo-500 font-mono"
            />
          </div>

          <div className="flex items-center gap-2">
            <label className="text-slate-400 font-semibold uppercase tracking-wider text-[11px]">Focus Corridor:</label>
            <select
              value={focusRoute}
              onChange={(e) => setFocusRoute(e.target.value)}
              className="bg-slate-800 border border-slate-700 text-white rounded-lg px-3 py-1 text-xs focus:outline-none focus:border-indigo-500"
            >
              <option value="79">Route 79 (79th - Highest Volume)</option>
              <option value="9">Route 9 (Ashland)</option>
              <option value="66">Route 66 (Chicago)</option>
              <option value="4">Route 4 (Cottage Grove)</option>
              <option value="49">Route 49 (Western)</option>
              <option value="X9">Route X9 (Ashland Express)</option>
            </select>
          </div>
        </div>
      </div>

      {/* Focus Route Evaluation Comparison Card */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 p-6 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <span>Route {focus?.route_id} Prediction vs Revealed Actuals</span>
              </h3>
              <p className="text-xs text-slate-400 mt-0.5">
                Saved forecast generated using only permitted pre-target history.
              </p>
            </div>
            <span className="text-xs font-mono text-indigo-400 bg-indigo-950/40 px-2.5 py-1 rounded-md border border-indigo-800/40">
              Method: {focus?.prediction_method}
            </span>
          </div>

          {/* Metric Triplet */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div className="p-4 rounded-xl bg-slate-800/50 border border-slate-700/60">
              <div className="text-[11px] font-semibold uppercase text-slate-400">Frozen Prediction</div>
              <div className="text-2xl font-black text-indigo-300 font-mono mt-1">
                {focus?.predicted_rides?.toLocaleString()} <span className="text-xs font-normal text-slate-400">rides</span>
              </div>
              <div className="text-[11px] text-slate-500 mt-1">Generated without future knowledge</div>
            </div>

            <div className="p-4 rounded-xl bg-slate-800/50 border border-slate-700/60">
              <div className="text-[11px] font-semibold uppercase text-slate-400">Revealed Actual Rides</div>
              <div className="text-2xl font-black text-sky-400 font-mono mt-1">
                {focus?.revealed_actual_rides !== null ? focus?.revealed_actual_rides?.toLocaleString() : 'Gated'} 
                <span className="text-xs font-normal text-slate-400"> rides</span>
              </div>
              <div className="text-[11px] text-slate-500 mt-1">From Chicago CTA actual records</div>
            </div>

            <div className="p-4 rounded-xl bg-slate-800/50 border border-slate-700/60">
              <div className="text-[11px] font-semibold uppercase text-slate-400">Replay Error / Accuracy</div>
              <div className={`text-2xl font-black font-mono mt-1 ${
                focus?.absolute_pct_error <= 15 ? 'text-emerald-400' : 'text-amber-400'
              }`}>
                {focus?.absolute_pct_error !== null ? `${focus?.absolute_pct_error}%` : 'N/A'}
                <span className="text-xs font-normal text-slate-400"> error</span>
              </div>
              <div className="text-[11px] text-slate-500 mt-1">
                Δ = {focus?.prediction_error ? (focus.prediction_error > 0 ? `+${focus.prediction_error}` : focus.prediction_error) : '0'} rides
              </div>
            </div>
          </div>

          {/* Audit & Leakage Protection Notice */}
          <div className="p-3.5 rounded-xl bg-slate-950/60 border border-slate-800 text-xs text-slate-300 flex items-start gap-2.5">
            <ShieldAlert className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
            <div className="space-y-1">
              <div className="font-semibold text-emerald-300">Strict Information-Availability Guardrail Active</div>
              <p className="text-slate-400 text-[11px] leading-relaxed">
                {session?.leakage_protection_notice} All features are calculated exclusively using observations captured on or before {session?.latest_permitted_actual_date}.
              </p>
            </div>
          </div>
        </div>

        {/* System Overview for Virtual Date */}
        <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-4">
          <h3 className="text-base font-bold text-white">System Bus Fleet Horizon</h3>
          <p className="text-xs text-slate-400">Active bus corridors simulated for {session?.current_virtual_date}.</p>

          <div className="space-y-3">
            <div className="flex justify-between items-center p-3 rounded-lg bg-slate-800/40 border border-slate-700/40 text-xs">
              <span className="text-slate-400">Active CTA Bus Routes</span>
              <span className="font-mono font-bold text-white">{sys?.active_routes_count} corridors</span>
            </div>

            <div className="flex justify-between items-center p-3 rounded-lg bg-slate-800/40 border border-slate-700/40 text-xs">
              <span className="text-slate-400">Total Actual Bus Rides</span>
              <span className="font-mono font-bold text-sky-400">{sys?.total_actual_bus_rides?.toLocaleString()}</span>
            </div>

            <div className="flex justify-between items-center p-3 rounded-lg bg-slate-800/40 border border-slate-700/40 text-xs">
              <span className="text-slate-400">Replay Session ID</span>
              <span className="font-mono text-slate-400 text-[11px]">{session?.session_id}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

