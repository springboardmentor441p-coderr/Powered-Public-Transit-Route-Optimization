"""
Milestone 3 — Step 7: Build Configuration-Driven Route × Time-Band Review List

Combines October 2026 forecast predictions (Step 6), typical historical
performance (Jan-Sep), stop exclusivity, pairwise overlap categorization
(same_family vs shared_corridor), and K=3 route clustering groups (+ M35 outlier)
against explicit screening thresholds loaded from configs/optimization_thresholds.json.

Produces one row per active (route, time_band) with a human-readable written reason.

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

from src.eda_utils import TIME_BAND_ORDER, get_time_band_label

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DEFAULT = ROOT / "configs" / "optimization_thresholds.json"
DATA_PROCESSED = ROOT / "data" / "processed"
TAB_DIR = ROOT / "reports" / "tables"


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
    preds_path = TAB_DIR / "m3_october_predictions.csv"
    preds = pd.read_csv(preds_path)
    if "day_group" not in preds.columns:
        preds["day_group"] = np.where(
            preds["day_of_week"].isin(["Saturday", "Sunday"]), "weekend", "weekday"
        )

    matched = pd.read_parquet(
        DATA_PROCESSED / "matched_hourly.parquet",
        columns=[
            "route",
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
    typical_hist = matched[
        (~matched["is_public_holiday"])
        & (~matched["holiday_schedule"])
        & (~matched["is_storm"])
        & (~matched["is_outlier"])
        & (matched["trips_running"] > 0)
    ]
    hist_agg = (
        typical_hist.groupby(["route", "time_band", "day_group"], as_index=False)
        .agg(
            hist_riders=("ridership", "sum"),
            hist_svc_hours=("service_hours", "sum"),
            hist_trips=("trips_running", "sum"),
        )
    )
    hist_agg["hist_riders_per_service_hour"] = np.where(
        hist_agg["hist_svc_hours"] > 0,
        (hist_agg["hist_riders"] / hist_agg["hist_svc_hours"]).round(2),
        np.nan,
    )

    coverage = pd.read_csv(TAB_DIR / "m2_route_stop_coverage.csv").set_index("route")
    pairs_df = pd.read_csv(TAB_DIR / "m2_route_overlap_all_pairs.csv")
    overlap_map = build_overlap_lookup(pairs_df)
    clusters = pd.read_csv(TAB_DIR / "m3_route_clusters_assigned.csv").set_index("route_id")
    profiles = pd.read_parquet(DATA_PROCESSED / "route_profiles.parquet").set_index("route_id")

    day_group_days = preds.groupby("day_group")["date"].nunique().to_dict()
    day_group_dates = (
        preds.groupby("day_group")["date"]
        .apply(lambda s: f"{s.min()}..{s.max()} ({s.nunique()}d)")
        .to_dict()
    )
    day_group_svc_totals = preds.groupby("day_group")["service_hours"].sum().to_dict()

    # Aggregate Step 6 predictions per (route, time_band, day_group)
    grouped = (
        preds.groupby(["route", "time_band", "day_group"], as_index=False)
        .agg(
            active_hours=("pred_ridership", "size"),
            total_trips_running=("trips_running", "sum"),
            total_service_hours=("service_hours", "sum"),
            total_pred_ridership=("pred_ridership", "sum"),
            high_demand_hours=("pred_high_demand_per_trip", "sum"),
            mean_threshold_p75=("threshold_p75", "mean"),
        )
    )

    lag_sub = (
        preds[preds["lag_mean_available"].notna()]
        .groupby(["route", "time_band", "day_group"], as_index=False)
        .agg(
            trend_pred_sum=("pred_ridership", "sum"),
            prior_4wk_sum=("lag_mean_available", "sum"),
        )
    )
    grouped = grouped.merge(lag_sub, on=["route", "time_band", "day_group"], how="left")
    grouped = grouped.merge(
        hist_agg[["route", "time_band", "day_group", "hist_riders_per_service_hour"]],
        on=["route", "time_band", "day_group"],
        how="left",
    )

    grouped["days_in_group"] = grouped["day_group"].map(day_group_days).astype(int)
    grouped["dates_covered"] = grouped["day_group"].map(day_group_dates)
    grouped["total_service_hours"] = grouped["total_service_hours"].round(2)
    grouped["avg_service_hours_per_day"] = (
        grouped["total_service_hours"] / grouped["days_in_group"]
    ).round(2)
    grouped["pct_of_day_group_service_hours"] = np.round(
        grouped["total_service_hours"] / grouped["day_group"].map(day_group_svc_totals) * 100.0,
        3,
    )
    grouped["total_pred_ridership"] = grouped["total_pred_ridership"].round(1)
    grouped["pred_riders_per_trip"] = np.where(
        grouped["total_trips_running"] > 0,
        (grouped["total_pred_ridership"] / grouped["total_trips_running"]).round(2),
        np.nan,
    )
    grouped["pred_riders_per_service_hour"] = np.where(
        grouped["total_service_hours"] > 0,
        (grouped["total_pred_ridership"] / grouped["total_service_hours"]).round(2),
        np.nan,
    )
    grouped["high_demand_freq_pct"] = (
        (grouped["high_demand_hours"] / grouped["active_hours"]) * 100.0
    ).round(1)
    grouped["mean_threshold_p75"] = grouped["mean_threshold_p75"].round(2)
    grouped["forecast_trend_pct"] = np.where(
        grouped["prior_4wk_sum"] > 0,
        ((grouped["trend_pred_sum"] - grouped["prior_4wk_sum"]) / grouped["prior_4wk_sum"] * 100.0).round(2),
        np.nan,
    )

    r7 = cfg["step7_review_thresholds"]
    f_cfg = r7["fewer_trips_screening"]
    m_cfg = r7["more_trips_screening"]
    c_cfg = r7["coverage_guardrails"]
    o_cfg = r7["shared_corridor_overlap"]
    t_cfg = r7["forecast_trend_bands"]

    rows = []
    tb_rank = {tb: i for i, tb in enumerate(TIME_BAND_ORDER)}
    dg_rank = {"weekday": 0, "weekend": 1}

    for _, row in grouped.iterrows():
        r = row["route"]
        tb = row["time_band"]
        dg = row["day_group"]
        tb_label = get_time_band_label(tb)

        r_svch = float(row["pred_riders_per_service_hour"])
        r_trip = float(row["pred_riders_per_trip"])
        hd_pct = float(row["high_demand_freq_pct"])
        act_hrs = int(row["active_hours"])
        trips = int(row["total_trips_running"])
        trend = row["forecast_trend_pct"]
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

        min_act_fewer = f_cfg[f"min_active_hours_{dg}"]
        min_trp_fewer = f_cfg[f"min_trips_{dg}"]
        min_act_more = m_cfg[f"min_active_hours_{dg}"]

        is_fewer_cand = (
            r_svch <= f_cfg["max_pred_riders_per_service_hour"]
            and hd_pct <= f_cfg["max_high_demand_freq_pct"]
            and act_hrs >= min_act_fewer
            and trips >= min_trp_fewer
        )
        is_more_cand = (
            hd_pct >= m_cfg["min_high_demand_freq_pct"]
            and r_svch >= m_cfg["min_pred_riders_per_service_hour"]
            and act_hrs >= min_act_more
        )

        trend_str = f"{trend:+.1f}% vs 4-wk baseline" if pd.notna(trend) else "trend unavailable"
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

        if is_fewer_cand:
            review_cat = f_cfg["category_name"]
            if excl_share >= c_cfg["high_exclusive_stop_share"]:
                action = "trim_conservatively_minus_10pct_protect_coverage"
                reason = (
                    f"Low {dg} riders per svc-hr ({r_svch:.1f} riders/svc-hr, {r_trip:.1f} riders/trip; "
                    f"{hd_pct:.0f}% hrs >0.96x p75; {trend_str}), while high exclusive stop share "
                    f"({excl_share*100:.1f}% >= {c_cfg['high_exclusive_stop_share']*100:.0f}%) means "
                    f"most stops depend on {r}; test conservative -10% trim to preserve stop coverage."
                )
            else:
                action = "trim_candidate_up_to_20pct"
                reason = (
                    f"Low {dg} riders per svc-hr and per trip ({r_svch:.1f} riders/svc-hr, {r_trip:.1f} riders/trip; "
                    f"{hd_pct:.0f}% hrs >0.96x p75; {trend_str}) with moderate/low stop exclusivity "
                    f"({excl_share*100:.1f}%) and {sc_str}; candidate for -10% or -20% trip reduction."
                )
        elif is_more_cand:
            review_cat = m_cfg["category_name"]
            action = "add_trips_candidate"
            reason = (
                f"High {dg} riders per trip and per svc-hr ({hd_pct:.0f}% of hours >0.96x p75, "
                f"{r_svch:.1f} riders/svc-hr, {r_trip:.1f} riders/trip; {trend_str}); "
                f"{excl_share*100:.1f}% exclusive stops, {ov_str}. Test +10% to +20% added trips."
            )
        elif is_merge_pair and tb in ("midday", "morning_peak", "evening_peak"):
            review_cat = "shared_corridor_overlap_watch"
            action = "corridor_merge_check_only"
            reason = (
                f"Moderate {dg} riders per svc-hr ({r_svch:.1f} riders/svc-hr, {hd_pct:.0f}% hrs >0.96x p75; {trend_str}), "
                f"flagged for corridor coordination because {sc_str} meets the >= "
                f"{o_cfg['min_overlap_share_for_merge_check']*100:.0f}% shared_corridor check "
                f"({excl_share*100:.1f}% exclusive stops)."
            )
        else:
            review_cat = "no_change_watch"
            action = "hold_or_monitor"
            if r == "M35":
                reason = (
                    f"Separate outlier M35 ({dg}: {r_svch:.1f} riders/svc-hr, {r_trip:.1f} riders/trip, "
                    f"100.0% exclusive RFK Bridge stops): tiny denominator means small absolute swings "
                    f"exceed p75 ({hd_pct:.0f}% hrs); monitor without cutting sole link."
                )
            elif hd_pct >= m_cfg["min_high_demand_freq_pct"]:
                reason = (
                    f"Frequent p75 flags ({hd_pct:.0f}% in {dg}), yet riders per service-hour remain below "
                    f"{m_cfg['min_pred_riders_per_service_hour']:.0f} ({r_svch:.1f} riders/svc-hr; "
                    f"{trend_str}); monitor alongside {ov_str}."
                )
            else:
                reason = (
                    f"Mid-range {dg} riders per trip and per svc-hr ({r_svch:.1f} riders/svc-hr, {r_trip:.1f} riders/trip, "
                    f"{hd_pct:.0f}% hrs >0.96x p75; {trend_str}); {excl_share*100:.1f}% exclusive stops, "
                    f"{ov_str}. Hold current trips."
                )

        rows.append(
            {
                "route": r,
                "route_long_name": long_name,
                "service_type": svc_type,
                "day_group": dg,
                "days_in_group": int(row["days_in_group"]),
                "dates_covered": row["dates_covered"],
                "time_band": tb,
                "time_band_label": tb_label,
                "_dg_sort": dg_rank.get(dg, 9),
                "_tb_sort": tb_rank.get(tb, 99),
                "group_id": grp_id,
                "route_group": grp_label,
                "active_hours": act_hrs,
                "total_trips_running": trips,
                "total_service_hours": round(float(row["total_service_hours"]), 2),
                "avg_service_hours_per_day": float(row["avg_service_hours_per_day"]),
                "pct_of_day_group_service_hours": float(row["pct_of_day_group_service_hours"]),
                "total_pred_ridership": round(float(row["total_pred_ridership"]), 1),
                "pred_riders_per_trip": r_trip,
                "pred_riders_per_service_hour": r_svch,
                "hist_riders_per_service_hour": row["hist_riders_per_service_hour"],
                "mean_threshold_p75": float(row["mean_threshold_p75"]),
                "high_demand_hours": int(row["high_demand_hours"]),
                "high_demand_freq_pct": hd_pct,
                "prior_4wk_avg_total_riders": round(float(row["prior_4wk_sum"]), 1)
                if pd.notna(row["prior_4wk_sum"])
                else np.nan,
                "forecast_trend_pct": trend,
                "trend_direction": trend_dir,
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

