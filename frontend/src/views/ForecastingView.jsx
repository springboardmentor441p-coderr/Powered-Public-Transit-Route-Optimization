import React, { useState, useEffect } from 'react';
import { 
  TrendingUp, 
  Calendar, 
  BarChart2, 
  Cpu, 
  CheckCircle2, 
  Layers, 
  ShieldAlert,
  Sparkles
} from 'lucide-react';
import { 
  ResponsiveContainer, 
  AreaChart, 
  Area, 
  XAxis, 
  YAxis, 
  Tooltip, 
  CartesianGrid 
} from 'recharts';
import { 
  getSystemForecast, 
  getRouteForecast, 
  getModelMetrics 
} from '../api';
import CrowdBadge from '../components/CrowdBadge';
import DataSourceBadge from '../components/DataSourceBadge';
import LoadingSpinner from '../components/LoadingSpinner';

const ROUTE_OPTIONS = [
  { id: 'SYSTEM', name: 'CTA Entire System (Bus + Rail Totals)' },
  { id: '79', name: 'Route 79 (79th - Highest Bus Ridership)' },
  { id: '9', name: 'Route 9 (Ashland Corridor)' },
  { id: '66', name: 'Route 66 (Chicago Ave)' },
  { id: '4', name: 'Route 4 (Cottage Grove)' },
  { id: '49', name: 'Route 49 (Western Ave)' },
  { id: 'X9', name: 'Route X9 (Ashland Express)' },
];

export default function ForecastingView() {
  const [selectedScope, setSelectedScope] = useState('SYSTEM');
  const [horizonDays, setHorizonDays] = useState(14);
  const [loading, setLoading] = useState(true);
  const [forecastData, setForecastData] = useState(null);
  const [metrics, setMetrics] = useState(null);

  useEffect(() => {
    setLoading(true);
    const fetchFc = selectedScope === 'SYSTEM'
      ? getSystemForecast(horizonDays)
      : getRouteForecast(selectedScope, horizonDays);

    Promise.allSettled([fetchFc, getModelMetrics()])
      .then(([fcRes, mRes]) => {
        if (fcRes.status === 'fulfilled') setForecastData(fcRes.value);
        if (mRes.status === 'fulfilled') setMetrics(mRes.value);
        setLoading(false);
      });
  }, [selectedScope, horizonDays]);

  const daysList = forecastData?.forecast || [];

  const chartData = daysList.map((d) => ({
    date: d.date?.slice(5),
    day: d.day_of_week?.slice(0, 3),
    demand: d.predicted_total_demand || d.predicted_rides,
    lower: d.lower_ci_95 ?? d.confidence_lower ?? d.lower_bound,
    upper: d.upper_ci_95 ?? d.confidence_upper ?? d.upper_bound,
    crowd: d.crowd_classification,
  }));

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="p-6 rounded-2xl bg-gradient-to-r from-slate-900 via-sky-950/40 to-slate-900 border border-slate-800 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="w-2.5 h-2.5 rounded-full bg-purple-400"></span>
            <span className="text-xs uppercase tracking-wider font-semibold text-purple-400">Machine Learning Intelligence</span>
          </div>
          <h2 className="text-2xl font-extrabold text-white tracking-tight">Daily Passenger Demand Forecasting</h2>
          <p className="text-sm text-slate-400 mt-1 max-w-2xl">
            Multi-horizon forecasts trained with lag-shifted features on chronological splits (2001–2024 train, 2025 validation, 2026 unseen test set).
          </p>
        </div>
        <DataSourceBadge source="FORECAST" />
      </div>

      {/* Methodology & Provenance Disclosure */}
      <div className="p-4 rounded-xl bg-purple-950/20 border border-purple-500/20 flex flex-col md:flex-row items-start md:items-center justify-between gap-3 text-xs">
        <div className="flex items-center gap-2 text-purple-300 font-semibold">
          <Sparkles className="w-4 h-4 text-purple-400 shrink-0" />
          <span>Statistically Validated Prediction Intervals & Data Boundary</span>
        </div>
        <p className="text-slate-400 max-w-3xl leading-relaxed text-[11px]">
          Published Chicago CTA ridership archive concludes on <strong>{forecastData?.latest_historical_date || 'August 31, 2026'}</strong>. Multi-step inference begins dynamically from the current date (<strong>{forecastData?.forecast_start || 'Upcoming'}</strong>). 
          Prediction intervals are calibrated on the chronological 2025 validation partition (Val RMSE = 96,527 rides, 95.34% empirical coverage), scaled recursively across horizon <em>h</em> (±1.96 × Val_RMSE × √(1 + 0.04(h - 1))).
        </p>
      </div>

      {/* Control Filters */}
      <div className="p-5 rounded-2xl bg-slate-900/80 border border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        {/* Scope Selector */}
        <div className="flex items-center gap-3">
          <label className="text-xs font-semibold uppercase tracking-wider text-slate-400">Forecast Target:</label>
          <select
            value={selectedScope}
            onChange={(e) => setSelectedScope(e.target.value)}
            className="bg-slate-800 border border-slate-700 text-white text-xs font-semibold rounded-xl px-3.5 py-2 focus:outline-none focus:border-purple-500"
          >
            {ROUTE_OPTIONS.map((opt) => (
              <option key={opt.id} value={opt.id}>{opt.name}</option>
            ))}
          </select>
        </div>

        {/* Horizon Selector */}
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-400 uppercase font-semibold">Horizon:</span>
          {[7, 14, 28].map((h) => (
            <button
              key={h}
              onClick={() => setHorizonDays(h)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
                horizonDays === h
                  ? 'bg-purple-600 text-white shadow-md'
                  : 'bg-slate-800 text-slate-400 hover:text-white'
              }`}
            >
              {h} Days
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <LoadingSpinner message="Calculating multi-horizon demand inference..." />
      ) : (
        <>
          {/* Main Chart Area */}
          <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div>
                <h3 className="text-base font-bold text-white">
                  {selectedScope === 'SYSTEM' ? 'CTA System Passenger Volume Projection' : `Corridor ${selectedScope} Daily Projection`}
                </h3>
                <p className="text-xs text-slate-400">Point forecast with 95% predictive confidence intervals</p>
              </div>

              <div className="flex items-center gap-4 text-xs font-mono">
                <span className="flex items-center gap-1.5 text-purple-400">
                  <span className="w-3 h-1 bg-purple-400 rounded"></span> Predicted Rides
                </span>
                <span className="flex items-center gap-1.5 text-purple-600/40">
                  <span className="w-3 h-2 bg-purple-500/20 rounded"></span> 95% Confidence Band
                </span>
              </div>
            </div>

            <div className="h-72 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData} margin={{ top: 10, right: 10, left: 10, bottom: 0 }}>
                  <defs>
                    <linearGradient id="bandGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#a855f7" stopOpacity={0.25}/>
                      <stop offset="95%" stopColor="#a855f7" stopOpacity={0.02}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.5} />
                  <XAxis dataKey="date" stroke="#94a3b8" fontSize={11} tickLine={false} />
                  <YAxis 
                    stroke="#94a3b8" 
                    fontSize={11} 
                    tickFormatter={(val) => `${(val / 1000).toFixed(0)}k`} 
                    domain={['dataMin - 15000', 'dataMax + 15000']} 
                    tickLine={false}
                  />
                  <Tooltip 
                    contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '0.5rem', color: '#fff', fontSize: '12px' }}
                    formatter={(val, name) => [Number(val).toLocaleString() + ' rides', name === 'demand' ? 'Forecast' : 'Bound']}
                  />
                  <Area type="monotone" dataKey="upper" stroke="none" fill="url(#bandGrad)" name="Upper 95% CI" />
                  <Area type="monotone" dataKey="demand" stroke="#c084fc" strokeWidth={2.5} fill="none" name="Predicted Demand" />
                  <Area type="monotone" dataKey="lower" stroke="none" fill="none" name="Lower 95% CI" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Forecast Days Table */}
          <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-4">
            <h3 className="text-sm font-bold uppercase tracking-wider text-slate-400">
              Daily Projected Schedule & Crowd Level Classification
            </h3>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-800/60 text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-700">
                  <tr>
                    <th className="px-4 py-3">Date</th>
                    <th className="px-4 py-3">Day of Week</th>
                    <th className="px-4 py-3">Service Type</th>
                    <th className="px-4 py-3 text-right">Predicted Demand</th>
                    <th className="px-4 py-3 text-right">Calibrated 95% Pred. Interval</th>
                    <th className="px-4 py-3 text-center">Daily Demand Intensity</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800">
                  {daysList.map((day, idx) => {
                    const demandVal = day.predicted_total_demand || day.predicted_rides;
                    const lowerVal = day.lower_ci_95 || day.lower_bound;
                    const upperVal = day.upper_ci_95 || day.upper_bound;
                    return (
                      <tr key={idx} className="hover:bg-slate-800/40 transition">
                        <td className="px-4 py-3 font-mono font-medium text-white">{day.date}</td>
                        <td className="px-4 py-3 text-slate-300 font-semibold">{day.day_of_week}</td>
                        <td className="px-4 py-3">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-medium ${
                            day.is_weekend ? 'bg-amber-500/10 text-amber-300' : 'bg-sky-500/10 text-sky-300'
                          }`}>
                            {day.is_weekend ? 'Weekend' : 'Weekday'}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-right font-mono font-bold text-sky-400 text-sm">
                          {demandVal ? demandVal.toLocaleString() : 'N/A'}
                        </td>
                        <td className="px-4 py-3 text-right font-mono text-slate-400 text-[11px]">
                          [{lowerVal?.toLocaleString()} – {upperVal?.toLocaleString()}]
                        </td>
                        <td className="px-4 py-3 text-center">
                          <CrowdBadge tier={day.crowd_classification} />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Model Benchmarking Table */}
          {metrics && (
            <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-bold uppercase tracking-wider text-slate-400">
                    Model Evaluation Benchmark (Unseen 2026 Test Set)
                  </h3>
                  <p className="text-xs text-slate-500">Evaluated on 243 out-of-sample days (Jan 1 – Aug 31, 2026)</p>
                </div>
                <div className="text-xs text-purple-400 font-medium px-2.5 py-1 rounded-lg bg-purple-500/10 border border-purple-500/30">
                  Best Model: <strong>Random Forest</strong>
                </div>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-800/60 text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-700">
                    <tr>
                      <th className="px-4 py-3">Model Architecture</th>
                      <th className="px-4 py-3 text-right">MAE (Mean Absolute Error)</th>
                      <th className="px-4 py-3 text-right">RMSE</th>
                      <th className="px-4 py-3 text-right">MAPE (%)</th>
                      <th className="px-4 py-3 text-right">R² Score</th>
                      <th className="px-4 py-3 text-center">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800">
                    {Object.entries(metrics.models || {}).map(([name, m]) => {
                      const isBest = name === metrics.best_model;
                      return (
                        <tr key={name} className={`hover:bg-slate-800/40 transition ${isBest ? 'bg-purple-950/20' : ''}`}>
                          <td className="px-4 py-3 font-semibold text-white flex items-center gap-2">
                            {isBest && <CheckCircle2 className="w-4 h-4 text-purple-400" />}
                            {name.replace('_', ' ')}
                          </td>
                          <td className="px-4 py-3 text-right font-mono text-slate-300">
                            ±{m.mae?.toLocaleString()} rides
                          </td>
                          <td className="px-4 py-3 text-right font-mono text-slate-400">
                            {m.rmse?.toLocaleString()}
                          </td>
                          <td className={`px-4 py-3 text-right font-mono font-bold ${isBest ? 'text-purple-400 text-sm' : 'text-slate-300'}`}>
                            {m.mape?.toFixed(2)}%
                          </td>
                          <td className="px-4 py-3 text-right font-mono text-slate-300">
                            {m.r2?.toFixed(2)}
                          </td>
                          <td className="px-4 py-3 text-center">
                            {isBest ? (
                              <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-purple-500/20 text-purple-300 border border-purple-500/40">
                                DEPLOYED BEST
                              </span>
                            ) : (
                              <span className="text-[10px] text-slate-500">Benchmark</span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

