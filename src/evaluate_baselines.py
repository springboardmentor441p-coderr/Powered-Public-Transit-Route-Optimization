"""
Milestone 2: Step 14 — Baseline Forecasts

Evaluates two simple heuristic baseline forecasts on the validation set (2026-06-01 to 2026-07-31):
1. Same hour last week: ridership 7 days earlier (lag_7d)
2. 4-week average: average of the 7, 14, 21, and 28-day lags (lag_mean_available)

Reports three error measures:
- MAE: Mean Absolute Error (in riders)
- RMSE: Root Mean Squared Error (in riders)
- WAPE: Weighted Absolute Percentage Error (sum(|y - y_hat|) / sum(y) * 100%)

Saves summary tables overall and per route to reports/tables/.
"""

from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
VAL_PATH = ROOT / "data" / "processed" / "val_features.parquet"
TAB_DIR = ROOT / "reports" / "tables"


def compute_metrics(y_true: pd.Series, y_pred: pd.Series) -> dict:
    """Calculate MAE, RMSE, and WAPE."""
    mask = y_true.notnull() & y_pred.notnull()
    y = y_true[mask].values
    y_hat = y_pred[mask].values

    if len(y) == 0:
        return {"n_eval": 0, "mae": np.nan, "rmse": np.nan, "wape_pct": np.nan}

    err = np.abs(y - y_hat)
    mae = float(np.mean(err))
    rmse = float(np.sqrt(np.mean((y - y_hat) ** 2)))
    sum_y = float(np.sum(y))
    wape = float((np.sum(err) / sum_y) * 100.0) if sum_y > 0 else np.nan

    return {
        "n_eval": int(len(y)),
        "mae": round(mae, 2),
        "rmse": round(rmse, 2),
        "wape_pct": round(wape, 2),
    }


def evaluate_baselines():
    print(f"Loading validation dataset: {VAL_PATH.relative_to(ROOT)}...")
    val_df = pd.read_parquet(VAL_PATH)
    print(f"Validation rows: {len(val_df):,}, dates: {val_df['date'].min()} to {val_df['date'].max()} (41 routes)")

    common_mask = (
        val_df["ridership"].notnull()
        & val_df["lag_7d"].notnull()
        & val_df["lag_mean_available"].notnull()
    )
    val_eval = val_df[common_mask].copy()
    print(f"Fair comparison evaluation rows (both baselines non-null): {len(val_eval):,} / {len(val_df):,} ({len(val_eval)/len(val_df)*100:.2f}%)")

    y_true = val_eval["ridership"]
    y_pred_lag7 = val_eval["lag_7d"]
    y_pred_4wk = val_eval["lag_mean_available"]

    # 1. Overall evaluation
    m_lag7 = compute_metrics(y_true, y_pred_lag7)
    m_4wk = compute_metrics(y_true, y_pred_4wk)

    overall_records = [
        {
            "model_name": "Same hour last week (lag_7d)",
            "evaluated_rows": m_lag7["n_eval"],
            "coverage_pct": round(m_lag7["n_eval"] / len(val_df) * 100, 2),
            "mae": m_lag7["mae"],
            "rmse": m_lag7["rmse"],
            "wape_pct": m_lag7["wape_pct"],
        },
        {
            "model_name": "4-week average (lag_mean_available)",
            "evaluated_rows": m_4wk["n_eval"],
            "coverage_pct": round(m_4wk["n_eval"] / len(val_df) * 100, 2),
            "mae": m_4wk["mae"],
            "rmse": m_4wk["rmse"],
            "wape_pct": m_4wk["wape_pct"],
        },
    ]

    overall_df = pd.DataFrame(overall_records)
    overall_csv = TAB_DIR / "m2_baseline_forecast_overall.csv"
    overall_df.to_csv(overall_csv, index=False)
    print(f"\nSaved overall metrics: {overall_csv.relative_to(ROOT)}")
    print(overall_df.to_string())

    # 2. Per-route evaluation on the common evaluated rows
    route_records = []
    routes = sorted(val_eval["route"].unique())

    for r in routes:
        r_sub = val_eval[val_eval["route"] == r]
        y_r = r_sub["ridership"]
        p7 = r_sub["lag_7d"]
        p4 = r_sub["lag_mean_available"]

        m7 = compute_metrics(y_r, p7)
        m4 = compute_metrics(y_r, p4)

        route_records.append({
            "route": r,
            "total_riders": int(y_r.sum()),
            "lag7_mae": m7["mae"],
            "lag7_rmse": m7["rmse"],
            "lag7_wape_pct": m7["wape_pct"],
            "avg4wk_mae": m4["mae"],
            "avg4wk_rmse": m4["rmse"],
            "avg4wk_wape_pct": m4["wape_pct"],
            "best_baseline": "4-week average" if m4["wape_pct"] <= m7["wape_pct"] else "Same hour last week",
        })

    route_df = pd.DataFrame(route_records)
    route_csv = TAB_DIR / "m2_baseline_forecast_per_route.csv"
    route_df.to_csv(route_csv, index=False)
    print(f"\nSaved per-route metrics: {route_csv.relative_to(ROOT)} ({len(route_df)} routes)")
    print(route_df.head(10).to_string())


if __name__ == "__main__":
    evaluate_baselines()
