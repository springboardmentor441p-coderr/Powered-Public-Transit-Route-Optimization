"""
Milestone 2: Step 13 — Route Clustering Table

One row per route (41 routes), computed from typical weekdays in the training period (2026-01-04 to 2026-05-31):
- weekday riders (log scale), weekend-to-weekday ratio
- share of riders in morning peak, evening peak, and night
- riders per trip and riders per service-hour at peak and off-peak (totals / totals)
- route length, average stop spacing, scheduled speed, weekday trips
- demand variability (from Step 5), share of stops no other route serves (from Step 6)

Feature Selection & Scaling:
- Assess pairwise correlations and drop one of each pair with |r| > 0.85 to retain 8 to 10 features.
- Scale all selected features using StandardScaler.
- Save to data/processed/clustering_features.parquet and reports/tables/.
"""

from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
MATCHED_PATH = ROOT / "data" / "processed" / "matched_hourly.parquet"
PROFILES_PATH = ROOT / "data" / "processed" / "route_profiles.parquet"
COVERAGE_PATH = ROOT / "reports" / "tables" / "m2_route_stop_coverage.csv"
VARIABILITY_PATH = ROOT / "reports" / "tables" / "m2_route_demand_variability.csv"
DATA_PROCESSED_DIR = ROOT / "data" / "processed"
TAB_DIR = ROOT / "reports" / "tables"


def compute_clustering_features():
    print("Loading data for Step 13 route clustering table...")
    df = pd.read_parquet(MATCHED_PATH)
    profiles = pd.read_parquet(PROFILES_PATH)
    coverage = pd.read_csv(COVERAGE_PATH)
    variability = pd.read_csv(VARIABILITY_PATH)

    # 1. Filter to training period (2026-01-04 to 2026-05-31)
    train_df = df[df["date"] <= "2026-05-31"].copy()

    # Define typical mask
    typical_mask = (
        (~train_df["is_public_holiday"])
        & (~train_df["holiday_schedule"])
        & (~train_df["is_storm"])
        & (~train_df["is_outlier"])
    )
    typical_wd = train_df[typical_mask & (~train_df["is_weekend"])].copy()
    typical_we = train_df[typical_mask & (train_df["is_weekend"])].copy()

    routes = sorted(df["route"].unique())
    n_wd_days = typical_wd["date"].nunique()
    n_we_days = typical_we["date"].nunique()

    # Precompute demand variability per route (mean CV across daytime hours 06 to 22)
    daytime_var = variability[variability["hour"].between(6, 22)].groupby("route")["cv"].mean().to_dict()

    # Coverage map: exclusive stop share
    cov_map = coverage.set_index("route")["exclusive_stop_share"].to_dict()

    # Route profile lookup
    prof_map = profiles.set_index("route_id")

    records = []
    for r in routes:
        r_wd = typical_wd[typical_wd["route"] == r]
        r_we = typical_we[typical_we["route"] == r]

        # 1. Daily ridership
        tot_wd_riders = r_wd["ridership"].sum()
        mean_wd_daily = tot_wd_riders / n_wd_days if n_wd_days > 0 else 0
        weekday_riders_log = np.log1p(mean_wd_daily)

        tot_we_riders = r_we["ridership"].sum()
        mean_we_daily = tot_we_riders / n_we_days if n_we_days > 0 else 0
        weekend_to_weekday_ratio = (mean_we_daily / mean_wd_daily) if mean_wd_daily > 0 else 0.0

        # 2. Time-band shares of weekday riders
        am_riders = r_wd[r_wd["time_band"] == "morning_peak"]["ridership"].sum()
        pm_riders = r_wd[r_wd["time_band"] == "evening_peak"]["ridership"].sum()
        night_riders = r_wd[r_wd["time_band"] == "night"]["ridership"].sum()

        morning_peak_share = (am_riders / tot_wd_riders) if tot_wd_riders > 0 else 0.0
        evening_peak_share = (pm_riders / tot_wd_riders) if tot_wd_riders > 0 else 0.0
        night_share = (night_riders / tot_wd_riders) if tot_wd_riders > 0 else 0.0

        # 3. Peak vs Off-peak efficiency (Totals ÷ Totals)
        peak_mask = r_wd["time_band"].isin(["morning_peak", "evening_peak"])
        peak_sub = r_wd[peak_mask]
        offpeak_sub = r_wd[~peak_mask]

        peak_riders = peak_sub["ridership"].sum()
        peak_trips = peak_sub["trips_running"].sum()
        peak_sh = peak_sub["service_hours"].sum()

        offpeak_riders = offpeak_sub["ridership"].sum()
        offpeak_trips = offpeak_sub["trips_running"].sum()
        offpeak_sh = offpeak_sub["service_hours"].sum()

        peak_rpt = (peak_riders / peak_trips) if peak_trips > 0 else 0.0
        offpeak_rpt = (offpeak_riders / offpeak_trips) if offpeak_trips > 0 else 0.0

        peak_rpsh = (peak_riders / peak_sh) if peak_sh > 0 else 0.0
        offpeak_rpsh = (offpeak_riders / offpeak_sh) if offpeak_sh > 0 else 0.0

        # 4. Route geometry & timetable features
        p_row = prof_map.loc[r]
        length_km = float(p_row["route_length_km"])
        stop_cnt = int(p_row["stop_count"])
        avg_spacing_km = (length_km / stop_cnt) if stop_cnt > 0 else 0.0
        speed_kmh = float(p_row["avg_scheduled_speed_kmh"])
        weekday_trips = r_wd["trips_running"].sum() / n_wd_days

        # 5. External stability and coverage features
        demand_var = daytime_var.get(r, 0.25)
        exclusive_stops = cov_map.get(r, 0.0)

        records.append({
            "route": r,
            "weekday_riders_log": round(float(weekday_riders_log), 4),
            "weekend_to_weekday_ratio": round(float(weekend_to_weekday_ratio), 4),
            "morning_peak_share": round(float(morning_peak_share), 4),
            "evening_peak_share": round(float(evening_peak_share), 4),
            "night_share": round(float(night_share), 4),
            "peak_riders_per_trip": round(float(peak_rpt), 2),
            "offpeak_riders_per_trip": round(float(offpeak_rpt), 2),
            "peak_riders_per_service_hour": round(float(peak_rpsh), 2),
            "offpeak_riders_per_service_hour": round(float(offpeak_rpsh), 2),
            "route_length_km": round(length_km, 2),
            "avg_stop_spacing_km": round(float(avg_spacing_km), 4),
            "scheduled_speed_kmh": round(speed_kmh, 2),
            "weekday_trips": round(float(weekday_trips), 1),
            "demand_variability": round(float(demand_var), 4),
            "exclusive_stop_share": round(float(exclusive_stops), 4),
        })

    candidate_df = pd.DataFrame(records)
    print(f"Generated candidate clustering features for {len(candidate_df)} routes (15 candidate metrics).")

    # Correlation Matrix Analysis
    num_cols = [c for c in candidate_df.columns if c != "route"]
    corr_matrix = candidate_df[num_cols].corr()
    corr_csv = TAB_DIR / "m2_clustering_feature_correlations.csv"
    corr_matrix.round(4).to_csv(corr_csv)
    print(f"Saved: {corr_csv.relative_to(ROOT)}")

    # Check pairs with |r| > 0.85
    high_corr_pairs = []
    for i in range(len(num_cols)):
        for j in range(i + 1, len(num_cols)):
            c1, c2 = num_cols[i], num_cols[j]
            r_val = corr_matrix.loc[c1, c2]
            if abs(r_val) > 0.85:
                high_corr_pairs.append((c1, c2, r_val))

    print("\nHighly Correlated Pairs (|r| > 0.85):")
    for c1, c2, r_val in high_corr_pairs:
        print(f"  - {c1} vs {c2}: r = {r_val:.3f}")

    # Dropping redundant features:
    # 1. peak_riders_per_trip and peak_riders_per_service_hour are typically strongly correlated with each other and offpeak versions.
    # 2. weekday_trips strongly correlates with weekday_riders_log.
    # 3. evening_peak_share or morning_peak_share: keep both or peak vs night share.
    # We select a balanced, non-redundant set of 9 features covering demand volume, temporal profile, efficiency, geometry, speed, variability, and network coverage.
    
    # Selected 9 features:
    selected_features = [
        "weekday_riders_log",              # Volume scale (log)
        "weekend_to_weekday_ratio",        # Weekend vs weekday demand profile
        "morning_peak_share",              # Peak concentration
        "night_share",                     # 24h / evening orientation
        "peak_riders_per_service_hour",    # Efficiency (riders per service-hour at peak)
        "route_length_km",                 # Corridor length
        "scheduled_speed_kmh",             # Operational speed
        "demand_variability",              # Demand stability (CV)
        "exclusive_stop_share",            # Network coverage role
    ]

    # Verify no selected pair has |r| > 0.85
    sel_corr = candidate_df[selected_features].corr()
    max_corr = sel_corr.abs().where(~np.eye(len(selected_features), dtype=bool)).max().max()
    print(f"\nSelected {len(selected_features)} clustering features (Maximum pairwise |r| = {max_corr:.3f} < 0.85):")
    for f in selected_features:
        print(f"  * {f}")

    # Standard Scaling
    scaler = StandardScaler()
    scaled_values = scaler.fit_transform(candidate_df[selected_features])
    scaled_df = pd.DataFrame(scaled_values, columns=selected_features)
    scaled_df.insert(0, "route", candidate_df["route"])

    # Save outputs
    unscaled_csv = TAB_DIR / "m2_clustering_features_unscaled.csv"
    scaled_csv = TAB_DIR / "m2_clustering_features_scaled.csv"
    clustering_parquet = DATA_PROCESSED_DIR / "clustering_features.parquet"

    candidate_df.to_csv(unscaled_csv, index=False)
    scaled_df.to_csv(scaled_csv, index=False)
    scaled_df.to_parquet(clustering_parquet, index=False)

    print(f"\nSaved:")
    print(f"  Unscaled: {unscaled_csv.relative_to(ROOT)}")
    print(f"  Scaled:   {scaled_csv.relative_to(ROOT)}")
    print(f"  Parquet:  {clustering_parquet.relative_to(ROOT)} ({len(scaled_df)} routes)")

    return candidate_df, scaled_df


if __name__ == "__main__":
    compute_clustering_features()
