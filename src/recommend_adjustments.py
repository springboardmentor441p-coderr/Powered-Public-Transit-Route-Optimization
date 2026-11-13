"""
Milestone 3 — Steps 8 & 9: Service Scenarios, Shared-Corridor Merge Checks &
Budget-Neutral Service-Hour Reallocation Plan

Step 8:
  - Evaluates +/-10% and +/-20% trip changes across all fewer_trips_candidate and
    more_trips_candidate (route, day_group, time_band) cells from Step 7 under the
    explicit assumption that ridership remains constant when trips change.
  - Evaluates merge/consolidation feasibility strictly on shared_corridor route pairs
    (explicitly excluding same_family variants such as M15/M15+, M34+/M34A+, M14A+/M14D+).

Step 9:
  - Builds one budget-neutral service reallocation plan transferring scheduled
    service-hours within weekday (10d) and weekend (4d) budgets from low riders/svc-hr
    night/early-morning cells to cells with high riders per trip (net service-hour
    change <= 0.0 per day_group), respecting stop exclusivity guardrails and trip floors.

Outputs:
  reports/tables/m3_step8_candidate_scenarios.csv
  reports/tables/m3_step8_shared_corridor_merge_checks.csv
  reports/tables/m3_step9_budget_neutral_reallocation.csv
  reports/figures/m3_step9_reallocation_summary.png

Usage:
    python -m src.recommend_adjustments
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.build_review_list import classify_overlap_pair, load_config

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DEFAULT = ROOT / "configs" / "optimization_thresholds.json"
DATA_PROCESSED = ROOT / "data" / "processed"
TAB_DIR = ROOT / "reports" / "tables"
FIG_DIR = ROOT / "reports" / "figures"


def simulate_trip_scenarios(
    review_df: pd.DataFrame, preds_df: pd.DataFrame, cfg: dict
) -> pd.DataFrame:
    """Test +/-10% and +/-20% trip changes per Step 7 candidate (route, day_group, time_band)."""
    rules = cfg["step8_9_adjustment_rules"]
    c_cfg = cfg["step7_review_thresholds"]["coverage_guardrails"]
    f_cat = cfg["step7_review_thresholds"]["fewer_trips_screening"]["category_name"]
    m_cat = cfg["step7_review_thresholds"]["more_trips_screening"]["category_name"]
    deltas = rules["scenario_trip_changes_pct"]
    floor_per_hr = int(rules["min_trips_per_active_hour_floor"])

    if "day_group" not in preds_df.columns:
        preds_df = preds_df.copy()
        preds_df["day_group"] = np.where(
            preds_df["day_of_week"].isin(["Saturday", "Sunday"]), "weekend", "weekday"
        )

    dg_svc_totals = preds_df.groupby("day_group")["service_hours"].sum().to_dict()
    net_14d_svc = float(preds_df["service_hours"].sum())

    candidates = review_df[review_df["review_category"].isin([f_cat, m_cat])].copy()

    rows = []
    for _, cand in candidates.iterrows():
        r = cand["route"]
        tb = cand["time_band"]
        dg = cand["day_group"]
        days_in_grp = int(cand["days_in_group"])
        cat = cand["review_category"]
        act_hrs = int(cand["active_hours"])
        base_trips = int(cand["total_trips_running"])
        base_svc_hrs = float(cand["total_service_hours"])
        tot_riders = float(cand["total_pred_ridership"])
        base_hd_hrs = int(cand["high_demand_hours"])
        excl_share = float(cand["exclusive_stop_share"])

        sub_hrs = preds_df[
            (preds_df["route"] == r)
            & (preds_df["time_band"] == tb)
            & (preds_df["day_group"] == dg)
        ]
        min_trips_floor = act_hrs * floor_per_hr

        for pct in deltas:
            scale_target = 1.0 + pct / 100.0
            new_trips = int(max(min_trips_floor, round(base_trips * scale_target)))
            actual_scale = new_trips / base_trips if base_trips > 0 else 1.0
            new_svc_hrs = round(base_svc_hrs * actual_scale, 2)
            delta_trips = new_trips - base_trips
            delta_svc_hrs = round(new_svc_hrs - base_svc_hrs, 2)

            # Constant ridership assumption: total riders unchanged when trips change
            new_r_per_trip = round(tot_riders / new_trips, 2) if new_trips > 0 else np.nan
            new_r_per_svch = round(tot_riders / new_svc_hrs, 2) if new_svc_hrs > 0 else np.nan

            # Recompute hourly p75 threshold exceedance under scaled trips
            sim_trips_hr = np.maximum(floor_per_hr, sub_hrs["trips_running"].values * actual_scale)
            sim_ratio_hr = sub_hrs["pred_ridership"].values / sim_trips_hr
            sim_hd_hrs = int((sim_ratio_hr > sub_hrs["cutoff_threshold"].values).sum())
            hd_delta = sim_hd_hrs - base_hd_hrs

            if pct < 0 and excl_share >= c_cfg["high_exclusive_stop_share"] and abs(pct) > 10:
                guardrail_status = "exceeds_10pct_exclusivity_guardrail"
            elif pct < 0 and hd_delta > 0:
                guardrail_status = "warning_pushes_hours_above_threshold"
            else:
                guardrail_status = "ok"

            rows.append(
                {
                    "route": r,
                    "day_group": dg,
                    "days_in_group": days_in_grp,
                    "time_band": tb,
                    "review_category": cat,
                    "group_id": int(cand["group_id"]),
                    "exclusive_stop_share": excl_share,
                    "scenario_trip_change_pct": pct,
                    "effective_trip_change_pct": round((actual_scale - 1.0) * 100.0, 2),
                    "base_trips": base_trips,
                    "new_trips": new_trips,
                    "delta_trips": delta_trips,
                    "base_service_hours": base_svc_hrs,
                    "new_service_hours": new_svc_hrs,
                    "delta_service_hours": delta_svc_hrs,
                    "delta_service_hours_per_day": round(delta_svc_hrs / days_in_grp, 2),
                    "pct_of_day_group_service_hours": round(
                        delta_svc_hrs / dg_svc_totals[dg] * 100.0, 3
                    ),
                    "pct_of_14day_network_service_hours": round(
                        delta_svc_hrs / net_14d_svc * 100.0, 3
                    ),
                    "constant_pred_ridership": tot_riders,
                    "base_riders_per_trip": float(cand["pred_riders_per_trip"]),
                    "new_riders_per_trip": new_r_per_trip,
                    "base_riders_per_service_hour": float(cand["pred_riders_per_service_hour"]),
                    "new_riders_per_service_hour": new_r_per_svch,
                    "base_high_demand_hours": base_hd_hrs,
                    "sim_high_demand_hours": sim_hd_hrs,
                    "high_demand_hours_delta": hd_delta,
                    "guardrail_status": guardrail_status,
                }
            )

    return pd.DataFrame(rows)


def evaluate_shared_corridor_merges(
    preds_df: pd.DataFrame, cfg: dict
) -> pd.DataFrame:
    """Evaluate merge feasibility strictly for shared_corridor pairs (excluding same_family)."""
    min_share = cfg["step7_review_thresholds"]["shared_corridor_overlap"][
        "min_overlap_share_for_merge_check"
    ]
    pairs = pd.read_csv(TAB_DIR / "m2_route_overlap_all_pairs.csv")
    pairs["overlap_category"] = [
        classify_overlap_pair(r1, r2) for r1, r2 in zip(pairs["route_1"], pairs["route_2"])
    ]

    # Assert strict shared_corridor filter (plus >=30% floor so borderline corridor pairs are visible)
    sc_pairs = pairs[
        (pairs["overlap_category"] == "shared_corridor") & (pairs["overlap_share"] >= 0.30)
    ].copy()
    assert (sc_pairs["overlap_category"] == "shared_corridor").all()

    coverage = pd.read_csv(TAB_DIR / "m2_route_stop_coverage.csv").set_index("route")
    clusters = pd.read_csv(TAB_DIR / "m3_route_clusters_assigned.csv").set_index("route_id")
    route_agg = (
        preds_df.groupby("route")
        .agg(
            tot_riders=("pred_ridership", "sum"),
            tot_trips=("trips_running", "sum"),
            tot_svc_hrs=("service_hours", "sum"),
            high_hrs=("pred_high_demand_per_trip", "sum"),
            n_hrs=("pred_ridership", "size"),
        )
    )
    route_agg["riders_per_trip"] = route_agg["tot_riders"] / route_agg["tot_trips"]
    route_agg["riders_per_svch"] = route_agg["tot_riders"] / route_agg["tot_svc_hrs"]
    route_agg["high_pct"] = 100.0 * route_agg["high_hrs"] / route_agg["n_hrs"]

    rows = []
    for _, p in sc_pairs.sort_values("overlap_share", ascending=False).iterrows():
        r_sm = p["smaller_route"]
        r_lg = p["larger_route"]
        ov_share = float(p["overlap_share"])
        meets_40 = ov_share >= min_share

        sm_riders_day = float(route_agg.loc[r_sm, "tot_riders"]) / 14.0
        lg_riders_day = float(route_agg.loc[r_lg, "tot_riders"]) / 14.0
        sm_excl = float(coverage.loc[r_sm, "exclusive_stop_share"])
        lg_excl = float(coverage.loc[r_lg, "exclusive_stop_share"])
        sm_high = float(route_agg.loc[r_sm, "high_pct"])
        lg_high = float(route_agg.loc[r_lg, "high_pct"])
        sm_grp = int(clusters.loc[r_sm, "group_id"])
        lg_grp = int(clusters.loc[r_lg, "group_id"])

        # Stress test: if full merge dropped 20% of combined trips while retaining riders
        comb_riders = float(route_agg.loc[r_sm, "tot_riders"] + route_agg.loc[r_lg, "tot_riders"])
        comb_trips = float(route_agg.loc[r_sm, "tot_trips"] + route_agg.loc[r_lg, "tot_trips"])
        base_comb_rpt = comb_riders / comb_trips
        post_20cut_rpt = comb_riders / (0.80 * comb_trips)

        unique_stops_sm = int(p["smaller_route_stops"] - p["shared_stops_count"])

        # Operational merge screening verdict
        if sm_riders_day >= 5000 and max(sm_high, lg_high) >= 35.0:
            verdict = "do_not_merge_coordinate_headways_only"
            reason = (
                f"Both routes carry heavy demand ({r_sm} ~{sm_riders_day:,.0f}/day, "
                f"{sm_high:.0f}% high-demand hrs; {r_lg} ~{lg_riders_day:,.0f}/day, "
                f"{lg_high:.0f}% high-demand hrs) and serve {unique_stops_sm} non-shared stops "
                f"on {r_sm}; merging/cutting 20% pushes corridor average load from "
                f"{base_comb_rpt:.1f} to {post_20cut_rpt:.1f} riders/trip. Stagger headways instead."
            )
        elif sm_excl >= 0.45 or unique_stops_sm >= 20:
            verdict = "partial_segment_spacing_only_unique_branches"
            reason = (
                f"Smaller route {r_sm} retains {unique_stops_sm} unshared stops "
                f"({sm_excl*100:.1f}% stop exclusivity across network); shared trunk "
                f"allows timed spacing, but full route merger would sever distinct branch service."
            )
        elif meets_40 and min(sm_riders_day, lg_riders_day) < 3500:
            verdict = "candidate_for_offpeak_consolidation_study"
            reason = (
                f"High shared_corridor overlap ({ov_share*100:.1f}%) with lighter load on "
                f"{r_sm} (~{sm_riders_day:,.0f} pred riders/day, {sm_high:.0f}% high-demand hrs, "
                f"Group {sm_grp}); test off-peak/night schedule consolidation with {r_lg} "
                f"(Group {lg_grp}), subject to field audit of the {unique_stops_sm} unshared stops."
            )
        else:
            verdict = "monitor_shared_corridor_no_merge"
            reason = (
                f"Moderate shared_corridor overlap ({ov_share*100:.1f}%) or distinct corridor "
                f"role ({r_sm} ~{sm_riders_day:,.0f}/day vs {r_lg} ~{lg_riders_day:,.0f}/day); "
                f"use selective trip trims rather than route merger."
            )

        rows.append(
            {
                "route_1": p["route_1"],
                "route_2": p["route_2"],
                "overlap_category": "shared_corridor",
                "smaller_route": r_sm,
                "larger_route": r_lg,
                "shared_stops": int(p["shared_stops_count"]),
                "unshared_stops_on_smaller_route": unique_stops_sm,
                "overlap_share_pct": round(ov_share * 100.0, 1),
                "jaccard_pct": round(float(p["jaccard_similarity"]) * 100.0, 1),
                "meets_40pct_config_rule": meets_40,
                "smaller_route_group": sm_grp,
                "larger_route_group": lg_grp,
                "smaller_route_excl_stop_share": round(sm_excl, 4),
                "larger_route_excl_stop_share": round(lg_excl, 4),
                "smaller_route_pred_riders_per_day": round(sm_riders_day, 0),
                "larger_route_pred_riders_per_day": round(lg_riders_day, 0),
                "combined_base_riders_per_trip": round(base_comb_rpt, 2),
                "combined_post_20pct_cut_riders_per_trip": round(post_20cut_rpt, 2),
                "merge_feasibility_verdict": verdict,
                "verdict_reason": reason,
            }
        )

    return pd.DataFrame(rows)


def build_budget_neutral_reallocation(
    review_df: pd.DataFrame, scenarios_df: pd.DataFrame, cfg: dict
) -> pd.DataFrame:
    """Construct one budget-neutral service reallocation plan balanced within each day_group."""
    f_cat = cfg["step7_review_thresholds"]["fewer_trips_screening"]["category_name"]
    m_cat = cfg["step7_review_thresholds"]["more_trips_screening"]["category_name"]
    c_cfg = cfg["step7_review_thresholds"]["coverage_guardrails"]

    all_donors = []
    all_recips = []

    for dg, min_base_hrs in [("weekday", 20.0), ("weekend", 10.0)]:
        # 1. Eligible donor trims within day_group (exclude M35 sole link, >= min_base_hrs, 0 hours moved > p75)
        donors_pool = scenarios_df[
            (scenarios_df["day_group"] == dg)
            & (scenarios_df["review_category"] == f_cat)
            & (scenarios_df["route"] != "M35")
            & (scenarios_df["base_service_hours"] >= min_base_hrs)
            & (scenarios_df["scenario_trip_change_pct"] < 0)
            & (scenarios_df["guardrail_status"] == "ok")
            & (scenarios_df["high_demand_hours_delta"] == 0)
        ].copy()

        chosen_donors = []
        for (r, tb), grp in donors_pool.groupby(["route", "time_band"]):
            excl = float(grp["exclusive_stop_share"].iloc[0])
            target_pct = -20 if excl < c_cfg["moderate_exclusive_stop_share"] else -10
            pick = grp[grp["scenario_trip_change_pct"] == target_pct]
            if pick.empty:
                pick = grp[grp["scenario_trip_change_pct"] == -10]
            if not pick.empty:
                chosen_donors.append(pick.iloc[0])

        donor_df = (
            pd.DataFrame(chosen_donors)
            .merge(
                review_df[
                    [
                        "route",
                        "day_group",
                        "time_band",
                        "high_demand_freq_pct",
                        "top_shared_corridor_partner",
                        "top_shared_corridor_share",
                    ]
                ],
                on=["route", "day_group", "time_band"],
                how="left",
            )
            .sort_values("base_riders_per_service_hour", ascending=True)
            .reset_index(drop=True)
        )
        freed_hrs = round(float(-donor_df["delta_service_hours"].sum()), 2)

        # 2. Eligible recipient additions within same day_group (high riders/trip cells >= 40 riders/svc-hr)
        recip_pool = scenarios_df[
            (scenarios_df["day_group"] == dg)
            & (scenarios_df["review_category"] == m_cat)
            & (scenarios_df["scenario_trip_change_pct"].isin([10, 20]))
            & (scenarios_df["base_riders_per_service_hour"] >= 40.0)
        ].merge(
            review_df[
                [
                    "route",
                    "day_group",
                    "time_band",
                    "high_demand_freq_pct",
                    "top_shared_corridor_partner",
                    "top_shared_corridor_share",
                ]
            ],
            on=["route", "day_group", "time_band"],
            how="left",
        )

        best_per_cell = []
        for (r, tb), grp in recip_pool.groupby(["route", "time_band"]):
            freq = float(grp["high_demand_freq_pct"].iloc[0])
            want_pct = 20 if freq >= 85.0 else 10
            pick = grp[grp["scenario_trip_change_pct"] == want_pct]
            if pick.empty:
                pick = grp.iloc[[0]]
            best_per_cell.append(pick.iloc[0].copy())

        recip_ranked = (
            pd.DataFrame(best_per_cell)
            .sort_values(
                ["high_demand_freq_pct", "base_riders_per_service_hour"],
                ascending=[False, False],
            )
            .reset_index(drop=True)
        )

        allocated = []
        remaining = freed_hrs
        for _, row in recip_ranked.iterrows():
            cost = float(row["delta_service_hours"])
            if cost <= remaining + 1e-6:
                allocated.append(row)
                remaining = round(remaining - cost, 2)
            else:
                alt = recip_pool[
                    (recip_pool["route"] == row["route"])
                    & (recip_pool["time_band"] == row["time_band"])
                    & (recip_pool["scenario_trip_change_pct"] == 10)
                ]
                if not alt.empty:
                    alt_row = alt.iloc[0].copy()
                    alt_cost = float(alt_row["delta_service_hours"])
                    if alt_cost <= remaining + 1e-6:
                        allocated.append(alt_row)
                        remaining = round(remaining - alt_cost, 2)

        recip_df = pd.DataFrame(allocated)
        assert round(float(recip_df["delta_service_hours"].sum() + donor_df["delta_service_hours"].sum()), 2) <= 0.0, (
            f"day_group={dg} exceeded budget neutrality"
        )
        all_donors.append(donor_df)
        all_recips.append(recip_df)

    donor_all = pd.concat(all_donors, ignore_index=True)
    recip_all = pd.concat(all_recips, ignore_index=True)

    donor_all["reallocation_role"] = "donor_trim"
    recip_all["reallocation_role"] = "recipient_add"
    donor_all["rationale"] = [
        (
            f"Low {r['day_group']} riders/svc-hr ({r['base_riders_per_service_hour']:.1f} riders/svc-hr, "
            f"{r['high_demand_freq_pct']:.1f}% hrs >0.96x p75); {r['exclusive_stop_share']*100:.1f}% exclusive stops -> "
            f"{r['scenario_trip_change_pct']}% trips shifts {-r['delta_service_hours']:.1f} svc-hrs over "
            f"{int(r['days_in_group'])}d ({-r['delta_service_hours_per_day']:.1f}/day, "
            f"{-r['pct_of_day_group_service_hours']:.2f}% of {r['day_group']} svc-hrs) with 0 hours moving >0.96x p75."
        )
        for _, r in donor_all.iterrows()
    ]
    recip_all["rationale"] = [
        (
            f"High {r['day_group']} riders per trip ({r['high_demand_freq_pct']:.1f}% hrs >0.96x p75, "
            f"{r['base_riders_per_service_hour']:.1f} riders/svc-hr); +{r['scenario_trip_change_pct']}% trips adds "
            f"+{r['delta_service_hours']:.1f} svc-hrs over {int(r['days_in_group'])}d (+{r['delta_service_hours_per_day']:.1f}/day); "
            f"with riders held constant, {-int(r['high_demand_hours_delta'])} "
            f"{'hour falls' if -int(r['high_demand_hours_delta']) == 1 else 'hours fall'} below 0.96x p75."
        )
        for _, r in recip_all.iterrows()
    ]

    cols = [
        "reallocation_role",
        "day_group",
        "days_in_group",
        "route",
        "time_band",
        "group_id",
        "exclusive_stop_share",
        "high_demand_freq_pct",
        "scenario_trip_change_pct",
        "base_trips",
        "new_trips",
        "delta_trips",
        "base_service_hours",
        "new_service_hours",
        "delta_service_hours",
        "delta_service_hours_per_day",
        "pct_of_day_group_service_hours",
        "pct_of_14day_network_service_hours",
        "constant_pred_ridership",
        "base_riders_per_trip",
        "new_riders_per_trip",
        "base_riders_per_service_hour",
        "new_riders_per_service_hour",
        "base_high_demand_hours",
        "sim_high_demand_hours",
        "high_demand_hours_delta",
        "rationale",
    ]
    plan_df = pd.concat([donor_all[cols], recip_all[cols]], ignore_index=True)

    net_svc = round(float(plan_df["delta_service_hours"].sum()), 2)
    assert net_svc <= 0.0, f"Plan exceeded budget neutrality: net_service_hours={net_svc}"
    return plan_df


def plot_reallocation_summary(plan_df: pd.DataFrame, out_path: Path, preds_df: pd.DataFrame) -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    donors = plan_df[plan_df["reallocation_role"] == "donor_trim"]
    recips = plan_df[plan_df["reallocation_role"] == "recipient_add"]

    total_14d_svc = float(preds_df["service_hours"].sum())
    freed_hrs = float(-donors["delta_service_hours"].sum())
    added_hrs = float(recips["delta_service_hours"].sum())
    net_hrs = added_hrs - freed_hrs
    below_thresh = int(-recips["high_demand_hours_delta"].sum())
    created_hd = int(donors["high_demand_hours_delta"].sum())
    freed_pct = freed_hrs / total_14d_svc * 100.0

    fig, axes = plt.subplots(1, 2, figsize=(14.0, 5.5))

    # Left panel: Service-hours transferred over the 14-day period by time_band & day_group
    bands = ["early_morning", "morning_peak", "midday", "evening_peak", "night"]
    wkd_d = [float(donors[(donors["time_band"] == b) & (donors["day_group"] == "weekday")]["delta_service_hours"].sum()) for b in bands]
    wke_d = [float(donors[(donors["time_band"] == b) & (donors["day_group"] == "weekend")]["delta_service_hours"].sum()) for b in bands]
    wkd_r = [float(recips[(recips["time_band"] == b) & (recips["day_group"] == "weekday")]["delta_service_hours"].sum()) for b in bands]
    wke_r = [float(recips[(recips["time_band"] == b) & (recips["day_group"] == "weekend")]["delta_service_hours"].sum()) for b in bands]

    x = np.arange(len(bands))
    w = 0.55
    axes[0].bar(x, wkd_d, width=w, color="#b45309", label=f"Weekday trims (-{-sum(wkd_d):.0f} hrs / 10d)")
    axes[0].bar(x, wke_d, bottom=wkd_d, width=w, color="#f59e0b", label=f"Weekend trims (-{-sum(wke_d):.0f} hrs / 4d)")
    axes[0].bar(x, wkd_r, width=w, color="#0b5394", label=f"Weekday adds (+{sum(wkd_r):.0f} hrs / 10d)")
    axes[0].bar(x, wke_r, bottom=wkd_r, width=w, color="#60a5fa", label=f"Weekend adds (+{sum(wke_r):.0f} hrs / 4d)")
    axes[0].axhline(0, color="black", linewidth=0.9)

    tot_d = [a + b for a, b in zip(wkd_d, wke_d)]
    tot_r = [a + b for a, b in zip(wkd_r, wke_r)]
    for idx, (vd, vr) in enumerate(zip(tot_d, tot_r)):
        if vd < -1.0:
            axes[0].text(idx, vd - 15, f"{vd:.0f}", ha="center", va="top", fontsize=8.5, fontweight="bold")
        if vr > 1.0:
            axes[0].text(idx, vr + 12, f"+{vr:.0f}", ha="center", va="bottom", fontsize=8.5, fontweight="bold")

    axes[0].set_xticks(x)
    axes[0].set_xticklabels(["Early\nMorning", "Morning\nPeak", "Midday", "Evening\nPeak", "Night"])
    axes[0].set_ylim(min(tot_d) * 1.28 - 40, max(max(tot_r) * 1.25 + 40, 260))
    axes[0].set_ylabel("Service-Hours Change Over 14 Days (Oct 18–31)")
    axes[0].set_title(
        f"{freed_hrs:.1f} Hrs Moved Over 14 Days ({freed_pct:.2f}% of Network, Net {net_hrs:+.1f} Hrs)"
    )
    axes[0].grid(True, axis="y", alpha=0.3)
    axes[0].legend(loc="upper left", frameon=True, fontsize=8)

    # Right panel: Top cells with high riders per trip (before vs after under constant riders)
    top_recips = recips.sort_values("high_demand_hours_delta").head(12).iloc[::-1]
    ylabels = [
        f"{r['route']} ({'wkday' if r['day_group'] == 'weekday' else 'wkend'}, {r['time_band'][:3]}) +{r['scenario_trip_change_pct']}%"
        for _, r in top_recips.iterrows()
    ]
    y = np.arange(len(top_recips))
    axes[1].barh(y - 0.18, top_recips["base_high_demand_hours"], height=0.34, color="#9ca3af", label="Before Added Trips")
    axes[1].barh(y + 0.18, top_recips["sim_high_demand_hours"], height=0.34, color="#16a34a", label="After (Riders Held Constant)")
    axes[1].set_yticks(y)
    axes[1].set_yticklabels(ylabels, fontsize=8)
    axes[1].set_xlabel("Hours Exceeding High-Demand Threshold (Oct 18–31)")
    axes[1].set_title(
        f"With Riders Constant, {below_thresh} Hours Fall Below Threshold ({created_hd} Added)"
    )
    axes[1].grid(True, axis="x", alpha=0.3)
    axes[1].legend(frameon=True, fontsize=8.5)

    fig.suptitle(
        "Step 9 Budget-Neutral Reallocation (10 Weekdays + 4 Weekend Days, Oct 18–31; Riders Held Constant)",
        fontsize=11,
        fontweight="bold",
        y=0.99,
    )
    plt.tight_layout(rect=[0, 0, 1, 0.94])
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description="Run Steps 8-9 schedule scenarios, merge checks, and reallocation.")
    parser.add_argument("--config", default=str(CONFIG_DEFAULT), help="Path to optimization thresholds JSON config")
    args = parser.parse_args()

    cfg = load_config(Path(args.config))
    review_df = pd.read_csv(TAB_DIR / "m3_step7_review_list.csv")
    preds_df = pd.read_csv(TAB_DIR / "m3_october_predictions.csv")

    scenarios_df = simulate_trip_scenarios(review_df, preds_df, cfg)
    scenarios_path = TAB_DIR / "m3_step8_candidate_scenarios.csv"
    scenarios_df.to_csv(scenarios_path, index=False)

    merge_df = evaluate_shared_corridor_merges(preds_df, cfg)
    merge_path = TAB_DIR / "m3_step8_shared_corridor_merge_checks.csv"
    merge_df.to_csv(merge_path, index=False)

    plan_df = build_budget_neutral_reallocation(review_df, scenarios_df, cfg)
    plan_path = TAB_DIR / "m3_step9_budget_neutral_reallocation.csv"
    plan_df.to_csv(plan_path, index=False)

    fig_path = FIG_DIR / "m3_step9_reallocation_summary.png"
    plot_reallocation_summary(plan_df, fig_path, preds_df)

    total_14d_svc = float(preds_df["service_hours"].sum())
    donors = plan_df[plan_df["reallocation_role"] == "donor_trim"]
    recips = plan_df[plan_df["reallocation_role"] == "recipient_add"]
    freed = float(-donors["delta_service_hours"].sum())
    added = float(recips["delta_service_hours"].sum())
    print(f"Saved {len(scenarios_df)} candidate scenarios -> {scenarios_path}")
    print(f"Saved {len(merge_df)} shared_corridor merge checks -> {merge_path}")
    print(
        f"Saved budget-neutral reallocation over 14 days ({len(donors)} donors -{freed:.2f} hrs "
        f"[{freed/total_14d_svc*100:.2f}% of {total_14d_svc:,.1f} total svc-hrs], "
        f"{len(recips)} recipients +{added:.2f} hrs, net={added - freed:+.2f} hrs) -> {plan_path}"
    )
    for dg in ("weekday", "weekend"):
        dd = donors[donors["day_group"] == dg]
        rr = recips[recips["day_group"] == dg]
        dg_tot = float(preds_df.loc[preds_df["day_group"] == dg, "service_hours"].sum())
        days_n = int(preds_df.loc[preds_df["day_group"] == dg, "date"].nunique())
        df_h = float(-dd["delta_service_hours"].sum())
        da_h = float(rr["delta_service_hours"].sum())
        print(
            f"  {dg} ({days_n}d): -{df_h:.2f} hrs ({-df_h/days_n:.2f}/day, {df_h/dg_tot*100:.2f}% of {dg_tot:,.1f} {dg} svc-hrs) "
            f"-> +{da_h:.2f} hrs (+{da_h/days_n:.2f}/day), net={da_h - df_h:+.2f} hrs"
        )
    print(
        f"With riders held constant, {-int(recips['high_demand_hours_delta'].sum())} hours fall below the high-demand threshold "
        f"(donor hours moving above: {int(donors['high_demand_hours_delta'].sum())})."
    )
    print(f"Saved figure -> {fig_path}")


if __name__ == "__main__":
    main()
