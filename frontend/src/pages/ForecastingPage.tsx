import { useEffect, useState } from "react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { apiClient } from "../api/client";
import {
  Badge,
  EmptyState,
  ErrorState,
  LoadingState,
  MethodNote,
  PaginationBar,
  SectionCard,
  formatNum,
} from "../components/ui";
import type { HistoricalForecastResponse, HistoricalForecastSummaryResponse } from "../types/api";

export function ForecastingPage() {
  const [tier, setTier] = useState<"tier1" | "tier2">("tier1");
  const [period, setPeriod] = useState<"validation" | "test" | "august_holdout">("august_holdout");
  const [routeId, setRouteId] = useState<string>("79");
  const [startDate, setStartDate] = useState<string>("");
  const [endDate, setEndDate] = useState<string>("");
  const [offset, setOffset] = useState<number>(0);

  const [summary, setSummary] = useState<HistoricalForecastSummaryResponse | null>(null);
  const [forecast, setForecast] = useState<HistoricalForecastResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Never expose unsupported Tier 2 August holdout
  const handleTierChange = (nextTier: "tier1" | "tier2") => {
    setTier(nextTier);
    if (nextTier === "tier2" && period === "august_holdout") {
      setPeriod("test");
    }
    setOffset(0);
  };

  useEffect(() => {
    const controller = new AbortController();
    apiClient
      .getHistoricalForecastSummary(undefined, controller.signal)
      .then(setSummary)
      .catch(() => {});
    return () => controller.abort();
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);

    apiClient
      .getHistoricalForecast(
        {
          tier,
          period,
          route_id: routeId.trim() || undefined,
          start_date: startDate || undefined,
          end_date: endDate || undefined,
          limit: 50,
          offset,
        },
        controller.signal
      )
      .then(setForecast)
      .catch((err: unknown) => {
        if (err instanceof DOMException && err.name === "AbortError") return;
        setError(err instanceof Error ? err.message : "Failed to load historical evaluation predictions.");
      })
      .finally(() => setLoading(false));

    return () => controller.abort();
  }, [tier, period, routeId, startDate, endDate, offset]);

  const chartData =
    forecast?.data.map((d) => ({
      label: `${d.date} (${d.route_id})`,
      actual: d.actual_rides,
      predicted: d.predicted_rides !== null ? Number(d.predicted_rides.toFixed(1)) : null,
    })) ?? [];

  return (
    <div className="space-y-6">
      <MethodNote title="Historical Evaluation Results Only — Future Forecasting Supported: No" tone="warning">
        These predictions are verified historical Random Forest evaluation outputs (through 2026-08-31) using observed
        autoregressive lag features. <strong>Future forecasting supported: No.</strong> Tier 2 does not have an August
        holdout partition.
      </MethodNote>

      {summary && (
        <SectionCard
          title="Aggregate Historical Evaluation Metrics"
          subtitle={`Scope: ${summary.forecast_scope} • Future forecasting supported: ${summary.future_forecasting_supported ? "Yes" : "No"}`}
        >
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-slate-800 text-slate-400">
                <tr>
                  <th className="py-2 pr-3">Tier / Period</th>
                  <th className="py-2 pr-3">Window</th>
                  <th className="py-2 pr-3 text-right">Rows Evaluated</th>
                  <th className="py-2 pr-3 text-right">Total Records</th>
                  <th className="py-2 pr-3 text-right">WAPE (%)</th>
                  <th className="py-2 pr-3 text-right">MAE</th>
                  <th className="py-2 pr-3 text-right">RMSE</th>
                  <th className="py-2 text-right">R²</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/70">
                {summary.summaries.map((s) => (
                  <tr key={`${s.tier}-${s.period}`} className="hover:bg-slate-800/40">
                    <td className="py-2 pr-3 font-semibold text-sky-300">
                      {s.tier} / {s.period}
                    </td>
                    <td className="py-2 pr-3 font-mono text-slate-300">
                      {s.evaluation_start} → {s.evaluation_end}
                    </td>
                    <td className="py-2 pr-3 text-right text-slate-200">{s.rows_evaluated.toLocaleString("en-US")}</td>
                    <td className="py-2 pr-3 text-right text-slate-400">
                      {s.total_prediction_records.toLocaleString("en-US")}
                    </td>
                    <td className="py-2 pr-3 text-right font-mono text-emerald-300">{formatNum(s.wape, 2)}%</td>
                    <td className="py-2 pr-3 text-right font-mono text-slate-200">{formatNum(s.mae, 2)}</td>
                    <td className="py-2 pr-3 text-right font-mono text-slate-200">{formatNum(s.rmse, 2)}</td>
                    <td className="py-2 text-right font-mono text-violet-300">{formatNum(s.r2, 4)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </SectionCard>
      )}

      <SectionCard
        title="Historical Prediction Explorer"
        subtitle="Compare tuned Random Forest evaluation predictions against actual CTA ridership"
      >
        <div className="mb-5 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <div>
            <label htmlFor="fc-tier" className="mb-1 block text-xs text-slate-400">
              Model Tier
            </label>
            <select
              id="fc-tier"
              value={tier}
              onChange={(e) => handleTierChange(e.target.value as "tier1" | "tier2")}
              className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs text-slate-100"
            >
              <option value="tier1">Tier 1 (Macro 2022–2026)</option>
              <option value="tier2">Tier 2 (GTFS Era)</option>
            </select>
          </div>

          <div>
            <label htmlFor="fc-period" className="mb-1 block text-xs text-slate-400">
              Evaluation Period
            </label>
            <select
              id="fc-period"
              value={period}
              onChange={(e) => {
                setPeriod(e.target.value as "validation" | "test" | "august_holdout");
                setOffset(0);
              }}
              className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs text-slate-100"
            >
              <option value="validation">Validation</option>
              <option value="test">Test</option>
              {tier === "tier1" && <option value="august_holdout">August Holdout (Tier 1 only)</option>}
            </select>
          </div>

          <div>
            <label htmlFor="fc-route" className="mb-1 block text-xs text-slate-400">
              Route Filter (optional)
            </label>
            <input
              id="fc-route"
              type="text"
              value={routeId}
              onChange={(e) => {
                setRouteId(e.target.value);
                setOffset(0);
              }}
              placeholder="e.g. 79 (blank = all)"
              className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs text-slate-100"
            />
          </div>

          <div>
            <label htmlFor="fc-start" className="mb-1 block text-xs text-slate-400">
              Start Date
            </label>
            <input
              id="fc-start"
              type="date"
              value={startDate}
              onChange={(e) => {
                setStartDate(e.target.value);
                setOffset(0);
              }}
              className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs text-slate-100"
            />
          </div>

          <div>
            <label htmlFor="fc-end" className="mb-1 block text-xs text-slate-400">
              End Date
            </label>
            <input
              id="fc-end"
              type="date"
              value={endDate}
              onChange={(e) => {
                setEndDate(e.target.value);
                setOffset(0);
              }}
              className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs text-slate-100"
            />
          </div>
        </div>

        {loading ? (
          <LoadingState label="Loading historical predictions..." />
        ) : error ? (
          <ErrorState message={error} />
        ) : !forecast || forecast.data.length === 0 ? (
          <EmptyState />
        ) : (
          <div className="space-y-5">
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <Badge variant="amber">Scope: {forecast.forecast_scope}</Badge>
              <Badge variant="rose">
                Future forecasting supported: {forecast.future_forecasting_supported ? "Yes" : "No"}
              </Badge>
              <Badge variant="slate">{forecast.model_identifier}</Badge>
            </div>

            <div className="h-72 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData} margin={{ top: 8, right: 16, left: 10, bottom: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis dataKey="label" stroke="#94a3b8" fontSize={10} />
                  <YAxis stroke="#94a3b8" fontSize={12} />
                  <Tooltip
                    contentStyle={{ backgroundColor: "#0f172a", borderColor: "#334155", color: "#f8fafc" }}
                  />
                  <Legend />
                  <Line type="monotone" dataKey="actual" name="Actual Rides" stroke="#34d399" strokeWidth={2} dot={false} />
                  <Line
                    type="monotone"
                    dataKey="predicted"
                    name="RF Historical Prediction"
                    stroke="#38bdf8"
                    strokeWidth={2}
                    dot={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>

            <div className="max-h-72 overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="border-b border-slate-800 text-slate-400">
                  <tr>
                    <th className="py-2 pr-3">Date</th>
                    <th className="py-2 pr-3">Route</th>
                    <th className="py-2 pr-3 text-right">Actual</th>
                    <th className="py-2 pr-3 text-right">Predicted</th>
                    <th className="py-2 pr-3 text-right">Abs Error</th>
                    <th className="py-2 pr-3 text-right">% Error</th>
                    <th className="py-2">Baseline B Strategy</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/70">
                  {forecast.data.map((row) => (
                    <tr key={`${row.date}-${row.route_id}`} className="hover:bg-slate-800/40">
                      <td className="py-2 pr-3 font-mono text-slate-200">{row.date}</td>
                      <td className="py-2 pr-3 font-semibold text-sky-300">{row.route_id}</td>
                      <td className="py-2 pr-3 text-right text-slate-100">{formatNum(row.actual_rides, 0)}</td>
                      <td className="py-2 pr-3 text-right text-sky-300">{formatNum(row.predicted_rides, 2)}</td>
                      <td className="py-2 pr-3 text-right text-amber-300">{formatNum(row.absolute_error, 2)}</td>
                      <td className="py-2 pr-3 text-right text-slate-300">
                        {row.percentage_error !== null ? `${formatNum(row.percentage_error, 2)}%` : "N/A"}
                      </td>
                      <td className="py-2">
                        {row.baseline_b_strategy ? (
                          <Badge variant={row.fallback_baseline_b ? "amber" : "emerald"}>
                            {row.baseline_b_strategy}
                          </Badge>
                        ) : (
                          <span className="text-slate-500">—</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <PaginationBar pagination={forecast.pagination} onPageChange={setOffset} />
          </div>
        )}
      </SectionCard>
    </div>
  );
}
