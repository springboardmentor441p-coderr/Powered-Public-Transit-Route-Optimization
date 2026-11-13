"""
Milestone 3 — Step 7: Build Configuration-Driven Route × Day-Group × Time-Band Review List

Evaluates observed typical-day ridership and service levels across a full 3-month window
(2026-08-01 to 2026-10-31: 63 typical weekdays and 27 typical weekend days, excluding public
holidays, holiday schedules, storm/outage hours, and the M35 Sep 19 outlier), joined with
non-overlapping Jan-Jul typical performance, stop exclusivity, pairwise overlap categorization
(same_family vs shared_corridor), and K=3 route clustering groups (+ M35 outlier) against
explicit screening thresholds loaded from configs/optimization_thresholds.json (including
days_count >= 20 and avg_trips_per_day >= 2.0 matching Milestone 2).

Produces one row per active (route, day_group, time_band) with a metric-backed written reason.

Usage:
    python -m src.build_review_list
    python -m src.build_review_list --config configs/optimization_thresholds.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.build_matched_table import assign_time_band
from src.eda_utils import TIME_BAND_ORDER, get_time_band_label
from src.predict import (
    EXTENDED_PUBLIC_HOLIDAYS,
    STORM_DATES,
    build_schedule_for_range,
    load_clean_ridership_history,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DEFAULT = ROOT / "configs" / "optimization_thresholds.json"
DATA_PROCESSED = ROOT / "data" / "processed"
TAB_DIR = ROOT / "reports" / "tables"


def load_observed_review_window_hourly(
    start_date: str = "2026-08-01", end_date: str = "2026-10-31"
) -> pd.DataFrame:
    """Load clean typical-day active hourly rows for start_date..end_date.

    Uses matched_hourly.parquet directly for <= 2026-09-30 (never reading test_features.parquet
    or writing test_runs.log) and combines cleaned Oct 2026 ridership with active GTFS schedules
    (2026-09-03 for Oct 1-16, 2026-10-17 for Oct 17-31).
    """
    matched = pd.read_parquet(
        DATA_PROCESSED / "matched_hourly.parquet",
        columns=[
            "route",
            "date",
            "hour",
            "day_of_week",
            "is_weekend",
            "is_public_holiday",
            "holiday_schedule",
            "is_storm",
            "is_outlier",
            "time_band",
            "ridership",
            "trips_running",
            "service_hours",
        ],
    )
    aug_sep = matched[
        (matched["date"] >= start_date)
        & (matched["date"] <= min(end_date, "2026-09-30"))
        & (matched["trips_running"] > 0)
    ].copy()

    frames = [aug_sep]
    if end_date >= "2026-10-01":
        oct_start = max(start_date, "2026-10-01")
        sched_parts = []
        hol_flags: dict[str, bool] = {}
        if oct_start <= "2026-10-16":
            s1, h1 = build_schedule_for_range(oct_start, min(end_date, "2026-10-16"), "2026-09-03")
            sched_parts.append(s1)
            hol_flags.update(h1)
        if end_date >= "2026-10-17":
            s2, h2 = build_schedule_for_range(max(oct_start, "2026-10-17"), end_date, "2026-10-17")
            sched_parts.append(s2)
            hol_flags.update(h2)
        sched_oct = pd.concat(sched_parts, ignore_index=True)
        rid = load_clean_ridership_history(end_date)
        rid_oct = rid[(rid["date"] >= oct_start) & (rid["date"] <= end_date)].copy()
        oct_df = sched_oct.merge(rid_oct, on=["route", "date", "hour"], how="left")
        oct_df["ridership"] = oct_df["ridership"].fillna(0.0)
        oct_df = oct_df[oct_df["trips_running"] > 0].copy()

        dt_s = pd.to_datetime(oct_df["date"])
        oct_df["day_of_week"] = dt_s.dt.day_name()
        oct_df["is_weekend"] = oct_df["day_of_week"].isin(["Saturday", "Sunday"])
        oct_df["is_public_holiday"] = oct_df["date"].isin(EXTENDED_PUBLIC_HOLIDAYS)
        oct_df["holiday_schedule"] = oct_df["date"].map(hol_flags).fillna(False).astype(bool)
        oct_df["is_storm"] = oct_df["date"].isin(STORM_DATES)
        oct_df["is_outlier"] = False
        oct_df["time_band"] = oct_df["hour"].apply(assign_time_band)
        frames.append(oct_df[aug_sep.columns])

    obs = pd.concat(frames, ignore_index=True)
    obs = obs[
        (~obs["is_public_holiday"])
        & (~obs["holiday_schedule"])
        & (~obs["is_storm"])
        & (~obs["is_outlier"])
        & (obs["trips_running"] > 0)
    ].copy()
    obs["day_group"] = np.where(obs["is_weekend"], "weekend", "weekday")
    obs["day_type"] = np.where(
        obs["day_of_week"] == "Saturday",
        "Typical Saturday",
        np.where(obs["day_of_week"] == "Sunday", "Typical Sunday", "Typical Weekday"),
    )
    p75 = pd.read_csv(TAB_DIR / "m2_high_demand_thresholds.csv")
    obs = obs.merge(p75, on=["route", "day_type"], how="left")
    obs["obs_riders_per_trip"] = obs["ridership"] / obs["trips_running"]
    obs["obs_high_demand_per_trip"] = (obs["obs_riders_per_trip"] > obs["threshold_p75"]).astype(int)
    return obs


def classify_overlap_pair(r1: str, r2: str) -> str:
    """Match Step 6 overlap rule strictly: same_family vs shared_corridor."""
    b1, b2 = r1.rstrip("+"), r2.rstrip("+")
    if (
        b1 == b2
        or (b1.startswith("M34") and b2.startswith("M34"))
        or (b1.startswith("M14") and b2.startswith("M14"))
    ):
        return "same_family"
    return "shared_corridor"


def load_config(config_path: Path) -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_overlap_lookup(pairs_df: pd.DataFrame) -> dict[str, dict]:
    """Extract highest overall overlap partner and highest shared_corridor partner per route."""
    pairs = pairs_df.copy()
    pairs["overlap_category"] = [
        classify_overlap_pair(r1, r2) for r1, r2 in zip(pairs["route_1"], pairs["route_2"])
    ]
    all_routes = sorted(set(pairs["route_1"]).union(set(pairs["route_2"])))
    lookup = {}
    for route in all_routes:
        sub = pairs[(pairs["route_1"] == route) | (pairs["route_2"] == route)].sort_values(
            "overlap_share", ascending=False
        )
        top_row = sub.iloc[0]
        partner = top_row["route_2"] if top_row["route_1"] == route else top_row["route_1"]

        sc_sub = sub[sub["overlap_category"] == "shared_corridor"]
        if not sc_sub.empty:
            sc_row = sc_sub.iloc[0]
            sc_partner = sc_row["route_2"] if sc_row["route_1"] == route else sc_row["route_1"]
            sc_share = float(sc_row["overlap_share"])
        else:
            sc_partner = "None"
            sc_share = 0.0

        lookup[route] = {
            "top_overlap_partner": partner,
            "top_overlap_share": round(float(top_row["overlap_share"]), 4),
            "top_overlap_category": top_row["overlap_category"],
            "top_shared_corridor_partner": sc_partner,
            "top_shared_corridor_share": round(sc_share, 4),
        }
    return lookup


def build_review_table(cfg: dict) -> pd.DataFrame:
    w_cfg = cfg["step7_9_review_window"]
    start_date = w_cfg["start_date"]
    end_date = w_cfg["end_date"]

    obs = load_observed_review_window_hourly(start_date=start_date, end_date=end_date)

    # Non-overlapping Jan-Jul typical-day reference from matched_hourly.parquet
    matched = pd.read_parquet(
        DATA_PROCESSED / "matched_hourly.parquet",
        columns=[
            "route",
            "date",
            "time_band",
            "is_weekend",
            "ridership",
            "service_hours",
            "trips_running",
            "is_public_holiday",
            "holiday_schedule",
            "is_storm",
            "is_outlier",
        ],
    )
    matched["day_group"] = np.where(matched["is_weekend"], "weekend", "weekday")
    jan_jul_typ = matched[
        (matched["date"] < start_date)
        & (~matched["is_public_holiday"])
        & (~matched["holiday_schedule"])
        & (~matched["is_storm"])
        & (~matched["is_outlier"])
        & (matched["trips_running"] > 0)
    ]
    hist_agg = (
        jan_jul_typ.groupby(["route", "time_band", "day_group"], as_index=False)
        .agg(
            hist_riders=("ridership", "sum"),
            hist_svc_hours=("service_hours", "sum"),
        )
    )
    hist_agg["hist_jan_jul_riders_per_service_hour"] = np.where(
        hist_agg["hist_svc_hours"] > 0,
        (hist_agg["hist_riders"] / hist_agg["hist_svc_hours"]).round(2),
        np.nan,
    )

    coverage = pd.read_csv(TAB_DIR / "m2_route_stop_coverage.csv").set_index("route")
    pairs_df = pd.read_csv(TAB_DIR / "m2_route_overlap_all_pairs.csv")
    overlap_map = build_overlap_lookup(pairs_df)
    clusters = pd.read_csv(TAB_DIR / "m3_route_clusters_assigned.csv").set_index("route_id")
    profiles = pd.read_parquet(DATA_PROCESSED / "route_profiles.parquet").set_index("route_id")

    day_group_days = obs.groupby("day_group")["date"].nunique().to_dict()
    day_group_dates = (
        obs.groupby("day_group")["date"]
        .apply(lambda s: f"{s.min()}..{s.max()} ({s.nunique()} typical d)")
        .to_dict()
    )
    day_group_svc_totals = obs.groupby("day_group")["service_hours"].sum().to_dict()

    # Aggregate observed typical-day hours per (route, time_band, day_group)
    grouped = (
        obs.groupby(["route", "time_band", "day_group"], as_index=False)
        .agg(
            days_count=("date", "nunique"),
            active_hours=("ridership", "size"),
            total_trips_running=("trips_running", "sum"),
            total_service_hours=("service_hours", "sum"),
            total_obs_ridership=("ridership", "sum"),
            high_demand_hours=("obs_high_demand_per_trip", "sum"),
            mean_threshold_p75=("threshold_p75", "mean"),
        )
    )

    grouped = grouped.merge(
        hist_agg[["route", "time_band", "day_group", "hist_jan_jul_riders_per_service_hour"]],
        on=["route", "time_band", "day_group"],
        how="left",
    )

    grouped["days_in_day_group"] = grouped["day_group"].map(day_group_days).astype(int)
    grouped["dates_covered"] = grouped["day_group"].map(day_group_dates)
    grouped["total_service_hours"] = grouped["total_service_hours"].round(2)
    grouped["avg_trips_per_day"] = (
        grouped["total_trips_running"] / grouped["days_count"]
    ).round(2)
    grouped["avg_service_hours_per_day"] = (
        grouped["total_service_hours"] / grouped["days_count"]
    ).round(2)
    grouped["pct_of_day_group_service_hours"] = np.round(
        grouped["total_service_hours"] / grouped["day_group"].map(day_group_svc_totals) * 100.0,
        3,
    )
    grouped["total_obs_ridership"] = grouped["total_obs_ridership"].round(1)
    grouped["obs_riders_per_trip"] = np.where(
        grouped["total_trips_running"] > 0,
        (grouped["total_obs_ridership"] / grouped["total_trips_running"]).round(2),
        np.nan,
    )
    grouped["obs_riders_per_service_hour"] = np.where(
        grouped["total_service_hours"] > 0,
        (grouped["total_obs_ridership"] / grouped["total_service_hours"]).round(2),
        np.nan,
    )
    grouped["high_demand_freq_pct"] = (
        (grouped["high_demand_hours"] / grouped["active_hours"]) * 100.0
    ).round(1)
    grouped["mean_threshold_p75"] = grouped["mean_threshold_p75"].round(2)
    grouped["obs_vs_jan_jul_pct"] = np.where(
        grouped["hist_jan_jul_riders_per_service_hour"] > 0,
        (
            (grouped["obs_riders_per_service_hour"] - grouped["hist_jan_jul_riders_per_service_hour"])
            / grouped["hist_jan_jul_riders_per_service_hour"]
            * 100.0
        ).round(2),
        np.nan,
    )

    r7 = cfg["step7_review_thresholds"]
    f_cfg = r7["fewer_trips_screening"]
    m_cfg = r7["more_trips_screening"]
    c_cfg = r7["coverage_guardrails"]
    o_cfg = r7["shared_corridor_overlap"]
    t_cfg = r7["demand_trend_bands"]

    rows = []
    tb_rank = {tb: i for i, tb in enumerate(TIME_BAND_ORDER)}
    dg_rank = {"weekday": 0, "weekend": 1}

    for _, row in grouped.iterrows():
        r = row["route"]
        tb = row["time_band"]
        dg = row["day_group"]
        tb_label = get_time_band_label(tb)

        days_cnt = int(row["days_count"])
        avg_trp_day = float(row["avg_trips_per_day"])
        r_svch = float(row["obs_riders_per_service_hour"])
        r_trip = float(row["obs_riders_per_trip"])
        hd_pct = float(row["high_demand_freq_pct"])
        act_hrs = int(row["active_hours"])
        trips = int(row["total_trips_running"])
        trend = row["obs_vs_jan_jul_pct"]
        trend_dir = (
            "flat"
            if pd.isna(trend)
            else ("rising" if trend >= t_cfg["rising_pct"] else ("falling" if trend <= t_cfg["falling_pct"] else "stable"))
        )

        excl_share = float(coverage.loc[r, "exclusive_stop_share"]) if r in coverage.index else 0.0
        ov = overlap_map.get(
            r,
            {
                "top_overlap_partner": "None",
                "top_overlap_share": 0.0,
                "top_overlap_category": "none",
                "top_shared_corridor_partner": "None",
                "top_shared_corridor_share": 0.0,
            },
        )
        grp_id = int(clusters.loc[r, "group_id"]) if r in clusters.index else -1
        grp_label = str(clusters.loc[r, "group_label"]) if r in clusters.index else "Unknown"
        svc_type = str(profiles.loc[r, "service_type"]) if r in profiles.index else "Unknown"
        long_name = str(profiles.loc[r, "route_long_name"]) if r in profiles.index else ""

        is_merge_pair = ov["top_shared_corridor_share"] >= o_cfg["min_overlap_share_for_merge_check"]

        meets_fewer_sample = (
            days_cnt >= f_cfg["min_days_count"]
            and avg_trp_day >= f_cfg["min_avg_trips_per_day"]
        )
        meets_more_sample = (
            days_cnt >= m_cfg["min_days_count"]
            and avg_trp_day >= m_cfg["min_avg_trips_per_day"]
        )

        is_fewer_cand = (
            r != "M35"
            and meets_fewer_sample
            and r_svch <= f_cfg["max_obs_riders_per_service_hour"]
            and hd_pct <= f_cfg["max_high_demand_freq_pct"]
        )
        is_more_cand = (
            r != "M35"
            and meets_more_sample
            and hd_pct >= m_cfg["min_high_demand_freq_pct"]
            and r_svch >= m_cfg["min_obs_riders_per_service_hour"]
        )

        trend_str = f"{trend:+.1f}% vs Jan-Jul" if pd.notna(trend) else "Jan-Jul ref unavailable"
        ov_str = (
            f"top overlap {ov['top_overlap_partner']} ({ov['top_overlap_share']*100:.1f}%, {ov['top_overlap_category']})"
            if ov["top_overlap_partner"] != "None"
            else "no shared stops with other routes"
        )
        sc_str = (
            f"max shared_corridor {ov['top_shared_corridor_partner']} ({ov['top_shared_corridor_share']*100:.1f}%)"
            if ov["top_shared_corridor_partner"] != "None"
            else "no shared_corridor overlap"
        )

        if not meets_fewer_sample or not meets_more_sample:
            review_cat = "no_change_watch"
            action = "hold_or_monitor_low_sample"
            reason = (
                f"Held out ({dg}: {days_cnt} days, {avg_trp_day:.1f} avg trips/day): "
                f"below Milestone 2 screening minimum ({f_cfg['min_days_count']} days, "
                f"{f_cfg['min_avg_trips_per_day']:.1f} avg trips/day); low sample / minimal service, do not adjust."
            )
        elif is_fewer_cand:
            review_cat = f_cfg["category_name"]
            if excl_share >= c_cfg["high_exclusive_stop_share"]:
                action = "trim_conservatively_minus_10pct_protect_coverage"
                reason = (
                    f"Low {dg} riders per svc-hr over {days_cnt} days ({r_svch:.1f} riders/svc-hr, "
                    f"{r_trip:.1f} riders/trip, {avg_trp_day:.1f} trips/day; {hd_pct:.1f}% hrs >p75; {trend_str}), "
                    f"while high exclusive stop share ({excl_share*100:.1f}% >= {c_cfg['high_exclusive_stop_share']*100:.0f}%) "
                    f"means most stops depend on {r}; test conservative -10% trim to preserve stop coverage."
                )
            else:
                action = "trim_candidate_up_to_20pct"
                reason = (
                    f"Low {dg} riders per svc-hr and per trip over {days_cnt} days ({r_svch:.1f} riders/svc-hr, "
                    f"{r_trip:.1f} riders/trip, {avg_trp_day:.1f} trips/day; {hd_pct:.1f}% hrs >p75; {trend_str}) "
                    f"with moderate/low stop exclusivity ({excl_share*100:.1f}%) and {sc_str}; "
                    f"candidate for -10% or -20% trip reduction."
                )
        elif is_more_cand:
            review_cat = m_cfg["category_name"]
            action = "add_trips_candidate"
            reason = (
                f"High {dg} riders per trip and per svc-hr over {days_cnt} days ({hd_pct:.1f}% of hours >p75, "
                f"{r_svch:.1f} riders/svc-hr, {r_trip:.1f} riders/trip, {avg_trp_day:.1f} trips/day; {trend_str}); "
                f"{excl_share*100:.1f}% exclusive stops, {ov_str}. Test +10% to +20% added trips."
            )
        elif is_merge_pair and tb in ("midday", "morning_peak", "evening_peak"):
            review_cat = "shared_corridor_overlap_watch"
            action = "corridor_merge_check_only"
            reason = (
                f"Moderate {dg} riders per svc-hr over {days_cnt} days ({r_svch:.1f} riders/svc-hr, "
                f"{hd_pct:.1f}% hrs >p75; {trend_str}), flagged for corridor coordination because "
                f"{sc_str} meets >= {o_cfg['min_overlap_share_for_merge_check']*100:.0f}% "
                f"shared_corridor check ({excl_share*100:.1f}% exclusive stops)."
            )
        else:
            review_cat = "no_change_watch"
            action = "hold_or_monitor"
            if r == "M35":
                reason = (
                    f"Separate outlier M35 ({dg}, {days_cnt} days: {r_svch:.1f} riders/svc-hr, "
                    f"{r_trip:.1f} riders/trip, 100.0% exclusive RFK Bridge stops): tiny denominator means "
                    f"small absolute swings exceed p75 ({hd_pct:.1f}% hrs); monitor without cutting sole link."
                )
            elif hd_pct >= m_cfg["min_high_demand_freq_pct"]:
                reason = (
                    f"Frequent p75 flags ({hd_pct:.1f}% in {dg} over {days_cnt} days), yet riders per service-hour "
                    f"remain below {m_cfg['min_obs_riders_per_service_hour']:.0f} ({r_svch:.1f} riders/svc-hr; "
                    f"{trend_str}); monitor alongside {ov_str}."
                )
            else:
                reason = (
                    f"Mid-range {dg} riders per trip and per svc-hr over {days_cnt} days ({r_svch:.1f} riders/svc-hr, "
                    f"{r_trip:.1f} riders/trip, {hd_pct:.1f}% hrs >p75; {trend_str}); {excl_share*100:.1f}% exclusive stops, "
                    f"{ov_str}. Hold current trips."
                )

        rows.append(
            {
                "route": r,
                "route_long_name": long_name,
                "service_type": svc_type,
                "day_group": dg,
                "days_count": days_cnt,
                "days_in_day_group": int(row["days_in_day_group"]),
                "dates_covered": row["dates_covered"],
                "time_band": tb,
                "time_band_label": tb_label,
                "_dg_sort": dg_rank.get(dg, 9),
                "_tb_sort": tb_rank.get(tb, 99),
                "group_id": grp_id,
                "route_group": grp_label,
                "active_hours": act_hrs,
                "total_trips_running": trips,
                "avg_trips_per_day": avg_trp_day,
                "total_service_hours": round(float(row["total_service_hours"]), 2),
                "avg_service_hours_per_day": float(row["avg_service_hours_per_day"]),
                "pct_of_day_group_service_hours": float(row["pct_of_day_group_service_hours"]),
                "total_obs_ridership": round(float(row["total_obs_ridership"]), 1),
                "obs_riders_per_trip": r_trip,
                "obs_riders_per_service_hour": r_svch,
                "hist_jan_jul_riders_per_service_hour": row["hist_jan_jul_riders_per_service_hour"],
                "obs_vs_jan_jul_pct": trend,
                "trend_direction": trend_dir,
                "mean_threshold_p75": float(row["mean_threshold_p75"]),
                "high_demand_hours": int(row["high_demand_hours"]),
                "high_demand_freq_pct": hd_pct,
                "exclusive_stop_share": round(excl_share, 4),
                "top_overlap_partner": ov["top_overlap_partner"],
                "top_overlap_share": ov["top_overlap_share"],
                "top_overlap_category": ov["top_overlap_category"],
                "top_shared_corridor_partner": ov["top_shared_corridor_partner"],
                "top_shared_corridor_share": ov["top_shared_corridor_share"],
                "is_merge_check_candidate": bool(is_merge_pair),
                "review_category": review_cat,
                "recommended_action": action,
                "reason": reason,
            }
        )

    out_df = (
        pd.DataFrame(rows)
        .sort_values(["route", "_dg_sort", "_tb_sort"])
        .drop(columns=["_dg_sort", "_tb_sort"])
        .reset_index(drop=True)
    )
    return out_df


def main():
    parser = argparse.ArgumentParser(description="Build Step 7 (route, day_group, time_band) review list from config thresholds.")
    parser.add_argument("--config", default=str(CONFIG_DEFAULT), help="Path to optimization thresholds JSON config")
    parser.add_argument("--out", default=str(TAB_DIR / "m3_step7_review_list.csv"), help="Output review list CSV")
    args = parser.parse_args()

    cfg = load_config(Path(args.config))
    review_df = build_review_table(cfg)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    review_df.to_csv(out_path, index=False)

    print(f"Saved Step 7 review list ({len(review_df)} route x day_group x time_band rows) -> {out_path}")
    print("\nBreakdown by (day_group, review_category):")
    print(review_df.groupby(["day_group", "review_category"]).size().to_string())


if __name__ == "__main__":
    main()

