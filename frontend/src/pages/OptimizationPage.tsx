import { useState } from 'react';
import { ArrowDown, ArrowUp, BusFront, Play, Search, SlidersHorizontal } from 'lucide-react';
import { useApi } from '../hooks/useApi';
import { getRoutes, runSimulation } from '../services/api';
import { Badge, Card, EmptyState, ErrorAlert, LoadingSpinner, PageHeader } from '../components/ui';
import type { Route, SimulationResult } from '../types';

const inputClass = 'mt-2 w-full rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-900 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100 dark:border-slate-700 dark:bg-slate-800 dark:text-white';

export default function OptimizationPage() {
  const { data: routes, loading: routesLoading, error: routesError, refetch } = useApi(() => getRoutes(1, 500));
  const [routeId, setRouteId] = useState('');
  const [routeSearch, setRouteSearch] = useState('');
  const [routeOptions, setRouteOptions] = useState<Route[] | null>(null);
  const [searchingRoutes, setSearchingRoutes] = useState(false);
  const [frequencyMultiplier, setFrequencyMultiplier] = useState(1.25);
  const [stopConsolidationPct, setStopConsolidationPct] = useState(0);
  const [result, setResult] = useState<SimulationResult | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const searchRoutes = async () => {
    setSearchingRoutes(true);
    setError(null);
    try {
      const response = await getRoutes(1, 100, routeSearch);
      setRouteOptions(response.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to search routes.');
    } finally {
      setSearchingRoutes(false);
    }
  };

  const simulate = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!routeId) return;
    setSubmitting(true);
    setError(null);
    try {
      setResult(await runSimulation({ route_id: routeId, frequency_multiplier: frequencyMultiplier, stop_consolidation_pct: stopConsolidationPct }));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to run the schedule scenario.');
      setResult(null);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader title="Schedule Optimization" subtitle="Explore hypothetical timetable scenarios using the existing deterministic simulator." />
      <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-200">
        <strong>Simulation estimates only.</strong> Results are modeled from GTFS schedule features and scenario assumptions. They are not actual vehicle assignments, observed travel times, passenger demand, or live operational measurements.
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(280px,0.8fr)_minmax(0,1.2fr)]">
        <Card title="Scenario controls">
          {routesLoading ? <LoadingSpinner text="Loading routes…" /> : routesError ? <ErrorAlert message={routesError} onRetry={refetch} /> : (
            <form onSubmit={simulate} className="space-y-5">
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
                Select route
                <span className="mt-2 flex gap-2">
                  <input type="search" value={routeSearch} onChange={event => setRouteSearch(event.target.value)} onKeyDown={event => { if (event.key === 'Enter') { event.preventDefault(); void searchRoutes(); } }} placeholder="Search route name or ID" className="min-w-0 flex-1 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100 dark:border-slate-700 dark:bg-slate-800 dark:text-white" />
                  <button type="button" title="Search all routes" aria-label="Search all routes" onClick={() => void searchRoutes()} disabled={searchingRoutes} className="rounded-lg border border-slate-200 px-3 text-slate-600 hover:bg-slate-50 disabled:opacity-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800">{searchingRoutes ? '…' : <Search className="h-4 w-4" />}</button>
                </span>
                <select required value={routeId} onChange={event => setRouteId(event.target.value)} className={inputClass}>
                  <option value="">Choose a route…</option>
                  {(routeOptions ?? routes?.items ?? []).map((route: Route) => <option key={route.route_id} value={route.route_id}>{route.route_short_name} — {route.route_long_name} ({route.route_id})</option>)}
                </select>
                <span className="mt-1 block text-xs font-normal text-slate-500">Search matches across the route catalogue. Without a search, showing the first {routes?.items.length ?? 0} routes.</span>
              </label>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
                <span className="flex justify-between"><span>Frequency multiplier</span><span className="font-semibold text-blue-600">{frequencyMultiplier.toFixed(2)}×</span></span>
                <input type="range" min="0.5" max="2" step="0.05" value={frequencyMultiplier} onChange={event => setFrequencyMultiplier(Number(event.target.value))} className="mt-3 w-full accent-blue-600" />
                <span className="mt-1 flex justify-between text-xs text-slate-500"><span>0.50× fewer scheduled trips</span><span>2.00× more scheduled trips</span></span>
              </label>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
                <span className="flex justify-between"><span>Stop consolidation assumption</span><span className="font-semibold text-blue-600">{stopConsolidationPct}%</span></span>
                <input type="range" min="0" max="50" step="1" value={stopConsolidationPct} onChange={event => setStopConsolidationPct(Number(event.target.value))} className="mt-3 w-full accent-blue-600" />
                <span className="mt-1 flex justify-between text-xs text-slate-500"><span>No change</span><span>Up to 50% fewer stops</span></span>
              </label>
              <button type="submit" disabled={!routeId || submitting} className="flex w-full items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-3 text-sm font-semibold text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50">
                {submitting ? <LoadingSpinner text="Simulating…" /> : <><Play className="h-4 w-4" /> Run schedule simulation</>}
              </button>
              {error && <ErrorAlert message={error} />}
            </form>
          )}
        </Card>

        <div className="space-y-6">
          {!result && <Card><EmptyState title="Configure a scenario" description="Select a route and adjust the assumptions to compare baseline and simulated schedule estimates." /></Card>}
          {result && <>
            <Card title={`${result.route_short_name} · ${result.scenario_name}`}>
              <div className="mb-5 flex flex-wrap items-center gap-2"><Badge color="amber">Hypothetical scenario</Badge><span className="text-xs text-slate-500">Route ID {result.route_id}</span></div>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <MetricCompare label="Average headway" unit="min" baseline={result.baseline_headway_min} simulated={result.simulated_headway_min} decimals={1} />
                <MetricCompare label="Trip duration" unit="min" baseline={result.baseline_trip_duration_min} simulated={result.simulated_trip_duration_min} decimals={1} />
                <MetricCompare label="Schedule-derived speed" unit="km/h" baseline={result.baseline_speed_kmh} simulated={result.simulated_speed_kmh} decimals={1} />
                <MetricCompare label="Estimated peak fleet" unit="vehicles" baseline={result.baseline_vehicles_required} simulated={result.simulated_vehicles_required} decimals={0} />
                <MetricCompare label="Scheduled trips" unit="trips/day" baseline={result.baseline_trips} simulated={result.simulated_trips} decimals={0} />
                <MetricCompare label="Scheduled vehicle hours" unit="hours" baseline={result.baseline_vehicle_hours} simulated={result.simulated_vehicle_hours} decimals={1} />
              </div>
            </Card>
            <Card title="Scenario assumptions and methodology">
              <div className="flex items-start gap-3 text-sm text-slate-600 dark:text-slate-300"><SlidersHorizontal className="mt-0.5 h-5 w-5 shrink-0 text-blue-600" /><div><p>Fleet requirement is a schedule-based estimate using cycle time, headway, and the simulator's recovery allowance. Stop consolidation applies a modeled trip-duration adjustment; it does not assert that any stop can or should be removed.</p>{result.schedule_derived_notes.length > 0 && <ul className="mt-3 list-disc space-y-1 pl-5">{result.schedule_derived_notes.map((note, index) => <li key={index}>{note}</li>)}</ul>}</div></div>
            </Card>
          </>}
        </div>
      </div>
      <div className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400"><BusFront className="h-4 w-4" /> No passenger, occupancy, congestion, or live-operation data is used.</div>
    </div>
  );
}

function MetricCompare({ label, unit, baseline, simulated, decimals }: { label: string; unit: string; baseline: number; simulated: number; decimals: number }) {
  const change = simulated - baseline;
  return (
    <div className="rounded-lg border border-slate-200 p-4 dark:border-slate-700">
      <p className="text-xs font-medium text-slate-500 dark:text-slate-400">{label}</p>
      <div className="mt-3 grid grid-cols-[1fr_auto_1fr] items-center gap-2 text-center">
        <div><p className="text-xs text-slate-400">Baseline</p><p className="mt-1 text-lg font-bold text-slate-800 dark:text-slate-100">{baseline.toFixed(decimals)} <span className="text-xs font-normal">{unit}</span></p></div>
        <div className="text-slate-300">→</div>
        <div><p className="text-xs text-slate-400">Simulated</p><p className="mt-1 text-lg font-bold text-blue-700 dark:text-blue-300">{simulated.toFixed(decimals)} <span className="text-xs font-normal">{unit}</span></p></div>
      </div>
      <p className={`mt-2 flex items-center justify-center gap-1 text-xs ${change <= 0 ? 'text-emerald-600' : 'text-amber-600'}`}>
        {change <= 0 ? <ArrowDown className="h-3 w-3" /> : <ArrowUp className="h-3 w-3" />}{Math.abs(change).toFixed(decimals)} {unit} change
      </p>
    </div>
  );
}
