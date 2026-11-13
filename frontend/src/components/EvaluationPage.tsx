import React, { useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { EvaluationData, fmtInt, fmtNum, fmtPct } from "../api";
import { PageHeader } from "./PageHeader";

interface EvaluationPageProps {
  evaluation: EvaluationData;
  onSelectRoute: (route: string) => void;
}

export const EvaluationPage: React.FC<EvaluationPageProps> = ({
  evaluation,
  onSelectRoute,
}) => {
  const [stage, setStage] = useState<"test" | "validation" | "october">("test");
  const [testSubset, setTestSubset] = useState<string>("With M35 Surge Hours");

  const filteredTestWeeks = useMemo(
    () =>
      evaluation.test.forecast_by_week.filter(
        (r) => String(r.evaluation_subset) === testSubset
      ),
    [evaluation.test.forecast_by_week, testSubset]
  );

  const filteredTestRoutes = useMemo(
    () =>
      evaluation.test.forecast_by_route.filter(
        (r) => String(r.evaluation_subset) === testSubset
      ),
    [evaluation.test.forecast_by_route, testSubset]
  );

  return (
    <div className="space-y-6">
      <PageHeader
        title="Model Evaluation: Validation, Single Logged Test & October Unseen Check"
        subtitle="Honest evaluation across chronological splits: Validation (Jun–Jul 2026) for model selection, Single Official Test Run (Aug–Sep 2026), and Unseen October Operational Check (Oct 18–31, 2026)."
        period={evaluation.period}
        source={evaluation.source}
        rightSlot={
          <div className="flex flex-wrap gap-1.5">
            {[
              { id: "test", label: "Test Set (Aug–Sep)" },
              { id: "validation", label: "Validation (Jun–Jul)" },
              { id: "october", label: "October Check (Oct 18–31)" },
            ].map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() => setStage(t.id as "test" | "validation" | "october")}
                className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
                  stage === t.id
                    ? "bg-blue-600 text-white"
                    : "bg-slate-100 text-slate-700 hover:bg-slate-200"
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>
        }
      />

      {/* Explicit October Limitation Banner (Always visible for transparency) */}
      <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-xs text-rose-950">
        <div className="font-semibold">
          October Operational Limitation (Post-Test Unseen Data: Oct 18–31, 2026)
        </div>
        <p className="mt-1 font-medium">{evaluation.october.headline}</p>
        <ul className="mt-1 list-disc space-y-0.5 pl-4 text-rose-900">
          {evaluation.october.limitations.map((lim, i) => (
            <li key={i}>{lim}</li>
          ))}
        </ul>
      </div>

      {/* Stage 1: Official Logged Test Set */}
      {stage === "test" ? (
        <div className="space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-slate-200 bg-white px-4 py-3 text-xs">
            <div>
              <span className="font-semibold text-slate-900">
                Single Logged Test Run ({evaluation.official_test_runs_logged} entry):
              </span>{" "}
              <span className="font-mono text-slate-600">
                {evaluation.official_test_log[0] ?? "not available"}
              </span>
            </div>
            <div className="flex gap-1.5">
              {["With M35 Surge Hours", "Without M35 Surge Hours"].map((sub) => (
                <button
                  key={sub}
                  type="button"
                  onClick={() => setTestSubset(sub)}
                  className={`rounded-md px-2.5 py-1 text-xs font-medium ${
                    testSubset === sub
                      ? "bg-slate-900 text-white"
                      : "bg-slate-100 text-slate-700"
                  }`}
                >
                  {sub}
                </button>
              ))}
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <h2 className="mb-3 text-sm font-semibold text-slate-900">
              Test Set Forecasting Overall (Aug–Sep 2026)
            </h2>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="border-b border-slate-200 text-slate-500">
                  <tr>
                    <th className="py-2 pr-3 font-medium">Subset</th>
                    <th className="py-2 pr-3 font-medium">Model</th>
                    <th className="py-2 pr-3 text-right font-medium">Common N</th>
                    <th className="py-2 pr-3 text-right font-medium">MAE</th>
                    <th className="py-2 pr-3 text-right font-medium">RMSE</th>
                    <th className="py-2 pr-3 text-right font-medium">WAPE %</th>
                    <th className="py-2 pr-3 text-right font-medium">Bias (Pred-Act)</th>
                    <th className="py-2 text-right font-medium">vs 4-Wk Avg</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {evaluation.test.forecast_overall.map((r, i) => (
                    <tr key={i}>
                      <td className="py-2 pr-3 text-slate-600">{String(r.evaluation_subset)}</td>
                      <td className="py-2 pr-3 font-medium text-slate-900">{String(r.model_name)}</td>
                      <td className="py-2 pr-3 text-right font-mono">{fmtInt(r.n_eval_common as number)}</td>
                      <td className="py-2 pr-3 text-right font-mono">{fmtNum(r.mae_common as number, 2)}</td>
                      <td className="py-2 pr-3 text-right font-mono">{fmtNum(r.rmse_common as number, 2)}</td>
                      <td className="py-2 pr-3 text-right font-mono font-bold">{fmtPct(r.wape_common_pct as number, 2)}</td>
                      <td className="py-2 pr-3 text-right font-mono">{fmtNum(r.bias_common_pred_minus_actual as number, 2)}</td>
                      <td className="py-2 text-right font-mono">{fmtNum(r.wape_diff_vs_4wk_pct_pts as number, 2)} pts</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <h3 className="mb-3 text-sm font-semibold text-slate-900">
                Weekly Test WAPE ({testSubset})
              </h3>
              <div className="h-64 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={filteredTestWeeks}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis dataKey="week_start" tick={{ fontSize: 10 }} />
                    <YAxis tick={{ fontSize: 11 }} unit="%" />
                    <Tooltip formatter={(val: unknown) => fmtPct(val as number | null, 2)} />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    <Line
                      type="monotone"
                      dataKey="wape_hgb_pct"
                      name="HGB (Retrained Jan–Jul)"
                      stroke="#1d4ed8"
                      strokeWidth={2.2}
                    />
                    <Line
                      type="monotone"
                      dataKey="wape_4wk_pct"
                      name="4-Week Avg Baseline"
                      stroke="#d97706"
                      strokeWidth={2}
                      strokeDasharray="4 4"
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <h3 className="mb-3 text-sm font-semibold text-slate-900">
                Test High-Riders-per-Trip Classification
              </h3>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="border-b border-slate-200 text-slate-500">
                    <tr>
                      <th className="py-2 pr-2 font-medium">Subset / Model</th>
                      <th className="py-2 pr-2 text-right font-medium">PR-AUC</th>
                      <th className="py-2 pr-2 text-right font-medium">Prec @ Rule B Load</th>
                      <th className="py-2 pr-2 text-right font-medium">Precision</th>
                      <th className="py-2 pr-2 text-right font-medium">Recall</th>
                      <th className="py-2 text-right font-medium">F1</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {evaluation.test.classification_overall.map((r, i) => (
                      <tr key={i}>
                        <td className="py-2 pr-2">
                          <div className="font-medium text-slate-900">{String(r.model_name)}</div>
                          <div className="text-[10px] text-slate-500">{String(r.evaluation_subset)}</div>
                        </td>
                        <td className="py-2 pr-2 text-right font-mono">{fmtNum(r.pr_auc_common as number, 4)}</td>
                        <td className="py-2 pr-2 text-right font-mono">{fmtNum(r.precision_at_rule_b_workload as number, 4)}</td>
                        <td className="py-2 pr-2 text-right font-mono">{fmtNum(r.precision_at_fixed_cutoff as number, 4)}</td>
                        <td className="py-2 pr-2 text-right font-mono">{fmtNum(r.recall_at_fixed_cutoff as number, 4)}</td>
                        <td className="py-2 text-right font-mono font-semibold">{fmtNum(r.f1_at_fixed_cutoff as number, 4)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <h3 className="mb-3 text-sm font-semibold text-slate-900">
              Per-Route Test Forecast Results ({testSubset}) — Click Route for Detail
            </h3>
            <div className="max-h-80 overflow-y-auto">
              <table className="w-full text-left text-xs">
                <thead className="sticky top-0 bg-white border-b border-slate-200 text-slate-500">
                  <tr>
                    <th className="py-2 pr-3 font-medium">Route</th>
                    <th className="py-2 pr-3 text-right font-medium">Hours</th>
                    <th className="py-2 pr-3 text-right font-medium">Actual Riders</th>
                    <th className="py-2 pr-3 text-right font-medium">HGB WAPE</th>
                    <th className="py-2 pr-3 text-right font-medium">4-Wk WAPE</th>
                    <th className="py-2 pr-3 text-right font-medium">Diff (pts)</th>
                    <th className="py-2 text-right font-medium">HGB Bias</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {filteredTestRoutes.map((r) => (
                    <tr key={String(r.route)} className="hover:bg-slate-50">
                      <td className="py-1.5 pr-3">
                        <button
                          type="button"
                          onClick={() => onSelectRoute(String(r.route))}
                          className="font-semibold text-blue-700 hover:underline"
                        >
                          {String(r.route)}
                        </button>
                      </td>
                      <td className="py-1.5 pr-3 text-right font-mono">{fmtInt(r.n_eval as number)}</td>
                      <td className="py-1.5 pr-3 text-right font-mono">{fmtInt(r.total_actual as number)}</td>
                      <td className="py-1.5 pr-3 text-right font-mono font-semibold">{fmtPct(r.wape_hgb_pct as number, 2)}</td>
                      <td className="py-1.5 pr-3 text-right font-mono">{fmtPct(r.wape_4wk_pct as number, 2)}</td>
                      <td
                        className={`py-1.5 pr-3 text-right font-mono ${
                          Number(r.wape_diff_hgb_minus_4wk) < 0 ? "text-emerald-700" : "text-rose-700"
                        }`}
                      >
                        {fmtNum(r.wape_diff_hgb_minus_4wk as number, 2)}
                      </td>
                      <td className="py-1.5 text-right font-mono">{fmtNum(r.bias_hgb_pred_minus_actual as number, 2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      ) : null}

      {/* Stage 2: Validation (Jun–Jul) */}
      {stage === "validation" ? (
        <div className="space-y-6">
          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <h2 className="mb-3 text-sm font-semibold text-slate-900">
              Validation Forecasting Model Comparison ({evaluation.validation.period})
            </h2>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="border-b border-slate-200 text-slate-500">
                  <tr>
                    <th className="py-2 pr-3 font-medium">Model</th>
                    <th className="py-2 pr-3 font-medium">Type</th>
                    <th className="py-2 pr-3 text-right font-medium">MAE</th>
                    <th className="py-2 pr-3 text-right font-medium">RMSE</th>
                    <th className="py-2 pr-3 text-right font-medium">WAPE (53,585)</th>
                    <th className="py-2 pr-3 text-right font-medium">Bias</th>
                    <th className="py-2 font-medium">Best Setting</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {evaluation.validation.forecast_comparison.map((r) => (
                    <tr key={String(r.model_name)}>
                      <td className="py-2 pr-3 font-medium text-slate-900">{String(r.model_name)}</td>
                      <td className="py-2 pr-3 text-slate-600">{String(r.model_type)}</td>
                      <td className="py-2 pr-3 text-right font-mono">{fmtNum(r.mae_53585 as number, 2)}</td>
                      <td className="py-2 pr-3 text-right font-mono">{fmtNum(r.rmse_53585 as number, 2)}</td>
                      <td className="py-2 pr-3 text-right font-mono font-bold">{fmtPct(r.wape_53585_pct as number, 2)}</td>
                      <td className="py-2 pr-3 text-right font-mono">{fmtNum(r.bias_53585_pred_minus_actual as number, 2)}</td>
                      <td className="py-2 text-slate-600">{String(r.best_setting)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <h3 className="mb-3 text-sm font-semibold text-slate-900">
                Validation Weekly WAPE (8 Wins, 1 Tie)
              </h3>
              <div className="h-64 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={evaluation.validation.forecast_weekly}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis dataKey="week_start" tick={{ fontSize: 10 }} />
                    <YAxis tick={{ fontSize: 11 }} unit="%" />
                    <Tooltip formatter={(val: unknown) => fmtPct(val as number | null, 2)} />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    <Bar dataKey="wape_hgb" name="HGB WAPE %" fill="#1d4ed8" />
                    <Bar dataKey="wape_4wk" name="4-Wk Avg WAPE %" fill="#d97706" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <h3 className="mb-3 text-sm font-semibold text-slate-900">
                Validation Fair Classification Comparison (at Rule B Workload)
              </h3>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="border-b border-slate-200 text-slate-500">
                    <tr>
                      <th className="py-2 pr-2 font-medium">Model</th>
                      <th className="py-2 pr-2 text-right font-medium">PR-AUC</th>
                      <th className="py-2 pr-2 text-right font-medium">Prec @ 13,081</th>
                      <th className="py-2 text-right font-medium">Max-F1 Flagged</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {evaluation.validation.classification_comparison.map((r) => (
                      <tr key={String(r.model_name)}>
                        <td className="py-2 pr-2 font-medium text-slate-900">{String(r.model_name)}</td>
                        <td className="py-2 pr-2 text-right font-mono">{fmtNum(r.pr_auc_53406 as number, 4)}</td>
                        <td className="py-2 pr-2 text-right font-mono">{fmtNum(r.precision_at_13081_hours as number, 4)}</td>
                        <td className="py-2 text-right font-mono">{fmtInt(r.pred_pos_at_max_f1 as number)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      ) : null}

      {/* Stage 3: October Unseen Operational Check */}
      {stage === "october" ? (
        <div className="space-y-6">
          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <h2 className="mb-3 text-sm font-semibold text-slate-900">
              October Operational Forecast Summary ({evaluation.october.period})
            </h2>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="border-b border-slate-200 text-slate-500">
                  <tr>
                    <th className="py-2 pr-3 font-medium">Lag Setup</th>
                    <th className="py-2 pr-3 font-medium">Model</th>
                    <th className="py-2 pr-3 text-right font-medium">MAE</th>
                    <th className="py-2 pr-3 text-right font-medium">RMSE</th>
                    <th className="py-2 pr-3 text-right font-medium">WAPE (12,270)</th>
                    <th className="py-2 pr-3 text-right font-medium">Bias</th>
                    <th className="py-2 text-right font-medium">Routes Winning</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {evaluation.october.forecast_summary.map((r, i) => (
                    <tr key={i}>
                      <td className="py-2 pr-3 text-slate-600">{String(r.lag_mode)}</td>
                      <td className="py-2 pr-3 font-medium text-slate-900">{String(r.model)}</td>
                      <td className="py-2 pr-3 text-right font-mono">{fmtNum(r.mae_active as number, 2)}</td>
                      <td className="py-2 pr-3 text-right font-mono">{fmtNum(r.rmse_active as number, 2)}</td>
                      <td className="py-2 pr-3 text-right font-mono font-bold">{fmtPct(r.wape_active_pct as number, 2)}</td>
                      <td className="py-2 pr-3 text-right font-mono">{fmtNum(r.bias_active_pred_minus_actual as number, 2)}</td>
                      <td className="py-2 text-right font-mono">
                        {r.routes_beating_4wk_of_41 === null
                          ? "not available"
                          : `${fmtInt(r.routes_beating_4wk_of_41 as number)} / 41`}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <h3 className="mb-3 text-sm font-semibold text-slate-900">
                October Daily WAPE (Publish-Date Lag Cutoff)
              </h3>
              <div className="h-64 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={evaluation.october.forecast_by_day}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis dataKey="date" tick={{ fontSize: 10 }} />
                    <YAxis tick={{ fontSize: 11 }} unit="%" />
                    <Tooltip formatter={(val: unknown) => fmtPct(val as number | null, 2)} />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    <Line
                      type="monotone"
                      dataKey="wape_frozen_cutoff_pct"
                      name="Frozen HGB (Cut)"
                      stroke="#1d4ed8"
                      strokeWidth={2}
                    />
                    <Line
                      type="monotone"
                      dataKey="wape_4wk_cutoff_pct"
                      name="4-Wk Avg (Cut)"
                      stroke="#d97706"
                      strokeWidth={2}
                      strokeDasharray="4 4"
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <h3 className="mb-3 text-sm font-semibold text-slate-900">
                October Diagnostic & Pipeline Checks
              </h3>
              <div className="space-y-2 text-xs">
                {evaluation.october.diagnostic_checks.map((c) => (
                  <div key={String(c.check_name)} className="rounded-lg bg-slate-50 p-3">
                    <div className="flex items-center justify-between font-semibold text-slate-900">
                      <span>{String(c.check_name)}</span>
                      <span className="text-emerald-700">{String(c.result)}</span>
                    </div>
                    <p className="mt-1 text-slate-600">{String(c.details)}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
};

