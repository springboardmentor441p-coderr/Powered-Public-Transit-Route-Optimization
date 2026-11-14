"""
Milestone 3 — Steps 8 & 9: Service Scenarios, Shared-Corridor Merge Checks &
Budget-Neutral Service-Hour Reallocation Plan

Step 8:
  - Evaluates +/-10% and +/-20% trip changes across all fewer_trips_candidate and
    more_trips_candidate (route, day_group, time_band) cells from Step 7 (observed
    Aug-Oct 2026 typical days, >= 20 days & >= 2.0 trips/day) under the explicit
    assumption that ridership remains constant when trips change.
  - Evaluates merge/consolidation feasibility strictly on shared_corridor route pairs
    (explicitly excluding same_family variants such as M15/M15+, M34+/M34A+, M14A+/M14D+).

Step 9:
  - Builds one budget-neutral service reallocation plan transferring scheduled
    service-hours within weekday (63 typical days) and weekend (27 typical days) budgets
    from low riders/svc-hr cells to cells with high riders per trip (net service-hour
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
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.build_review_list import (
    classify_overlap_pair,
    load_config,
    load_observed_review_window_hourly,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DEFAULT = ROOT / "configs" / "optimization_thresholds.json"
TAB_DIR = ROOT / "reports" / "tables"
FIG_DIR = ROOT / "reports" / "figures"


def compute_cell_scenario_effect(
    *,
    route: str,
    day_group: str,
    days_count: int,
    days_in_day_group: int,
    time_band: str,
    review_category: str,
    group_id: int,
    exclusive_stop_share: float,
    active_hours: int,
    base_trips: int,
    base_service_hours: float,
    constant_obs_ridership: float,
    base_riders_per_trip: float,
    base_riders_per_service_hour: float,
    base_high_demand_hours: int,
    hourly_trips: np.ndarray,
    hourly_riders: np.ndarray,
    hourly_p75: np.ndarray,
    dg_svc_total: float,
    net_window_svc: float,
    pct: float,
    floor_per_hr: int,
    high_excl_threshold: float,
) -> dict:
    """Compute constant-ridership trip & service-hour scenario metrics for one cell."""
    min_trips_floor = active_hours * floor_per_hr
    scale_target = 1.0 + pct / 100.0
    new_trips = int(max(min_trips_floor, round(base_trips * scale_target)))
    actual_scale = new_trips / base_trips if base_trips > 0 else 1.0
    new_svc_hrs = round(base_service_hours * actual_scale, 2)
    delta_trips = new_trips - base_trips
    delta_svc_hrs = round(new_svc_hrs - base_service_hours, 2)

    # Constant ridership assumption: riders stay the same when trips change
    new_r_per_trip = round(constant_obs_ridership / new_trips, 2) if new_trips > 0 else np.nan
    new_r_per_svch = round(constant_obs_ridership / new_svc_hrs, 2) if new_svc_hrs > 0 else np.nan

    # Recompute hourly p75 threshold exceedance under scaled trips
    sim_trips_hr = np.maximum(floor_per_hr, hourly_trips * actual_scale)
    sim_ratio_hr = hourly_riders / sim_trips_hr
    sim_hd_hrs = int((sim_ratio_hr > hourly_p75).sum())
    hd_delta = sim_hd_hrs - base_high_demand_hours

    if pct < 0 and exclusive_stop_share >= high_excl_threshold and abs(pct) > 10:
        guardrail_status = "exceeds_10pct_exclusivity_guardrail"
    elif pct < 0 and hd_delta > 0:
        guardrail_status = "warning_pushes_hours_above_threshold"
    else:
        guardrail_status = "ok"

    return {
        "route": route,
        "day_group": day_group,
        "days_count": int(days_count),
        "days_in_day_group": int(days_in_day_group),
        "time_band": time_band,
        "review_category": review_category,
        "group_id": int(group_id),
        "exclusive_stop_share": float(exclusive_stop_share),
        "scenario_trip_change_pct": pct,
        "effective_trip_change_pct": round((actual_scale - 1.0) * 100.0, 2),
        "base_trips": int(base_trips),
        "new_trips": new_trips,
        "delta_trips": delta_trips,
        "base_service_hours": float(base_service_hours),
        "new_service_hours": new_svc_hrs,
        "delta_service_hours": delta_svc_hrs,
        "delta_service_hours_per_day": (
            round(delta_svc_hrs / days_count, 2) if days_count > 0 else np.nan
        ),
        "pct_of_day_group_service_hours": (
            round(delta_svc_hrs / dg_svc_total * 100.0, 3) if dg_svc_total > 0 else np.nan
        ),
        "pct_of_window_network_service_hours": (
            round(delta_svc_hrs / net_window_svc * 100.0, 3) if net_window_svc > 0 else np.nan
        ),
        "constant_obs_ridership": float(constant_obs_ridership),
        "base_riders_per_trip": float(base_riders_per_trip),
        "new_riders_per_trip": new_r_per_trip,
        "base_riders_per_service_hour": float(base_riders_per_service_hour),
        "new_riders_per_service_hour": new_r_per_svch,
        "base_high_demand_hours": int(base_high_demand_hours),
        "sim_high_demand_hours": sim_hd_hrs,
        "high_demand_hours_delta": hd_delta,
        "guardrail_status": guardrail_status,
    }


def simulate_trip_scenarios(
    review_df: pd.DataFrame, obs_df: pd.DataFrame, cfg: dict
) -> pd.DataFrame:
    """Test +/-10% and +/-20% trip changes per Step 7 candidate (route, day_group, time_band)."""
    rules = cfg["step8_9_adjustment_rules"]
    c_cfg = cfg["step7_review_thresholds"]["coverage_guardrails"]
    f_cat = cfg["step7_review_thresholds"]["fewer_trips_screening"]["category_name"]
    m_cat = cfg["step7_review_thresholds"]["more_trips_screening"]["category_name"]
    deltas = rules["scenario_trip_changes_pct"]
    floor_per_hr = int(rules["min_trips_per_active_hour_floor"])

    dg_svc_totals = obs_df.groupby("day_group")["service_hours"].sum().to_dict()
    net_window_svc = float(obs_df["service_hours"].sum())

    candidates = review_df[review_df["review_category"].isin([f_cat, m_cat])].copy()

    rows = []
    for _, cand in candidates.iterrows():
        r = cand["route"]
        tb = cand["time_band"]
        dg = cand["day_group"]
        sub_hrs = obs_df[
            (obs_df["route"] == r)
            & (obs_df["time_band"] == tb)
            & (obs_df["day_group"] == dg)
        ]

        for pct in deltas:
            rows.append(
                compute_cell_scenario_effect(
                    route=r,
                    day_group=dg,
                    days_count=int(cand["days_count"]),
                    days_in_day_group=int(cand["days_in_day_group"]),
                    time_band=tb,
                    review_category=cand["review_category"],
                    group_id=int(cand["group_id"]),
                    exclusive_stop_share=float(cand["exclusive_stop_share"]),
                    active_hours=int(cand["active_hours"]),
                    base_trips=int(cand["total_trips_running"]),
                    base_service_hours=float(cand["total_service_hours"]),
                    constant_obs_ridership=float(cand["total_obs_ridership"]),
                    base_riders_per_trip=float(cand["obs_riders_per_trip"]),
                    base_riders_per_service_hour=float(cand["obs_riders_per_service_hour"]),
                    base_high_demand_hours=int(cand["high_demand_hours"]),
                    hourly_trips=sub_hrs["trips_running"].values,
                    hourly_riders=sub_hrs["ridership"].values,
                    hourly_p75=sub_hrs["threshold_p75"].values,
                    dg_svc_total=float(dg_svc_totals[dg]),
                    net_window_svc=net_window_svc,
                    pct=pct,
                    floor_per_hr=floor_per_hr,
                    high_excl_threshold=float(c_cfg["high_exclusive_stop_share"]),
                )
            )

    return pd.DataFrame(rows)


def evaluate_shared_corridor_merges(
    obs_df: pd.DataFrame, cfg: dict
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
        obs_df.groupby("route")
        .agg(
            tot_riders=("ridership", "sum"),
            tot_trips=("trips_running", "sum"),
            tot_svc_hrs=("service_hours", "sum"),
            high_hrs=("obs_high_demand_per_trip", "sum"),
            n_hrs=("ridership", "size"),
            n_days=("date", "nunique"),
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

        sm_riders_day = float(route_agg.loc[r_sm, "tot_riders"]) / float(route_agg.loc[r_sm, "n_days"])
        lg_riders_day = float(route_agg.loc[r_lg, "tot_riders"]) / float(route_agg.loc[r_lg, "n_days"])
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
            verdict = "keep_separate_unique_stops"
            reason = (
                f"{r_sm} also serves {unique_stops_sm} stops that {r_lg} doesn't "
                f"({sm_excl*100:.1f}% exclusive stops across the network). "
                f"Merging would take this service away from those stops."
            )
        elif meets_40 and min(sm_riders_day, lg_riders_day) < 3500:
            verdict = "candidate_for_offpeak_consolidation_study"
            reason = (
                f"High shared_corridor overlap ({ov_share*100:.1f}%) with lighter load on "
                f"{r_sm} (~{sm_riders_day:,.0f} obs riders/day, {sm_high:.0f}% high-demand hrs, "
                f"Group {sm_grp}); {r_sm} also serves {unique_stops_sm} stops that {r_lg} doesn't. "
                f"Check off-peak trip options on the shared section while keeping those stops served."
            )
        else:
            verdict = "monitor_shared_corridor_no_merge"
            reason = (
                f"{r_sm} also serves {unique_stops_sm} stops that {r_lg} doesn't "
                f"({ov_share*100:.1f}% shared stops; {r_sm} ~{sm_riders_day:,.0f}/day vs "
                f"{r_lg} ~{lg_riders_day:,.0f}/day). Selective trip changes fit better than merging."
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
                "smaller_route_obs_riders_per_day": round(sm_riders_day, 0),
                "larger_route_obs_riders_per_day": round(lg_riders_day, 0),
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

    for dg in ["weekday", "weekend"]:
        # 1. Eligible donor trims within day_group (exclude M35 sole link, 0 hours moving > p75)
        donors_pool = scenarios_df[
            (scenarios_df["day_group"] == dg)
            & (scenarios_df["review_category"] == f_cat)
            & (scenarios_df["route"] != "M35")
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
            want_pct = 20 if freq >= 80.0 else 10
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
            f"Low {r['day_group']} riders/svc-hr over {int(r['days_count'])}d ({r['base_riders_per_service_hour']:.1f} riders/svc-hr, "
            f"{r['high_demand_freq_pct']:.1f}% hrs >p75); {r['exclusive_stop_share']*100:.1f}% exclusive stops -> "
            f"{r['scenario_trip_change_pct']}% trips shifts {-r['delta_service_hours']:.1f} svc-hrs over "
            f"{int(r['days_count'])}d ({-r['delta_service_hours_per_day']:.1f}/day, "
            f"{-r['pct_of_day_group_service_hours']:.2f}% of {r['day_group']} svc-hrs) with 0 hours moving >p75."
        )
        for _, r in donor_all.iterrows()
    ]
    recip_all["rationale"] = [
        (
            f"High {r['day_group']} riders per trip over {int(r['days_count'])}d ({r['high_demand_freq_pct']:.1f}% hrs >p75, "
            f"{r['base_riders_per_service_hour']:.1f} riders/svc-hr); +{r['scenario_trip_change_pct']}% trips adds "
            f"+{r['delta_service_hours']:.1f} svc-hrs over {int(r['days_count'])}d (+{r['delta_service_hours_per_day']:.1f}/day); "
            f"with riders held constant, {-int(r['high_demand_hours_delta'])} "
            f"{'hour falls' if -int(r['high_demand_hours_delta']) == 1 else 'hours fall'} below p75."
        )
        for _, r in recip_all.iterrows()
    ]

    cols = [
        "reallocation_role",
        "day_group",
        "days_count",
        "days_in_day_group",
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
        "pct_of_window_network_service_hours",
        "constant_obs_ridership",
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


def plot_reallocation_summary(plan_df: pd.DataFrame, out_path: Path, obs_df: pd.DataFrame) -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    donors = plan_df[plan_df["reallocation_role"] == "donor_trim"]
    recips = plan_df[plan_df["reallocation_role"] == "recipient_add"]

    total_win_svc = float(obs_df["service_hours"].sum())
    wkd_days = int(obs_df.loc[obs_df["day_group"] == "weekday", "date"].nunique())
    wke_days = int(obs_df.loc[obs_df["day_group"] == "weekend", "date"].nunique())
    freed_hrs = float(-donors["delta_service_hours"].sum())
    added_hrs = float(recips["delta_service_hours"].sum())
    net_hrs = added_hrs - freed_hrs
    below_thresh = int(-recips["high_demand_hours_delta"].sum())
    created_hd = int(donors["high_demand_hours_delta"].sum())
    freed_pct = freed_hrs / total_win_svc * 100.0

    fig, axes = plt.subplots(1, 2, figsize=(14.0, 5.5))

    # Left panel: Average daily service-hours shifted (/day) by time_band & day_group
    bands = ["early_morning", "morning_peak", "midday", "evening_peak", "night"]
    wkd_d = [float(donors[(donors["time_band"] == b) & (donors["day_group"] == "weekday")]["delta_service_hours_per_day"].sum()) for b in bands]
    wke_d = [float(donors[(donors["time_band"] == b) & (donors["day_group"] == "weekend")]["delta_service_hours_per_day"].sum()) for b in bands]
    wkd_r = [float(recips[(recips["time_band"] == b) & (recips["day_group"] == "weekday")]["delta_service_hours_per_day"].sum()) for b in bands]
    wke_r = [float(recips[(recips["time_band"] == b) & (recips["day_group"] == "weekend")]["delta_service_hours_per_day"].sum()) for b in bands]

    x = np.arange(len(bands))
    w = 0.36
    axes[0].bar(x - w / 2, wkd_d, width=w, color="#b45309", label=f"Weekday trims ({sum(wkd_d):+.1f} hrs/day, {wkd_days}d)")
    axes[0].bar(x + w / 2, wke_d, width=w, color="#f59e0b", label=f"Weekend trims ({sum(wke_d):+.1f} hrs/day, {wke_days}d)")
    axes[0].bar(x - w / 2, wkd_r, width=w, color="#0b5394", label=f"Weekday adds ({sum(wkd_r):+.1f} hrs/day, {wkd_days}d)")
    axes[0].bar(x + w / 2, wke_r, width=w, color="#60a5fa", label=f"Weekend adds ({sum(wke_r):+.1f} hrs/day, {wke_days}d)")
    axes[0].axhline(0, color="black", linewidth=0.9)

    for idx in range(len(bands)):
        for offset, val in [(-w / 2, wkd_d[idx]), (w / 2, wke_d[idx])]:
            if val < -1.0:
                axes[0].text(idx + offset, val - 2.5, f"{val:.0f}", ha="center", va="top", fontsize=7.5, fontweight="bold")
        for offset, val in [(-w / 2, wkd_r[idx]), (w / 2, wke_r[idx])]:
            if val > 1.0:
                axes[0].text(idx + offset, val + 2.0, f"+{val:.0f}", ha="center", va="bottom", fontsize=7.5, fontweight="bold")

    axes[0].set_xticks(x)
    axes[0].set_xticklabels(["Early\nMorning", "Morning\nPeak", "Midday", "Evening\nPeak", "Night"])
    ymin = min(min(wkd_d), min(wke_d)) * 1.25 - 10
    ymax = max(max(wkd_r), max(wke_r)) * 1.30 + 15
    axes[0].set_ylim(ymin, ymax)
    axes[0].set_ylabel("Service-Hours Change per Day (Aug–Oct Typical Days)")
    axes[0].set_title(
        f"{freed_hrs:,.0f} Hrs Moved Over {wkd_days + wke_days}d ({freed_pct:.2f}% of Network, Net {net_hrs:+.1f} Hrs)"
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
    axes[1].set_xlabel(f"Observed Route-Hours Exceeding p75 Threshold ({wkd_days} Wkdays / {wke_days} Wkends)")
    axes[1].set_title(
        f"{below_thresh:,} Route-Hours (~{below_thresh / (wkd_days + wke_days):.1f}/day) Fall Below p75 ({created_hd} Added)",
        fontsize=10.5,
    )
    axes[1].grid(True, axis="x", alpha=0.3)
    axes[1].legend(frameon=True, fontsize=8.5)

    fig.suptitle(
        f"Step 9 Budget-Neutral Reallocation — Aug–Oct 2026 ({wkd_days} Typical Weekdays + {wke_days} Typical Weekend Days; Riders Constant)",
        fontsize=10.5,
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
    w_cfg = cfg["step7_9_review_window"]
    review_df = pd.read_csv(TAB_DIR / "m3_step7_review_list.csv")
    obs_df = load_observed_review_window_hourly(
        start_date=w_cfg["start_date"], end_date=w_cfg["end_date"]
    )

    scenarios_df = simulate_trip_scenarios(review_df, obs_df, cfg)
    scenarios_path = TAB_DIR / "m3_step8_candidate_scenarios.csv"
    scenarios_df.to_csv(scenarios_path, index=False)

    merge_df = evaluate_shared_corridor_merges(obs_df, cfg)
    merge_path = TAB_DIR / "m3_step8_shared_corridor_merge_checks.csv"
    merge_df.to_csv(merge_path, index=False)

    plan_df = build_budget_neutral_reallocation(review_df, scenarios_df, cfg)
    plan_path = TAB_DIR / "m3_step9_budget_neutral_reallocation.csv"
    plan_df.to_csv(plan_path, index=False)

    fig_path = FIG_DIR / "m3_step9_reallocation_summary.png"
    plot_reallocation_summary(plan_df, fig_path, obs_df)

    total_win_svc = float(obs_df["service_hours"].sum())
    n_days = int(obs_df["date"].nunique())
    donors = plan_df[plan_df["reallocation_role"] == "donor_trim"]
    recips = plan_df[plan_df["reallocation_role"] == "recipient_add"]
    freed = float(-donors["delta_service_hours"].sum())
    added = float(recips["delta_service_hours"].sum())
    print(f"Saved {len(scenarios_df)} candidate scenarios -> {scenarios_path}")
    print(f"Saved {len(merge_df)} shared_corridor merge checks -> {merge_path}")
    print(
        f"Saved budget-neutral reallocation over {n_days} typical days ({len(donors)} donors -{freed:.2f} hrs "
        f"[{freed/total_win_svc*100:.2f}% of {total_win_svc:,.1f} total svc-hrs], "
        f"{len(recips)} recipients +{added:.2f} hrs, net={added - freed:+.2f} hrs) -> {plan_path}"
    )
    for dg in ("weekday", "weekend"):
        dd = donors[donors["day_group"] == dg]
        rr = recips[recips["day_group"] == dg]
        dg_tot = float(obs_df.loc[obs_df["day_group"] == dg, "service_hours"].sum())
        days_n = int(obs_df.loc[obs_df["day_group"] == dg, "date"].nunique())
        df_h = float(-dd["delta_service_hours"].sum())
        da_h = float(rr["delta_service_hours"].sum())
        print(
            f"  {dg} ({days_n}d): -{df_h:.2f} hrs ({-df_h/days_n:.2f}/day, {df_h/dg_tot*100:.2f}% of {dg_tot:,.1f} {dg} svc-hrs) "
            f"-> +{da_h:.2f} hrs (+{da_h/days_n:.2f}/day), net={da_h - df_h:+.2f} hrs"
        )
    print(
        f"With riders held constant, {-int(recips['high_demand_hours_delta'].sum())} route-hours over {n_days} typical days "
        f"(about {-int(recips['high_demand_hours_delta'].sum()) / n_days:.1f} per day) fall below the high-demand threshold "
        f"(donor route-hours moving above: {int(donors['high_demand_hours_delta'].sum())})."
    )
    print(f"Saved figure -> {fig_path}")


if __name__ == "__main__":
    main()
