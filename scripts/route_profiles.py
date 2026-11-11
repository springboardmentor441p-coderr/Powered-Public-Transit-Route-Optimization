"""Validated route/date aggregation for exploratory route grouping.

Clustering remains in the editable notebook. These helpers enforce common observation
dates, preserve genuine zeros and expose incomplete inputs instead of imputing them.
"""

import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment


FEATURES = [
    "log_weekday_boardings", "weekend_boarding_ratio", "weekday_peak_share",
    "log_weekday_service_hours", "weekend_service_ratio",
]
WEIGHTS = np.array([1 / np.sqrt(3)] * 3 + [1 / np.sqrt(2)] * 2)
DAY_TYPES = ["Weekday", "Saturday", "Sunday"]


def common_profile_members(daily, hourly, routes, start, end):
    """Require the same complete eligible dates and 24 hours for every route.

    A known zero scheduled-service total is retained. Positive denominators are
    required later, only for weekday ratios. Missing demand never becomes zero.
    """
    routes = sorted(set(routes))
    if not routes or pd.Timestamp(start) > pd.Timestamp(end):
        raise ValueError("Nonempty routes and an ordered observation window are required")
    daily = daily.copy()
    hourly = hourly.copy()
    daily["payment_date"] = pd.to_datetime(daily.payment_date)
    hourly["payment_date"] = pd.to_datetime(hourly.payment_date)
    hourly["local_hour"] = pd.to_datetime(hourly.local_hour)
    daily = daily.loc[daily.bus_route.isin(routes) & daily.payment_date.between(start, end)]
    hourly = hourly.loc[hourly.bus_route.isin(routes) & hourly.payment_date.between(start, end)]
    if daily.duplicated(["bus_route", "payment_date"]).any():
        raise ValueError("Duplicate route/date inputs")
    if hourly.duplicated(["bus_route", "local_hour"]).any():
        raise ValueError("Duplicate route/hour inputs")
    if not hourly.local_hour.dt.normalize().eq(hourly.payment_date).all():
        raise ValueError("Hourly observation date disagrees with its clock timestamp")
    if not hourly.local_hour.eq(hourly.local_hour.dt.floor("h")).all():
        raise ValueError("Hourly observations must lie on clock-hour boundaries")
    hourly["peak_boardings"] = hourly.analysis_boardings.where(
        hourly.local_hour.dt.hour.isin([7, 8, 9, 16, 17, 18]), 0)
    hourly_days = hourly.groupby(["bus_route", "payment_date"], as_index=False).agg(
        hourly_rows=("local_hour", "size"), valid_hours=("analysis_boardings", "count"),
        hourly_boardings=("analysis_boardings", lambda x: x.sum(min_count=24)),
        peak_boardings=("peak_boardings", lambda x: x.sum(min_count=6)))
    merged = daily.merge(hourly_days, on=["bus_route", "payment_date"], how="left", validate="one_to_one")
    valid_demand = merged.analysis_boardings.notna()
    reconciled = np.isclose(merged.analysis_boardings, merged.hourly_boardings, rtol=0, atol=1e-6)
    eligible = (merged.schedule_comparison_eligible.eq(True)
                & valid_demand & merged.scheduled_departures.notna()
                & merged.scheduled_service_hours.notna()
                & merged.scheduled_departures.ge(0) & merged.scheduled_service_hours.ge(0)
                & merged.hourly_rows.eq(24) & merged.valid_hours.eq(24) & reconciled)
    merged["profile_date_eligible"] = eligible
    records = []
    for date in pd.date_range(start, end):
        part = merged.loc[merged.payment_date.eq(date)]
        common = len(part) == len(routes) and bool(part.profile_date_eligible.all())
        records.append({"payment_date": date, "expected_routes": len(routes),
                        "observed_routes": len(part), "eligible_routes": int(part.profile_date_eligible.sum()),
                        "unavailable_demand_routes": int(part.analysis_boardings.isna().sum()),
                        "unavailable_schedule_routes": int((~part.schedule_comparison_eligible.eq(True)).sum()),
                        "incomplete_hourly_routes": int((~part.valid_hours.eq(24)).sum()),
                        "unreconciled_routes": int((part.analysis_boardings.notna()
                            & part.hourly_boardings.notna()
                            & ~np.isclose(part.analysis_boardings, part.hourly_boardings, rtol=0, atol=1e-6)).sum()),
                        "included": common})
    coverage = pd.DataFrame(records)
    dates = coverage.loc[coverage.included, "payment_date"]
    if dates.empty:
        raise ValueError("No common complete eligible observation dates")
    members = merged.loc[merged.payment_date.isin(dates), [
        "bus_route", "payment_date", "analysis_boardings", "scheduled_departures",
        "scheduled_service_hours", "peak_boardings", "source_snapshot", "prior_source_snapshot",
    ]].sort_values(["bus_route", "payment_date"]).reset_index(drop=True)
    weekday = members.payment_date.dt.dayofweek
    members["day_type"] = np.select([weekday.eq(5), weekday.eq(6)], ["Saturday", "Sunday"], "Weekday")
    return members, coverage


def build_route_profiles(members, minimum_days=None):
    """One row per route; repeated dates are allowed for whole-week bootstrap draws.

    Saturday/Sunday means receive equal weight regardless of how many valid dates
    survived screening. Peak share is a ratio of sums over the same weekday rows.
    """
    minimum_days = minimum_days or {"Weekday": 20, "Saturday": 5, "Sunday": 5}
    required = ["analysis_boardings", "scheduled_departures", "scheduled_service_hours", "peak_boardings"]
    values = members[required].to_numpy(dtype=float)
    if len(members) == 0 or not np.isfinite(values).all() or (values < 0).any():
        raise ValueError("Profile members must contain finite nonnegative observations")
    if members.peak_boardings.gt(members.analysis_boardings + 1e-6).any():
        raise ValueError("Peak boardings cannot exceed the matching daily total")
    grouped = members.groupby(["bus_route", "day_type"])
    counts = grouped.size().unstack("day_type").reindex(columns=DAY_TYPES, fill_value=0).fillna(0)
    for kind in DAY_TYPES:
        if counts[kind].lt(minimum_days[kind]).any():
            raise ValueError(f"Insufficient {kind} observations for a route profile")
    means = grouped[required[:3]].mean()
    result = pd.DataFrame(index=counts.index)
    for kind in DAY_TYPES:
        slug = kind.lower()
        result[f"{slug}_days"] = counts[kind].astype(int)
        result[f"mean_{slug}_boardings"] = means.analysis_boardings.xs(kind, level="day_type")
        result[f"mean_{slug}_departures"] = means.scheduled_departures.xs(kind, level="day_type")
        result[f"mean_{slug}_service_hours"] = means.scheduled_service_hours.xs(kind, level="day_type")
    if result.mean_weekday_boardings.le(0).any() or result.mean_weekday_service_hours.le(0).any():
        raise ValueError("Weekday reference demand and service must be positive; no zero imputation")
    weekdays = members.loc[members.day_type.eq("Weekday")].groupby("bus_route")
    result["weekday_peak_share"] = weekdays.peak_boardings.sum() / weekdays.analysis_boardings.sum()
    result["weekend_boarding_ratio"] = (
        result.mean_saturday_boardings + result.mean_sunday_boardings) / (2 * result.mean_weekday_boardings)
    result["weekend_service_ratio"] = (
        result.mean_saturday_service_hours + result.mean_sunday_service_hours) / (2 * result.mean_weekday_service_hours)
    result["log_weekday_boardings"] = np.log1p(result.mean_weekday_boardings)
    result["log_weekday_service_hours"] = np.log1p(result.mean_weekday_service_hours)
    result["weekday_boardings_per_service_hour"] = (
        weekdays.analysis_boardings.sum() / weekdays.scheduled_service_hours.sum())
    result["first_date"] = members.groupby("bus_route").payment_date.min()
    result["last_date"] = members.groupby("bus_route").payment_date.max()
    result["zero_service_dates"] = members.scheduled_service_hours.eq(0).groupby(members.bus_route).sum()
    if not np.isfinite(result[FEATURES].to_numpy()).all():
        raise ValueError("Missing or nonfinite clustering features")
    return result.sort_index().reset_index()


def choose_cluster_count(scores, minimum_size=4, tolerance=0.02):
    """Smallest eligible k within a predeclared silhouette tolerance of the best."""
    eligible = scores.loc[scores.min_cluster_size.ge(minimum_size) & scores.silhouette.notna()]
    if eligible.empty:
        raise ValueError("No candidate has the required minimum group size")
    best = eligible.silhouette.max()
    return int(eligible.loc[eligible.silhouette.ge(best - tolerance), "k"].min())


def align_labels(reference, candidate):
    """Match arbitrary group IDs for assignment-retention diagnostics, not probabilities."""
    reference, candidate = np.asarray(reference), np.asarray(candidate)
    if reference.shape != candidate.shape or reference.ndim != 1:
        raise ValueError("Partitions must describe the same ordered routes")
    rows, cols = np.unique(reference), np.unique(candidate)
    if len(rows) != len(cols):
        raise ValueError("Assignment retention requires the same number of groups")
    counts = np.array([[(reference == a)[candidate == b].sum() for b in cols] for a in rows])
    row_ids, col_ids = linear_sum_assignment(-counts)
    mapping = {cols[j]: rows[i] for i, j in zip(row_ids, col_ids)}
    return np.array([mapping[value] for value in candidate])
