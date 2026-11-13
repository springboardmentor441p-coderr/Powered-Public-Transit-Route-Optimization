"""
Milestone 3 — Steps 8 & 9: Service Scenarios, Shared-Corridor Merge Checks &
Budget-Neutral Service-Hour Reallocation Plan

Step 8:
  - Evaluates +/-10% and +/-20% trip changes across all underused and high-demand
    (route, time_band) candidates from Step 7 under the explicit assumption that
    ridership remains constant when trips change.
  - Evaluates merge/consolidation feasibility strictly on shared_corridor route pairs
    (explicitly excluding same_family variants such as M15/M15+, M34+/M34A+, M14A+/M14D+).

Step 9:
  - Builds one budget-neutral service reallocation plan transferring scheduled
    service-hours from low-productivity night/early-morning corridors to congested
    peak and midday corridors (net service-hour change <= 0.0), respecting stop
    exclusivity guardrails and minimum hourly trip floors.

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
    """Test +/-10% and +/-20% trip changes per Step 7 candidate (underused & high_demand)."""
    rules = cfg["step8_9_adjustment_rules"]
    c_cfg = cfg["step7_review_thresholds"]["coverage_guardrails"]
    deltas = rules["scenario_trip_changes_pct"]
    floor_per_hr = int(rules["min_trips_per_active_hour_floor"])

    candidates = review_df[
        review_df["review_category"].isin(["underused_candidate", "high_demand_candidate"])
    ].copy()

    rows = []
    for _, cand in candidates.iterrows():
        r = cand["route"]
        tb = cand["time_band"]
        cat = cand["review_category"]
        act_hrs = int(cand["active_hours"])
        base_trips = int(cand["total_trips_running"])
        base_svc_hrs = float(cand["total_service_hours"])
        tot_riders = float(cand["total_pred_ridership"])
        base_hd_hrs = int(cand["high_demand_hours"])
        excl_share = float(cand["exclusive_stop_share"])

        sub_hrs = preds_df[(preds_df["route"] == r) & (preds_df["time_band"] == tb)]
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
                guardrail_status = "warning_creates_new_high_demand_hours"
            else:
                guardrail_status = "ok"

            rows.append(
                {
                    "route": r,
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
    """Construct one budget-neutral service reallocation plan (net service_hours <= 0)."""
    c_cfg = cfg["step7_review_thresholds"]["coverage_guardrails"]
    high_excl = c_cfg["high_exclusive_stop_share"]

    # 1. Select eligible donor scenarios (underused_candidate, exclude M35 bridge lifeline, >=30 base hrs)
    donors_pool = scenarios_df[
        (scenarios_df["review_category"] == "underused_candidate")
        & (scenarios_df["route"] != "M35")
        & (scenarios_df["base_service_hours"] >= 30.0)
        & (scenarios_df["scenario_trip_change_pct"] < 0)
        & (scenarios_df["guardrail_status"] == "ok")
        & (scenarios_df["high_demand_hours_delta"] == 0)
    ].copy()

    # For each donor (route, time_band), choose -20% if low exclusivity (<0.40) and -10% otherwise
    chosen_donors = []
    for (r, tb), grp in donors_pool.groupby(["route", "time_band"]):
        excl = float(grp["exclusive_stop_share"].iloc[0])
        target_pct = -20 if excl < 0.40 else -10
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
                    "time_band",
                    "high_demand_freq_pct",
                    "top_shared_corridor_partner",
                    "top_shared_corridor_share",
                ]
            ],
            on=["route", "time_band"],
            how="left",
        )
        .sort_values("base_riders_per_service_hour", ascending=True)
        .reset_index(drop=True)
    )

    total_freed_hours = round(float(-donor_df["delta_service_hours"].sum()), 2)

    # 2. Select highest-priority recipients sorted by crowding pressure, without exceeding donor budget
    recip_pool = scenarios_df[
        (scenarios_df["review_category"] == "high_demand_candidate")
        & (scenarios_df["scenario_trip_change_pct"].isin([10, 20]))
        & (scenarios_df["base_riders_per_service_hour"] >= 40.0)
    ].merge(
        review_df[
            [
                "route",
                "time_band",
                "high_demand_freq_pct",
                "top_shared_corridor_partner",
                "top_shared_corridor_share",
            ]
        ],
        on=["route", "time_band"],
        how="left",
    )

    # Pick one primary action per high-demand candidate: +20% if >=85% high-demand hours, else +10%
    best_per_cell = []
    for (r, tb), grp in recip_pool.groupby(["route", "time_band"]):
        freq = float(grp["high_demand_freq_pct"].iloc[0])
        want_pct = 20 if freq >= 85.0 else 10
        pick = grp[grp["scenario_trip_change_pct"] == want_pct]
        if pick.empty:
            pick = grp.iloc[[0]]
        row = pick.iloc[0].copy()
        row["relief_efficiency"] = abs(row["high_demand_hours_delta"]) / max(
            row["delta_service_hours"], 0.1
        )
        best_per_cell.append(row)

    recip_ranked = (
        pd.DataFrame(best_per_cell)
        .sort_values(
            ["high_demand_freq_pct", "base_riders_per_service_hour"],
            ascending=[False, False],
        )
        .reset_index(drop=True)
    )

    # Allocate recipients up to total_freed_hours; check both desired +20% and fallback +10% if tight near cap
    allocated_rows = []
    remaining_budget = total_freed_hours

    for _, row in recip_ranked.iterrows():
        cost = float(row["delta_service_hours"])
        if cost <= remaining_budget + 1e-6:
            allocated_rows.append(row)
            remaining_budget = round(remaining_budget - cost, 2)
        else:
            # Try +10% step if +20% was too large for remaining budget
            alt = recip_pool[
                (recip_pool["route"] == row["route"])
                & (recip_pool["time_band"] == row["time_band"])
                & (recip_pool["scenario_trip_change_pct"] == 10)
            ]
            if not alt.empty:
                alt_row = alt.iloc[0].copy()
                alt_cost = float(alt_row["delta_service_hours"])
                if alt_cost <= remaining_budget + 1e-6:
                    allocated_rows.append(alt_row)
                    remaining_budget = round(remaining_budget - alt_cost, 2)

    recip_df = pd.DataFrame(allocated_rows)

    donor_df["reallocation_role"] = "donor_trim"
    recip_df["reallocation_role"] = "recipient_add"
    donor_df["rationale"] = [
        (
            f"Low October load ({r['base_riders_per_service_hour']:.1f} riders/svc-hr, "
            f"{r['high_demand_freq_pct']:.1f}% high-demand hrs); "
            f"{r['exclusive_stop_share']*100:.1f}% exclusive stops -> {r['scenario_trip_change_pct']}% trips "
            f"frees {-r['delta_service_hours']:.1f} svc-hrs with 0 new high-demand hours created."
        )
        for _, r in donor_df.iterrows()
    ]
    recip_df["rationale"] = [
        (
            f"Persistent crowding ({r['high_demand_freq_pct']:.1f}% high-demand hrs, "
            f"{r['base_riders_per_service_hour']:.1f} riders/svc-hr); +{r['scenario_trip_change_pct']}% trips "
            f"uses +{r['delta_service_hours']:.1f} svc-hrs and relieves {-r['high_demand_hours_delta']} high-demand hrs."
        )
        for _, r in recip_df.iterrows()
    ]

    cols = [
        "reallocation_role",
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
    plan_df = pd.concat([donor_df[cols], recip_df[cols]], ignore_index=True)

    # Assert strict budget-neutrality
    net_svc = round(float(plan_df["delta_service_hours"].sum()), 2)
    assert net_svc <= 0.0, f"Plan exceeded budget neutrality: net_service_hours={net_svc}"
    return plan_df


def plot_reallocation_summary(plan_df: pd.DataFrame, out_path: Path) -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    donors = plan_df[plan_df["reallocation_role"] == "donor_trim"]
    recips = plan_df[plan_df["reallocation_role"] == "recipient_add"]

    freed_hrs = float(-donors["delta_service_hours"].sum())
    added_hrs = float(recips["delta_service_hours"].sum())
    net_hrs = added_hrs - freed_hrs
    relieved_hd = int(-recips["high_demand_hours_delta"].sum())
    created_hd = int(donors["high_demand_hours_delta"].sum())

    fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.4))

    # Left panel: Service-hours balance by role & time_band
    bands = ["early_morning", "morning_peak", "midday", "evening_peak", "night"]
    donor_by_band = [
        float(donors.loc[donors["time_band"] == b, "delta_service_hours"].sum()) for b in bands
    ]
    recip_by_band = [
        float(recips.loc[recips["time_band"] == b, "delta_service_hours"].sum()) for b in bands
    ]
    x = np.arange(len(bands))
    w = 0.55
    b_d = axes[0].bar(x, donor_by_band, width=w, color="#b45309", label=f"Freed from Underused (-{freed_hrs:.1f} hrs)")
    b_r = axes[0].bar(x, recip_by_band, width=w, color="#0b5394", label=f"Added to High-Demand (+{added_hrs:.1f} hrs)")
    axes[0].axhline(0, color="black", linewidth=0.9)
    for bars in (b_d, b_r):
        for bar in bars:
            val = bar.get_height()
            if abs(val) > 1.0:
                offset = 18 if val > 0 else -38
                axes[0].text(
                    bar.get_x() + bar.get_width() / 2,
                    val + offset,
                    f"{val:+.0f}",
                    ha="center",
                    va="bottom" if val > 0 else "top",
                    fontsize=8.5,
                    fontweight="bold",
                )
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(["Early\nMorning", "Morning\nPeak", "Midday", "Evening\nPeak", "Night"])
    min_y = min(donor_by_band) if donor_by_band else -100.0
    max_y = max(recip_by_band) if recip_by_band else 100.0
    axes[0].set_ylim(min(min_y * 1.28, -530), max(max_y * 1.25, 560))
    axes[0].set_ylabel("2-Week Service-Hours Change (Oct 18–31 GTFS)")
    axes[0].set_title(
        f"Budget-Neutral Reallocation by Time Band (Net Change: {net_hrs:+.1f} hrs)"
    )
    axes[0].grid(True, axis="y", alpha=0.3)
    axes[0].legend(loc="upper left", frameon=True, fontsize=8.5)

    # Right panel: Top recipient high-demand hour relief
    top_recips = recips.sort_values("high_demand_hours_delta").head(12).iloc[::-1]
    ylabels = [f"{r['route']} ({r['time_band'][:3]}) +{r['scenario_trip_change_pct']}%" for _, r in top_recips.iterrows()]
    y = np.arange(len(top_recips))
    axes[1].barh(y - 0.18, top_recips["base_high_demand_hours"], height=0.34, color="#9ca3af", label="Before Reallocation")
    axes[1].barh(y + 0.18, top_recips["sim_high_demand_hours"], height=0.34, color="#16a34a", label="After Added Trips")
    axes[1].set_yticks(y)
    axes[1].set_yticklabels(ylabels, fontsize=8.5)
    axes[1].set_xlabel("Predicted High-Demand Hours (2-Week Window)")
    axes[1].set_title(
        f"{len(top_recips)} Recipient Corridors: {relieved_hd} High-Demand Hrs Relieved ({created_hd} Added)"
    )
    axes[1].grid(True, axis="x", alpha=0.3)
    axes[1].legend(frameon=True, fontsize=8.5)

    fig.suptitle(
        "Step 9 Budget-Neutral Reallocation Plan — Assumes Ridership Stays Constant When Trips Change",
        fontsize=11.5,
        fontweight="bold",
        y=0.99,
    )
    plt.tight_layout(rect=[0, 0, 1, 0.95])
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
    plot_reallocation_summary(plan_df, fig_path)

    donors = plan_df[plan_df["reallocation_role"] == "donor_trim"]
    recips = plan_df[plan_df["reallocation_role"] == "recipient_add"]
    freed = float(-donors["delta_service_hours"].sum())
    added = float(recips["delta_service_hours"].sum())
    print(f"Saved {len(scenarios_df)} candidate scenarios -> {scenarios_path}")
    print(f"Saved {len(merge_df)} shared_corridor merge checks -> {merge_path}")
    print(
        f"Saved budget-neutral reallocation ({len(donors)} donors -{freed:.2f} hrs, "
        f"{len(recips)} recipients +{added:.2f} hrs, net={added - freed:+.2f} hrs) -> {plan_path}"
    )
    print(f"High-demand hours relieved: {-int(recips['high_demand_hours_delta'].sum())} (created on donors: {int(donors['high_demand_hours_delta'].sum())})")
    print(f"Saved figure -> {fig_path}")


if __name__ == "__main__":
    main()
