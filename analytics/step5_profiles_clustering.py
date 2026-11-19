import json
import os
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

OUT_DIR = "data/processed/v1"
ARTIFACT_DIR = "artifacts/v1"

RANKING_MIN_DAYS = 20
CLUSTER_MIN_W_DAYS = 20
CLUSTER_MIN_WEEKEND_DAYS = 8

def build_profiles(matched_df: pd.DataFrame, start_date: str, end_date: str) -> pd.DataFrame:
    sub = matched_df[(matched_df["service_date"] >= start_date) & (matched_df["service_date"] <= end_date)].copy()
    grp = sub.groupby(["route", "daytype"], as_index=False).agg(
        observed_days=("service_date", "nunique"),
        total_rides=("rides", "sum"),
        mean_daily_rides=("rides", "mean"),
        std_daily_rides=("rides", "std"),
        total_scheduled_trips=("scheduled_trips", "sum"),
        mean_scheduled_trips=("scheduled_trips", "mean"),
        total_scheduled_hours=("scheduled_service_hours", "sum"),
        all_durations_complete=("duration_complete", "all"),
    )
    grp["rides_per_scheduled_trip"] = grp["total_rides"] / grp["total_scheduled_trips"]
    grp["rides_per_scheduled_hour"] = grp.apply(
        lambda r: r["total_rides"] / r["total_scheduled_hours"] if r["all_durations_complete"] and r["total_scheduled_hours"] > 0 else None,
        axis=1,
    )
    grp["is_ranking_eligible"] = (grp["observed_days"] >= RANKING_MIN_DAYS) & grp["rides_per_scheduled_hour"].notna()
    grp["service_productivity_metric_rank"] = (
        grp[grp["is_ranking_eligible"]]
        .groupby("daytype")["rides_per_scheduled_hour"]
        .rank(ascending=False, method="min")
    )
    return grp

def run():
    matched_df = pd.read_csv(os.path.join(OUT_DIR, "expanded_matched_utilization.csv"))

    # 1. Full matched period profiles for rankings
    profiles = build_profiles(matched_df, "2025-11-23", "2026-07-31")
    profiles.to_csv(os.path.join(OUT_DIR, "expanded_utilization_profiles.csv"), index=False)

    # 2. Pre-replay development profiles for Clustering (2025-11-23 to 2026-05-31)
    # 2. Pre-replay development profiles for Clustering (2025-11-23 to 2026-05-31)
    dev_profiles = build_profiles(matched_df, "2025-11-23", "2026-05-31")
    w = dev_profiles[dev_profiles["daytype"] == "W"].set_index("route")
    a = dev_profiles[dev_profiles["daytype"] == "A"].set_index("route")
    u = dev_profiles[dev_profiles["daytype"] == "U"].set_index("route")

    cluster_df = pd.DataFrame(index=w.index)
    cluster_df["weekday_observed_days"] = w["observed_days"]
    cluster_df["mean_weekday_rides"] = w["mean_daily_rides"]
    cluster_df["weekday_rides_cv"] = w["std_daily_rides"] / w["mean_daily_rides"]
    cluster_df["mean_weekday_scheduled_trips"] = w["mean_scheduled_trips"]
    cluster_df["weekday_rides_per_scheduled_hour"] = w["rides_per_scheduled_hour"]

    # Reindex weekend dataframes to match cluster_df index cleanly
    a_aligned = a.reindex(cluster_df.index)
    u_aligned = u.reindex(cluster_df.index)

    cluster_df["saturday_to_weekday_rides_ratio"] = a_aligned["mean_daily_rides"] / w["mean_daily_rides"]
    cluster_df.loc[a_aligned["observed_days"] < CLUSTER_MIN_WEEKEND_DAYS, "saturday_to_weekday_rides_ratio"] = None

    cluster_df["sunday_holiday_to_weekday_rides_ratio"] = u_aligned["mean_daily_rides"] / w["mean_daily_rides"]
    cluster_df.loc[u_aligned["observed_days"] < CLUSTER_MIN_WEEKEND_DAYS, "sunday_holiday_to_weekday_rides_ratio"] = None
    
    eligible = cluster_df[
        (cluster_df["weekday_observed_days"] >= CLUSTER_MIN_W_DAYS) &
        cluster_df["weekday_rides_per_scheduled_hour"].notna()
    ].copy()

    feat_cols = [
        "mean_weekday_rides", "weekday_rides_cv", "mean_weekday_scheduled_trips",
        "weekday_rides_per_scheduled_hour", "saturday_to_weekday_rides_ratio",
        "sunday_holiday_to_weekday_rides_ratio"
    ]

    pipe = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
        ("kmeans", KMeans(n_clusters=4, n_init=20, random_state=42))
    ])
    eligible["cluster_id"] = pipe.fit_predict(eligible[feat_cols])

    # Name clusters post-hoc based on centroid characteristics
    summary = eligible.groupby("cluster_id")[feat_cols].mean()
    ordered_ids = summary["mean_weekday_rides"].sort_values(ascending=False).index.tolist()
    labels = {
        ordered_ids[0]: "High-Demand Trunk Corridors",
        ordered_ids[1]: "Strong Urban Connectors",
        ordered_ids[2]: "Moderate Neighborhood Routes",
        ordered_ids[3]: "Specialized / Lower-Volume Routes",
    }
    eligible["cluster_label"] = eligible["cluster_id"].map(labels)
    eligible.reset_index().to_csv(os.path.join(OUT_DIR, "route_clusters.csv"), index=False)
    print("Route clustering complete. Grouped routes:", len(eligible))

if __name__ == "__main__":
    run()