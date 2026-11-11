"""Explicit descriptive review rules on matched route/date observations.

No models are fitted here. Missing or unsupported evidence remains unavailable.
Unsupervised labels and forecasting results do not enter the decision rules.
"""

import numpy as np
import pandas as pd


DAY_TYPES = ("Weekday", "Saturday", "Sunday")
KEYS = ["bus_route", "family", "day_type"]
DEFAULT_MINIMUM = {"Weekday": 40, "Saturday": 8, "Sunday": 8}
WINDOW_START, WINDOW_END = "2026-07-06", "2026-09-27"


def aggregate_review_profiles(members, minimum_days=None, routes=None):
    """Ratio of sums on the exact same paired observations; retain zero-service days."""
    minimum_days = DEFAULT_MINIMUM if minimum_days is None else minimum_days
    required = ["analysis_boardings", "scheduled_service_hours", "scheduled_departures"]
    values = members[required].to_numpy(dtype=float)
    if (members.empty and routes is None) or not np.isfinite(values).all() or (values < 0).any():
        raise ValueError("Review observations must be finite, nonnegative and nonempty")
    dates = pd.to_datetime(members.payment_date)
    expected = np.select([dates.dt.dayofweek.eq(5), dates.dt.dayofweek.eq(6)],
                         ["Saturday", "Sunday"], "Weekday")
    if not np.array_equal(expected, members.day_type.to_numpy()):
        raise ValueError("Day type disagrees with the observation date")
    copy = members.assign(payment_date=dates)
    copy["positive_boardings_zero_service"] = copy.analysis_boardings.gt(0) & copy.scheduled_service_hours.eq(0)
    result = copy.groupby(["bus_route", "day_type"]).agg(
        observed_dates=("payment_date", "size"),
        distinct_dates=("payment_date", "nunique"),
        first_date=("payment_date", "min"), last_date=("payment_date", "max"),
        total_boardings=("analysis_boardings", "sum"),
        total_service_hours=("scheduled_service_hours", "sum"),
        total_departures=("scheduled_departures", "sum"),
        positive_zero_service_dates=("positive_boardings_zero_service", "sum"),
    ).reset_index()
    # Reindex missing day types as unavailable; no observed values are zero-filled.
    route_ids = sorted(copy.bus_route.unique()) if routes is None else sorted(routes)
    index = pd.MultiIndex.from_product([route_ids, DAY_TYPES],
                                      names=["bus_route", "day_type"])
    result = result.set_index(["bus_route", "day_type"]).reindex(index).reset_index()
    result["minimum_dates"] = result.day_type.map(minimum_days)
    result["service_comparison_eligible"] = (
        result.observed_dates.ge(result.minimum_dates)
        & result.total_service_hours.gt(0) & result.positive_zero_service_dates.eq(0))
    for name, total in [("mean_boardings", "total_boardings"),
                         ("mean_service_hours", "total_service_hours"),
                         ("mean_departures", "total_departures")]:
        result[name] = result[total] / result.observed_dates
    result["boardings_per_bus_hour"] = (
        result.total_boardings / result.total_service_hours.where(result.total_service_hours.gt(0))
    ).where(result.service_comparison_eligible)
    result["evidence_status"] = np.select(
        [result.observed_dates.isna() | result.observed_dates.lt(result.minimum_dates),
         result.positive_zero_service_dates.gt(0), ~result.total_service_hours.gt(0)],
        ["insufficient_observations", "source_alignment_review", "no_positive_service_denominator"],
        "eligible")
    return result


def evaluate_review_rules(members, tail_quantile=0.10, ratio_threshold=1.25,
                          minimum_days=None, minimum_half_weekdays=20, minimum_cohort=10):
    """Return every rule evaluation, including unavailable and nontriggered cases.

    Relative tails use separate day-type cohorts. Weekend rates compare with that route's
    weekday rate. The temporal rule compares weekday rates before/after 17 August.
    Counts in bootstrap inputs may repeat dates; original member uniqueness is checked
    by the notebook before resampling.
    """
    if not 0 < tail_quantile < .5 or ratio_threshold <= 1 or minimum_cohort < 3:
        raise ValueError("Invalid descriptive review thresholds")
    if not pd.to_datetime(members.payment_date).between(WINDOW_START, WINDOW_END).all():
        raise ValueError("This protocol is restricted to its declared July-September observation window")
    profiles = aggregate_review_profiles(members, minimum_days)
    evaluations = []
    for kind in DAY_TYPES:
        cohort = profiles.loc[profiles.day_type.eq(kind) & profiles.service_comparison_eligible]
        metric = cohort.boardings_per_bus_hour
        lower, median, upper = (metric.quantile(q) for q in [tail_quantile, .5, 1 - tail_quantile])
        enough_cohort = len(cohort) >= minimum_cohort
        for row in profiles.loc[profiles.day_type.eq(kind)].itertuples():
            eligible = bool(row.service_comparison_eligible and enough_cohort)
            direction, triggered = "unavailable", pd.NA
            if eligible:
                direction = ("lower" if row.boardings_per_bus_hour <= lower and row.boardings_per_bus_hour < median
                             else "higher" if row.boardings_per_bus_hour >= upper and row.boardings_per_bus_hour > median
                             else "none")
                triggered = direction != "none"
            evaluations.append(dict(
                bus_route=row.bus_route, family="relative_service_use", day_type=kind,
                eligible=eligible, triggered=triggered, direction=direction,
                metric=row.boardings_per_bus_hour, lower_threshold=lower, upper_threshold=upper,
                reference_metric=median, cohort_routes=len(cohort), sample_dates=row.observed_dates,
                reference_dates=np.nan, first_date=row.first_date, last_date=row.last_date,
                numerator_boardings=row.total_boardings, denominator_bus_hours=row.total_service_hours,
                reference_numerator_boardings=np.nan, reference_denominator_bus_hours=np.nan,
                reference_first_date=row.first_date, reference_last_date=row.last_date,
                reason=(f"{row.boardings_per_bus_hour:.2f} boardings/bus-hour; {kind} cohort "
                        f"median {median:.2f}; tails {lower:.2f}/{upper:.2f}; {len(cohort)} eligible routes")
                       if eligible else f"Unavailable: {row.evidence_status if not row.service_comparison_eligible else 'insufficient_peer_routes'}",
            ))
    indexed = profiles.set_index(["bus_route", "day_type"])
    for route in sorted(profiles.bus_route.unique()):
        weekday = indexed.loc[(route, "Weekday")]
        for kind in ["Saturday", "Sunday"]:
            weekend = indexed.loc[(route, kind)]
            eligible = bool(weekday.service_comparison_eligible and weekend.service_comparison_eligible
                            and weekday.boardings_per_bus_hour > 0)
            ratio = (weekend.boardings_per_bus_hour / weekday.boardings_per_bus_hour) if eligible else np.nan
            direction = ("higher" if ratio >= ratio_threshold else "lower" if ratio <= 1 / ratio_threshold
                         else "none") if eligible else "unavailable"
            evaluations.append(dict(
                bus_route=route, family="weekend_intensity_difference", day_type=kind,
                eligible=eligible, triggered=(direction != "none") if eligible else pd.NA, direction=direction,
                metric=ratio, lower_threshold=1 / ratio_threshold, upper_threshold=ratio_threshold,
                reference_metric=weekday.boardings_per_bus_hour, cohort_routes=np.nan,
                sample_dates=weekend.observed_dates, reference_dates=weekday.observed_dates,
                first_date=weekend.first_date, last_date=weekend.last_date,
                numerator_boardings=weekend.total_boardings, denominator_bus_hours=weekend.total_service_hours,
                reference_numerator_boardings=weekday.total_boardings,
                reference_denominator_bus_hours=weekday.total_service_hours,
                reference_first_date=weekday.first_date, reference_last_date=weekday.last_date,
                reason=(f"{kind}/weekday boardings-per-bus-hour ratio {ratio:.2f}; "
                        f"rates {weekend.boardings_per_bus_hour:.2f}/{weekday.boardings_per_bus_hour:.2f}; "
                        f"review bounds {1/ratio_threshold:.2f}/{ratio_threshold:.2f}")
                       if eligible else "Unavailable: insufficient or unresolved weekday/weekend service evidence",
            ))
    date = pd.to_datetime(members.payment_date)
    early = aggregate_review_profiles(
        members.loc[date.between("2026-07-06", "2026-08-16")],
        {"Weekday": minimum_half_weekdays, "Saturday": 1, "Sunday": 1},
        routes=profiles.bus_route.unique()).set_index(["bus_route", "day_type"])
    late = aggregate_review_profiles(
        members.loc[date.between("2026-08-17", "2026-09-27")],
        {"Weekday": minimum_half_weekdays, "Saturday": 1, "Sunday": 1},
        routes=profiles.bus_route.unique()).set_index(["bus_route", "day_type"])
    for route in sorted(profiles.bus_route.unique()):
        a, b = early.loc[(route, "Weekday")], late.loc[(route, "Weekday")]
        eligible = bool(a.service_comparison_eligible and b.service_comparison_eligible
                        and a.boardings_per_bus_hour > 0)
        ratio = b.boardings_per_bus_hour / a.boardings_per_bus_hour if eligible else np.nan
        direction = ("higher" if ratio >= ratio_threshold else "lower" if ratio <= 1 / ratio_threshold
                     else "none") if eligible else "unavailable"
        evaluations.append(dict(
            bus_route=route, family="weekday_intensity_change", day_type="Weekday",
            eligible=eligible, triggered=(direction != "none") if eligible else pd.NA, direction=direction,
            metric=ratio, lower_threshold=1 / ratio_threshold, upper_threshold=ratio_threshold,
            reference_metric=a.boardings_per_bus_hour, cohort_routes=np.nan,
            sample_dates=b.observed_dates, reference_dates=a.observed_dates,
            first_date=b.first_date, last_date=b.last_date,
            numerator_boardings=b.total_boardings, denominator_bus_hours=b.total_service_hours,
            reference_numerator_boardings=a.total_boardings, reference_denominator_bus_hours=a.total_service_hours,
            reference_first_date=a.first_date, reference_last_date=a.last_date,
            early_mean_boardings=a.mean_boardings, late_mean_boardings=b.mean_boardings,
            early_mean_bus_hours=a.mean_service_hours, late_mean_bus_hours=b.mean_service_hours,
            reason=(f"Last/first six-week weekday boardings-per-bus-hour ratio {ratio:.2f}; "
                    f"rates {b.boardings_per_bus_hour:.2f}/{a.boardings_per_bus_hour:.2f}; "
                    f"review bounds {1/ratio_threshold:.2f}/{ratio_threshold:.2f}")
                   if eligible else "Unavailable: insufficient or unresolved six-week weekday evidence",
        ))
    evaluation = pd.DataFrame(evaluations)
    evaluation["triggered"] = evaluation.triggered.astype("boolean")
    assert not evaluation.duplicated(KEYS).any()
    return profiles, evaluation


def make_review_queue(evaluations, route_context):
    """One row per route; no composite score or ordering of route performance."""
    if route_context.bus_route.duplicated().any():
        raise ValueError("Context must contain exactly one record per route")
    if set(route_context.bus_route) != set(evaluations.bus_route):
        raise ValueError("Rule and context route populations differ")
    rows = []
    for route in sorted(route_context.bus_route):
        context = route_context.loc[route_context.bus_route.eq(route)].iloc[0]
        part = evaluations.loc[evaluations.bus_route.eq(route)]
        flags = part.loc[part.triggered.fillna(False)]
        source_review = bool(context.positive_boardings_zero_service_dates > 0)
        any_eligible = bool(part.eligible.any())
        state = ("source_clarification" if source_review else
                 "insufficient_evidence" if not any_eligible else
                 "planning_review" if len(flags) else "no_rule_triggered")
        flag_summary = " | ".join(
            f"{r.day_type}: {r.family} ({r.direction})" for r in flags.itertuples())
        if source_review:
            explanation = (f"Source clarification: {int(context.positive_boardings_zero_service_dates)} "
                           "positive-boardings/zero-service observations require verification.")
            if flag_summary:
                explanation += " Other retained rule evidence: " + flag_summary
        elif not any_eligible:
            explanation = "Insufficient supported comparisons; unavailable evidence does not imply balanced service."
        elif len(flags):
            explanation = flag_summary
        else:
            explanation = "No primary rule triggered among the supported historical comparisons."
        rows.append({
            "bus_route": route, "review_state": state,
            "review_families": "; ".join(sorted(flags.family.unique())),
            "flagged_evaluations": len(flags),
            "eligible_evaluations": int(part.eligible.sum()),
            "unavailable_evaluations": int((~part.eligible).sum()),
            "evidence_summary": explanation,
            "automated_service_change": False,
        })
    result = pd.DataFrame(rows).merge(route_context, on="bus_route", validate="one_to_one")
    result["review_order"] = result.review_state.map({
        "source_clarification": 0, "insufficient_evidence": 1,
        "planning_review": 2, "no_rule_triggered": 3,
    })
    return result.sort_values(["review_order", "bus_route"]).reset_index(drop=True)
