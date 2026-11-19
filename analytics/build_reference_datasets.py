"""
Step 7: Builds route/day-type productivity rankings, clustering profiles, and exact-date lag feature tables.
Implements Option 2 missing-28d-lag imputation policy and chronological train/validation/test splits.
"""
import os
from datetime import date, timedelta
import numpy as np
import pandas as pd

PROCESSED_DIR = "data/processed"
RANKING_MIN_OBSERVED_DAYS = 20

def run():
    boardings = pd.read_parquet(os.path.join(PROCESSED_DIR, "boardings_clean.parquet"))
    matched = pd.read_parquet(os.path.join(PROCESSED_DIR, "matched_utilization.parquet"))

    # 1. Build Route/Day-Type Profiles & Productivity Rankings (ratio of sums)
    prof = matched.groupby(["route", "daytype"], as_index=False).agg(
        date_min=("date", "min"),
        date_max=("date", "max"),
        observed_dates=("date", "nunique"),
        total_rides=("rides", "sum"),
        mean_daily_rides=("rides", "mean"),
        std_daily_rides=("rides", "std"),
        total_scheduled_trips=("scheduled_trips", "sum"),
        total_scheduled_hours=("scheduled_service_hours", "sum"),
        complete_duration_days=("duration_complete", "sum"),
    )
    prof["rides_per_scheduled_trip"] = prof["total_rides"] / prof["total_scheduled_trips"]
    prof["rides_per_scheduled_hour"] = prof.apply(
        lambda r: (r["total_rides"] / r["total_scheduled_hours"])
        if pd.notna(r["total_scheduled_hours"]) and r["total_scheduled_hours"] > 0
        else None,
        axis=1,
    )
    prof["eligible_for_ranking"] = (prof["observed_dates"] >= RANKING_MIN_OBSERVED_DAYS) & prof["rides_per_scheduled_hour"].notna()
    prof["eligibility_reason"] = prof.apply(
        lambda r: "eligible"
        if r["eligible_for_ranking"]
        else f"insufficient_days ({r['observed_dates']} < {RANKING_MIN_OBSERVED_DAYS})",
        axis=1,
    )

    prof["service_productivity_metric_rank"] = None
    for dt in ["W", "A", "U"]:
        mask = (prof["daytype"] == dt) & prof["eligible_for_ranking"]
        prof.loc[mask, "service_productivity_metric_rank"] = (
            prof.loc[mask, "rides_per_scheduled_hour"].rank(ascending=False, method="min").astype(int)
        )

    prof.to_parquet(os.path.join(PROCESSED_DIR, "productivity_rankings.parquet"), index=False)

    # 2. Build Exact-Date Demand Lag Features
    lookup = boardings.set_index(["route", "date"])["rides"].to_dict()
    feat_rows = []
    min_target_date = boardings["date"].min() + timedelta(days=28)
    target_df = boardings[boardings["date"] >= min_target_date].copy()

    for _, row in target_df.iterrows():
        r = row["route"]
        d = row["date"]
        l1 = lookup.get((r, d - timedelta(days=1)))
        l7 = lookup.get((r, d - timedelta(days=7)))
        l14 = lookup.get((r, d - timedelta(days=14)))
        l21 = lookup.get((r, d - timedelta(days=21)))
        l28 = lookup.get((r, d - timedelta(days=28)))

        seasonal_vals = [v for v in (l7, l14, l21, l28) if v is not None]
        avail_obs = len(seasonal_vals)
        seasonal_mean = float(np.mean(seasonal_vals)) if avail_obs >= 2 else None

        # Option 2 missing-history policy: fill missing 28d lag from available 7/14/21d lags
        l28_avail = 1 if l28 is not None else 0
        l28_filled = l28
        if l28 is None:
            donors = [v for v in (l7, l14, l21) if v is not None]
            if donors:
                l28_filled = float(np.mean(donors))

        feat_rows.append({
            "route": r,
            "date": d,
            "daytype": row["daytype"],
            "rides": int(row["rides"]),
            "day_of_week": d.weekday(),
            "month": d.month,
            "is_weekend": 1 if d.weekday() >= 5 else 0,
            "is_sunday_holiday_daytype": 1 if row["daytype"] == "U" else 0,
            "rides_1_day_before": l1,
            "rides_7_days_before": l7,
            "rides_14_days_before": l14,
            "rides_21_days_before": l21,
            "rides_28_days_before": l28_filled,
            "rides_28_days_before_raw": l28,
            "rides_28_days_before_available": l28_avail,
            "available_same_weekday_observations": avail_obs,
            "past_four_same_weekdays_mean": seasonal_mean,
        })

    feats = pd.DataFrame(feat_rows)

    # Chronological splits aligned with spec Section 9.10.3
    def assign_split(d: date) -> str:
        if d < date(2026, 4, 1):
            return "train"
        elif d < date(2026, 6, 1):
            return "validation"
        return "test"

    feats["split"] = feats["date"].map(assign_split)
    feats.to_parquet(os.path.join(PROCESSED_DIR, "daily_forecasting_features.parquet"), index=False)

    # Join with matched schedule for service-aware model
    service_feats = feats.merge(
        matched[["route", "date", "scheduled_trips", "scheduled_service_hours", "duration_complete", "source_snapshot", "archive_available_from"]],
        on=["route", "date"],
        how="inner",
    )
    service_feats.to_parquet(os.path.join(PROCESSED_DIR, "matched_service_features.parquet"), index=False)
    print(f"[build_reference_datasets] Built {len(prof)} profile rows, {len(feats)} demand feature rows, and {len(service_feats)} matched service feature rows.")

if __name__ == "__main__":
    run()
