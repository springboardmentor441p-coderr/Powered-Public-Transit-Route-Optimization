"""Model evaluation endpoints covering Validation (Jun-Jul), Test (Aug-Sep), and October (Oct 18-31)."""

from __future__ import annotations

from fastapi import APIRouter, Request

from backend.app.data import clean_records
from backend.app.schemas import EvaluationResponse

router = APIRouter(prefix="/api", tags=["evaluation"])


@router.get("/evaluation", response_model=EvaluationResponse)
def get_evaluation(request: Request) -> EvaluationResponse:
    store = request.app.state.store
    oct_df = store.october_forecast_summary
    cutoff_rows = oct_df[oct_df["lag_mode"].astype(str).str.contains("Publish-Date Cutoff", na=False)]
    base_row = cutoff_rows[cutoff_rows["model"].astype(str).str.contains("4-Week Average", na=False)].iloc[0]
    frozen_row = cutoff_rows[cutoff_rows["model"].astype(str).str.contains("Frozen Step 5", na=False)].iloc[0]
    prod_row = cutoff_rows[cutoff_rows["model"].astype(str).str.contains("Production", na=False)].iloc[0]

    n_oct_active = int(base_row["n_active_eval"])
    base_wape = float(base_row["wape_active_pct"])
    frozen_wape = float(frozen_row["wape_active_pct"])
    prod_wape = float(prod_row["wape_active_pct"])
    frozen_bias = float(frozen_row["bias_active_pred_minus_actual"])
    frozen_wins = int(frozen_row["routes_beating_4wk_of_41"])

    return EvaluationResponse(
        period="Validation: Jun–Jul 2026 | Test (single logged run): Aug–Sep 2026 | Operational Check: Oct 18–31, 2026",
        source="app_data/validation_*.csv, test_*.csv & october_*.csv (matching Milestone 3 report tables)",
        validation={
            "period": "2026-06-01 to 2026-07-31 (54,046 rows / 53,585 common lag rows)",
            "forecast_comparison": clean_records(store.val_forecast_comparison),
            "forecast_weekly": clean_records(store.val_forecast_weekly),
            "classification_comparison": clean_records(store.val_classification_comparison),
            "notes": [
                "HistGradientBoosting beats the 4-week average on validation (13.03% vs 14.08% WAPE, winning 8 of 9 weeks and tying 1).",
                "At Rule B's exact workload (13,081 flagged hours), HistGradientBoosting Classifier scores 0.6610 precision vs Rule B's 0.6638, whereas Forecast / Trips achieves 0.6801.",
            ],
        },
        test={
            "period": "2026-08-01 to 2026-09-30 (single logged final evaluation; never tuned on or reloaded)",
            "forecast_overall": clean_records(store.test_forecast_overall),
            "forecast_by_week": clean_records(store.test_forecast_by_week),
            "forecast_by_day_type": clean_records(store.test_forecast_by_day_type),
            "forecast_by_time_band": clean_records(store.test_forecast_by_time_band),
            "forecast_by_route": clean_records(store.test_forecast_by_route),
            "classification_overall": clean_records(store.test_classification_overall),
            "notes": [
                "Single final test run logged before October check; models were retrained on Jan–Jul 2026 with validation-selected hyperparameters.",
                "Retrained HistGradientBoosting lowers test WAPE from 15.41% (4-week avg) to 14.06% with M35 surge hours (and 14.04% vs 15.39% without the 6-hr Sep 19 M35 event surge).",
            ],
        },
        october={
            "period": f"2026-10-18 to 2026-10-31 (14 unseen days; {n_oct_active:,} active route-hours; timetable 2026-10-17)",
            "headline": (
                "On unseen October data, the frozen Step 5 model did not beat the 4-week average baseline "
                f"overall under realistic publish-date lags ({frozen_wape:.2f}% vs {base_wape:.2f}% WAPE; "
                f"{frozen_wins} of 41 routes beat baseline)."
            ),
            "forecast_summary": clean_records(store.october_forecast_summary),
            "forecast_by_day": clean_records(store.october_forecast_by_day),
            "forecast_by_route": clean_records(store.october_forecast_by_route),
            "classification_summary": clean_records(store.october_classification_summary),
            "diagnostic_checks": clean_records(store.october_diagnostic_checks),
            "limitations": [
                (
                    f"Post-test retraining on Jan–Sep made October slightly worse ({prod_wape:.2f}% vs {frozen_wape:.2f}% WAPE): "
                    "calendar month is not a model feature, so when autumn ridership shifts above earlier levels "
                    "the model loses its edge while the 4-week average adjusts automatically."
                ),
                (
                    f"Higher October observed ridership (+17.1% vs Jan–Jul) and negative forecast bias ({frozen_bias:.2f} cutoff "
                    "to -16.41 rolling riders/hr) are consistent with each other, though 14 days is a short operational window."
                ),
            ],
        },
        official_test_runs_logged=int(store.version["official_test_runs_logged"]),
        official_test_log=list(store.version["official_test_log"]),
    )

