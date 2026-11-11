"""Historical planning arithmetic; no timetable generation or service execution."""

import hashlib
import numpy as np
import pandas as pd

DAY_TYPES = ("Weekday", "Saturday", "Sunday")
MINIMUM_DAYS = {"Weekday": 40, "Saturday": 8, "Sunday": 8}


def _number(value, name, lower=None, upper=None, strictly_positive=False):
    if isinstance(value, (bool, np.bool_)):
        raise ValueError(f"{name} must be a finite number")
    try:
        result = float(value)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"{name} must be a finite number") from exc
    if (not np.isfinite(result) or (strictly_positive and result <= 0)
            or (lower is not None and result < lower) or (upper is not None and result > upper)):
        raise ValueError(f"{name} is outside the permitted arithmetic domain")
    return result


def build_scenario_baselines(members, review, minimum_days=None):
    """Paired totals and daily means with explicit route-level source gates."""
    minimum_days = MINIMUM_DAYS if minimum_days is None else minimum_days
    members = members.copy()
    members["payment_date"] = pd.to_datetime(members.payment_date)
    routes = sorted(members.bus_route.unique())
    if not routes or review.bus_route.duplicated().any() or sorted(review.bus_route) != routes:
        raise ValueError("Baseline observations and review context must have the same unique route population")
    if members.duplicated(["bus_route", "payment_date"]).any():
        raise ValueError("Duplicate baseline route/date observations")
    if not members.groupby("payment_date").bus_route.nunique().eq(len(routes)).all():
        raise ValueError("All routes must share the same baseline observation dates")
    for field, expected in [("review_period_start", members.payment_date.min()),
                             ("review_period_end", members.payment_date.max())]:
        if field not in review or not pd.to_datetime(review[field]).eq(expected).all():
            raise ValueError("Review and scenario baseline periods must match exactly")
    if not members.payment_date.eq(members.payment_date.dt.normalize()).all():
        raise ValueError("Baseline dates must be normalized clock dates")
    numeric = members[["analysis_boardings", "scheduled_departures", "scheduled_service_hours"]].to_numpy(dtype=float)
    if not np.isfinite(numeric).all() or (numeric < 0).any():
        raise ValueError("Missing, nonfinite or negative baseline observations cannot become scenarios")
    if not np.isclose(members.scheduled_departures, np.round(members.scheduled_departures)).all():
        raise ValueError("Observed trip-start counts must be integers; only derived daily means may be fractional")
    weekday = members.payment_date.dt.dayofweek
    kinds = np.select([weekday.eq(5), weekday.eq(6)], ["Saturday", "Sunday"], "Weekday")
    if not np.array_equal(kinds, members.day_type.to_numpy()):
        raise ValueError("Day type disagrees with baseline clock dates")
    allowed = {"source_clarification", "insufficient_evidence", "planning_review", "no_rule_triggered"}
    if not review.review_state.isin(allowed).all():
        raise ValueError("Unknown review states cannot pass a scenario gate")
    members["source_issue"] = members.analysis_boardings.gt(0) & members.scheduled_service_hours.eq(0)
    actual_issues = members.groupby("bus_route").source_issue.sum().reindex(routes)
    reported_issues = review.set_index("bus_route").positive_boardings_zero_service_dates.reindex(routes)
    if reported_issues.isna().any() or not np.array_equal(actual_issues.to_numpy(), reported_issues.to_numpy()):
        raise ValueError("Review source-issue counts do not match the exact baseline observations")
    grouped = members.groupby(["bus_route", "day_type"])
    baseline = grouped.agg(
        observed_dates=("payment_date", "nunique"), first_date=("payment_date", "min"),
        last_date=("payment_date", "max"), total_boardings=("analysis_boardings", "sum"),
        total_departures=("scheduled_departures", "sum"),
        total_bus_hours=("scheduled_service_hours", "sum"),
        positive_zero_service_dates=("source_issue", "sum"),
    ).reindex(pd.MultiIndex.from_product([routes, DAY_TYPES], names=["bus_route", "day_type"])).reset_index()
    date_sets = grouped.payment_date.agg(lambda values: hashlib.sha256(
        "\n".join(sorted(values.dt.strftime("%Y-%m-%d"))).encode()).hexdigest())
    baseline["observation_dates_sha256"] = pd.MultiIndex.from_frame(
        baseline[["bus_route", "day_type"]]).map(date_sets)
    baseline["source_snapshots"] = pd.MultiIndex.from_frame(baseline[["bus_route", "day_type"]]).map(
        grouped.source_snapshot.agg(lambda x: "; ".join(sorted(set(x)))))
    baseline["prior_source_snapshots"] = pd.MultiIndex.from_frame(baseline[["bus_route", "day_type"]]).map(
        grouped.prior_source_snapshot.agg(lambda x: "; ".join(sorted(set(x)))))
    context_columns = [c for c in ["bus_route", "review_state", "positive_boardings_zero_service_dates",
                                   "route_long_name", "exclusive_stop_ids", "snapshot_id"] if c in review]
    baseline = baseline.merge(review[context_columns], on="bus_route", validate="many_to_one")
    baseline["minimum_dates"] = baseline.day_type.map(minimum_days)
    baseline["baseline_status"] = np.select([
        baseline.review_state.eq("source_clarification") | baseline.positive_boardings_zero_service_dates.gt(0),
        baseline.review_state.eq("insufficient_evidence"),
        baseline.observed_dates.isna() | baseline.observed_dates.lt(baseline.minimum_dates),
        ~baseline.total_departures.gt(0) | ~baseline.total_bus_hours.gt(0),
    ], ["source_clarification_required", "insufficient_evidence", "insufficient_day_type_support",
        "no_positive_baseline_service"], "eligible")
    baseline["baseline_eligible"] = baseline.baseline_status.eq("eligible")
    for name, total in [("mean_boardings", "total_boardings"), ("mean_departures", "total_departures"),
                         ("mean_bus_hours", "total_bus_hours")]:
        baseline[name] = baseline[total] / baseline.observed_dates
    baseline["boardings_per_departure"] = (
        baseline.total_boardings / baseline.total_departures.where(baseline.total_departures.gt(0))
    ).where(baseline.baseline_eligible)
    baseline["boardings_per_bus_hour"] = (
        baseline.total_boardings / baseline.total_bus_hours.where(baseline.total_bus_hours.gt(0))
    ).where(baseline.baseline_eligible)
    baseline["baseline_id"] = baseline.bus_route + "|" + baseline.day_type + "|" + baseline.observation_dates_sha256.fillna("unavailable")
    baseline["unit_scope"] = "mean daily clock-date service; not an integer timetable"
    return baseline


def compare_frequency(baseline, frequency_factor, demand_factor=1., max_added_bus_hours=None,
                      minimum_retained_fraction=.8):
    """Proportional trip/hour alternatives with an independent demand assumption.

    Scaling both trip starts and clock-date service exposure is an explicit aggregate
    assumption. Their ratio is not a measured trip duration or round-trip vehicle cycle.
    """
    frequency_factor = _number(frequency_factor, "frequency_factor", strictly_positive=True)
    demand_factor = _number(demand_factor, "demand_factor", lower=0)
    floor = _number(minimum_retained_fraction, "minimum_retained_fraction", lower=0, upper=1)
    budget = None if max_added_bus_hours is None else _number(max_added_bus_hours, "max_added_bus_hours", lower=0)
    result = baseline.copy()
    usable = result.baseline_eligible.eq(True)
    required = ["mean_boardings", "mean_departures", "mean_bus_hours"]
    numbers = result.loc[usable, required].to_numpy(dtype=float)
    if (not np.isfinite(numbers).all() or (numbers < 0).any()
            or result.loc[usable, ["mean_departures", "mean_bus_hours"]].le(0).any().any()):
        raise ValueError("Eligible baselines must contain finite demand and positive paired service")
    result["frequency_factor"] = frequency_factor
    result["demand_factor"] = demand_factor
    result["max_added_bus_hours"] = np.nan if budget is None else budget
    result["minimum_retained_fraction"] = floor
    result["scenario_mean_departures"] = (result.mean_departures * frequency_factor).where(usable)
    result["scenario_mean_bus_hours"] = (result.mean_bus_hours * frequency_factor).where(usable)
    result["scenario_mean_boardings"] = (result.mean_boardings * demand_factor).where(usable)
    result["delta_mean_departures"] = result.scenario_mean_departures - result.mean_departures
    result["delta_mean_bus_hours"] = result.scenario_mean_bus_hours - result.mean_bus_hours
    result["scenario_boardings_per_departure"] = result.scenario_mean_boardings / result.scenario_mean_departures
    result["scenario_boardings_per_bus_hour"] = result.scenario_mean_boardings / result.scenario_mean_bus_hours
    for name in ["boardings_per_departure", "boardings_per_bus_hour"]:
        original = result[name].where(result[name].gt(0))
        result[f"change_{name}_fraction"] = (result[f"scenario_{name}"] / original - 1).where(usable)
    result["retention_limit_pass"] = pd.Series(pd.NA, index=result.index, dtype="boolean")
    result.loc[usable, "retention_limit_pass"] = frequency_factor >= floor - 1e-12
    result["added_hours_limit_pass"] = pd.Series(pd.NA, index=result.index, dtype="boolean")
    if budget is not None:
        result.loc[usable, "added_hours_limit_pass"] = result.loc[usable, "delta_mean_bus_hours"].le(budget + 1e-10)
    result["arithmetic_status"] = "withheld"
    result.loc[usable, "arithmetic_status"] = (
        "within_retention_limit_budget_unspecified" if budget is None else "within_declared_arithmetic_limits")
    if budget is not None:
        over_budget = usable & result.added_hours_limit_pass.eq(False).fillna(False)
        result.loc[over_budget, "arithmetic_status"] = "exceeds_added_hours_limit"
    result.loc[usable & result.retention_limit_pass.eq(False).fillna(False), "arithmetic_status"] = "below_retained_service_limit"
    result["demand_assumption"] = ("fixed historical published mean" if demand_factor == 1 else
                                    "independent analyst multiplier; not estimated response to service")
    result["timetable_feasibility"] = "not_assessed"
    result["automatic_service_change"] = False
    return result


def transfer_bus_hours(baselines, donor, recipient, day_type, bus_hours,
                       minimum_retained_fraction=.8):
    """Two-route arithmetic with identical observation dates and fixed summed bus-hours."""
    amount = _number(bus_hours, "bus_hours", lower=0)
    if donor == recipient:
        raise ValueError("A transfer requires two different routes")
    selected = []
    for route in [donor, recipient]:
        rows = baselines.loc[baselines.bus_route.eq(route) & baselines.day_type.eq(day_type)]
        if len(rows) != 1 or not bool(rows.iloc[0].baseline_eligible):
            raise ValueError("Both transfer routes require one eligible baseline for the selected day type")
        selected.append(rows)
    a, b = selected[0].iloc[0], selected[1].iloc[0]
    if pd.isna(a.observation_dates_sha256) or a.observation_dates_sha256 != b.observation_dates_sha256:
        raise ValueError("Transfers require exactly the same matched observation dates")
    if amount >= a.mean_bus_hours:
        raise ValueError("Transfer cannot remove all or more donor service hours")
    factors = [(a.mean_bus_hours - amount) / a.mean_bus_hours,
               (b.mean_bus_hours + amount) / b.mean_bus_hours]
    result = pd.concat([
        compare_frequency(rows, factor, max_added_bus_hours=amount,
                          minimum_retained_fraction=minimum_retained_fraction)
        for rows, factor in zip(selected, factors)
    ], ignore_index=True)
    result["transfer_role"] = ["donor", "recipient"]
    result["transfer_bus_hours"] = amount
    result["transfer_donor"], result["transfer_recipient"] = donor, recipient
    result["budget_scope"] = "paired fixed total scheduled bus-hours; not a verified fleet budget"
    net = float(result.delta_mean_bus_hours.sum())
    if not np.isclose(net, 0, rtol=0, atol=1e-9):
        raise AssertionError("Transfer failed bus-hour conservation")
    summary = {
        "donor": donor, "recipient": recipient, "day_type": day_type, "transfer_bus_hours": amount,
        "baseline_total_mean_bus_hours": float(result.mean_bus_hours.sum()),
        "scenario_total_mean_bus_hours": float(result.scenario_mean_bus_hours.sum()),
        "net_mean_bus_hours_change": net,
        "net_mean_departures_change": float(result.delta_mean_departures.sum()),
        "baseline_total_mean_boardings": float(result.mean_boardings.sum()),
        "scenario_total_mean_boardings": float(result.scenario_mean_boardings.sum()),
        "retention_limits_pass": bool(result.retention_limit_pass.all()),
        "arithmetic_status": ("within_stated_transfer_limits" if result.retention_limit_pass.all()
                              else "below_retained_service_limit"),
        "timetable_feasibility": "not_assessed", "automatic_service_change": False,
    }
    return result, summary
