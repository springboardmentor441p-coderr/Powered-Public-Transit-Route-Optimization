"""Recompute historical review decisions, resamples and queue membership independently."""

from pathlib import Path
import hashlib
import json

import nbformat
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/processed/new_york"
OUT = DATA / "route_review"
KEYS = ["bus_route", "family", "day_type"]


def digest(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def independent_rules(members, routes, tail, ratio, minimum, half_minimum, cohort_minimum):
    """Recreate numerical rules from observation totals without importing the rule module."""
    index = pd.MultiIndex.from_product([routes, ["Weekday", "Saturday", "Sunday"]],
                                      names=["bus_route", "day_type"])

    def rates(frame, support):
        frame = frame.copy()
        frame["bad"] = frame.analysis_boardings.gt(0) & frame.scheduled_service_hours.eq(0)
        result = frame.groupby(["bus_route", "day_type"]).agg(
            n=("payment_date", "size"), b=("analysis_boardings", "sum"),
            h=("scheduled_service_hours", "sum"), bad=("bad", "sum")).reindex(index)
        required = result.index.get_level_values("day_type").map(support)
        result["valid"] = result.n.ge(required) & result.h.gt(0) & result.bad.eq(0)
        result["rate"] = (result.b / result.h.where(result.h.gt(0))).where(result.valid)
        return result

    p = rates(members, minimum)
    first = rates(members.loc[members.payment_date.between("2026-07-06", "2026-08-16")],
                  {"Weekday": half_minimum, "Saturday": 1, "Sunday": 1})
    last = rates(members.loc[members.payment_date.between("2026-08-17", "2026-09-27")],
                 {"Weekday": half_minimum, "Saturday": 1, "Sunday": 1})
    records = []

    def add(route, family, kind, eligible, metric, lower, upper, reference, n, reference_n,
            peer_median=None):
        if not eligible:
            direction, triggered = "unavailable", pd.NA
        else:
            high = metric >= upper and (peer_median is None or metric > peer_median)
            low = metric <= lower and (peer_median is None or metric < peer_median)
            direction = "higher" if high else "lower" if low else "none"
            triggered = direction != "none"
        records.append(dict(bus_route=route, family=family, day_type=kind,
                            eligible=bool(eligible), triggered=triggered, direction=direction,
                            metric=metric, lower_threshold=lower, upper_threshold=upper,
                            reference_metric=reference, sample_dates=n, reference_dates=reference_n))

    for kind in ["Weekday", "Saturday", "Sunday"]:
        part = p.xs(kind, level="day_type")
        peers = part.loc[part.valid, "rate"]
        lower, median, upper = peers.quantile(tail), peers.quantile(.5), peers.quantile(1 - tail)
        for route, row in part.iterrows():
            add(route, "relative_service_use", kind, row.valid and len(peers) >= cohort_minimum,
                row.rate, lower, upper, median, row.n, np.nan, peer_median=median)
    for route in routes:
        weekday = p.loc[(route, "Weekday")]
        for kind in ["Saturday", "Sunday"]:
            weekend = p.loc[(route, kind)]
            valid = weekday.valid and weekend.valid and weekday.rate > 0
            value = weekend.rate / weekday.rate if valid else np.nan
            add(route, "weekend_intensity_difference", kind, valid, value,
                1 / ratio, ratio, weekday.rate, weekend.n, weekday.n)
        a, b = first.loc[(route, "Weekday")], last.loc[(route, "Weekday")]
        valid = a.valid and b.valid and a.rate > 0
        add(route, "weekday_intensity_change", "Weekday", valid,
            b.rate / a.rate if valid else np.nan, 1 / ratio, ratio, a.rate, b.n, a.n)
    result = pd.DataFrame(records)
    result["triggered"] = result.triggered.astype("boolean")
    return result


def compare_rules(actual, expected):
    actual, expected = actual.set_index(KEYS).sort_index(), expected.set_index(KEYS).sort_index()
    pd.testing.assert_index_equal(actual.index, expected.index)
    for field in ["eligible", "direction"]:
        np.testing.assert_array_equal(actual[field], expected[field])
    pd.testing.assert_series_equal(actual.triggered.astype("boolean"), expected.triggered,
                                   check_names=False)
    numeric_fields = ["metric", "lower_threshold", "upper_threshold", "sample_dates", "reference_dates"]
    if "reference_metric" in actual:
        numeric_fields.append("reference_metric")
    for field in numeric_fields:
        np.testing.assert_allclose(actual[field].to_numpy(dtype=float),
                                   expected[field].to_numpy(dtype=float), rtol=1e-10, atol=1e-9, equal_nan=True)


def run():
    manifest = json.loads((OUT / "manifest.json").read_text())
    protocol, routes = manifest["protocol"], manifest["routes"]
    for path, record in manifest["products"].items():
        assert digest(ROOT / path) == record["sha256"], path
    for mapping in ["input_files", "source_code", "protected_original_files"]:
        for path, expected in manifest[mapping].items():
            assert digest(ROOT / path) == expected, path

    def read(name, nullable=False, dates=None):
        return pd.read_csv(OUT / f"{name}.csv", parse_dates=dates or [],
                           dtype={"triggered": "boolean"} if nullable else None)

    members = pd.read_csv(DATA / "route_clustering/profile_members.csv", parse_dates=["payment_date"])
    assert not members.duplicated(["bus_route", "payment_date"]).any()
    assert sorted(members.bus_route.unique()) == routes
    assert members.groupby("payment_date").bus_route.nunique().eq(len(routes)).all()
    assert len(members) == manifest["member_route_dates"]
    assert members.payment_date.nunique() == manifest["common_dates"]
    source = pd.read_csv(DATA / "matched_daily_features.csv", low_memory=False, parse_dates=["payment_date"])
    paired = members.merge(source[["bus_route", "payment_date", "analysis_boardings", "scheduled_service_hours",
                                    "scheduled_departures", "schedule_comparison_eligible"]],
                           on=["bus_route", "payment_date"], validate="one_to_one", suffixes=("", "_source"))
    assert len(paired) == len(members) and paired.schedule_comparison_eligible.eq(True).all()
    for column in ["analysis_boardings", "scheduled_service_hours", "scheduled_departures"]:
        np.testing.assert_allclose(paired[column], paired[f"{column}_source"], atol=1e-8)
    profiles = read("route_day_type_evidence").set_index(["bus_route", "day_type"]).sort_index()
    groups = members.groupby(["bus_route", "day_type"])
    for saved, field in [("total_boardings", "analysis_boardings"), ("total_service_hours", "scheduled_service_hours"),
                          ("total_departures", "scheduled_departures")]:
        np.testing.assert_allclose(profiles[saved], groups[field].sum().sort_index(), rtol=1e-12)
    np.testing.assert_array_equal(profiles.observed_dates, groups.size().sort_index())
    expected_rates = profiles.total_boardings / profiles.total_service_hours.where(profiles.total_service_hours.gt(0))
    expected_valid = (profiles.observed_dates.ge(profiles.index.get_level_values("day_type").map(protocol["minimum_days"]))
                      & profiles.total_service_hours.gt(0) & profiles.positive_zero_service_dates.eq(0))
    np.testing.assert_array_equal(profiles.service_comparison_eligible, expected_valid)
    np.testing.assert_allclose(profiles.boardings_per_bus_hour,
                               expected_rates.where(expected_valid), equal_nan=True)
    issues = members.loc[members.analysis_boardings.gt(0) & members.scheduled_service_hours.eq(0)]
    saved_issues = read("source_issue_dates", dates=["payment_date"])
    pd.testing.assert_index_equal(
        issues.set_index(["bus_route", "payment_date"]).sort_index().index,
        saved_issues.set_index(["bus_route", "payment_date"]).sort_index().index)
    bad = issues.groupby(["bus_route", "day_type"]).size().reindex(profiles.index, fill_value=0)
    np.testing.assert_array_equal(profiles.positive_zero_service_dates, bad)
    expected = independent_rules(members, routes, protocol["tail_quantile"], protocol["ratio_threshold"],
                                 protocol["minimum_days"], protocol["minimum_half_weekdays"], protocol["minimum_cohort"])
    rules = read("rule_evaluations", nullable=True)
    compare_rules(rules, expected)
    assert len(rules) == manifest["rule_evaluations"] == len(routes) * 6
    flags = read("review_signals", nullable=True)
    pd.testing.assert_index_equal(flags.set_index(KEYS).sort_index().index,
                                   rules.loc[rules.triggered.fillna(False)].set_index(KEYS).sort_index().index)
    assert len(flags) == manifest["triggered_evaluations"]
    for row in rules.itertuples():
        if row.family != "weekday_intensity_change":
            part = members.loc[members.bus_route.eq(row.bus_route) & members.day_type.eq(row.day_type)]
        else:
            part = members.loc[members.bus_route.eq(row.bus_route) & members.day_type.eq("Weekday")
                               & members.payment_date.between(protocol["late_start"], protocol["late_end"])]
        np.testing.assert_allclose([row.numerator_boardings, row.denominator_bus_hours],
                                   [part.analysis_boardings.sum(), part.scheduled_service_hours.sum()])
        assert pd.Timestamp(row.first_date) == part.payment_date.min()
        assert pd.Timestamp(row.last_date) == part.payment_date.max()
        assert isinstance(row.reason, str) and len(row.reason) > 10

    # Recreate all threshold settings, not only those with stronger signals.
    sensitivity = read("threshold_evaluations", nullable=True)
    sensitivity_summary = read("threshold_sensitivity_summary")
    for variant, part in sensitivity.groupby("variant"):
        tail, ratio = float(part.tail_quantile.iloc[0]), float(part.ratio_threshold.iloc[0])
        recomputed = independent_rules(members, routes, tail, ratio, protocol["minimum_days"],
                                       protocol["minimum_half_weekdays"], protocol["minimum_cohort"])
        compare_rules(part, recomputed)
        for family, group in part.groupby("family"):
            saved = sensitivity_summary.loc[sensitivity_summary.variant.eq(variant)
                                             & sensitivity_summary.family.eq(family)].iloc[0]
            assert saved.flagged_evaluations == int(group.triggered.sum())
            assert saved.flagged_routes == group.loc[group.triggered.fillna(False)].bus_route.nunique()

    # Rebuild every stratified week resample from the original members.
    dates = members.payment_date - pd.to_timedelta(members.payment_date.dt.dayofweek, unit="D")
    blocks = list(members.groupby(dates))
    early = [part for week, part in blocks if week <= pd.Timestamp(protocol["early_end"])]
    late = [part for week, part in blocks if week >= pd.Timestamp(protocol["late_start"])]
    assert len(early) == len(late) == 6
    rng = np.random.default_rng(protocol["seed"])
    bootstrap = read("bootstrap_evaluations", nullable=True)
    bootstrap_runs = read("bootstrap_runs").set_index("repetition")
    for repetition in range(protocol["bootstrap_repetitions"]):
        a, b = rng.integers(0, 6, size=6), rng.integers(0, 6, size=6)
        sample = pd.concat([early[i] for i in a] + [late[i] for i in b], ignore_index=True)
        recomputed = independent_rules(sample, routes, protocol["tail_quantile"], protocol["ratio_threshold"],
                                       protocol["bootstrap_minimum_days"],
                                       protocol["bootstrap_minimum_half_weekdays"], protocol["minimum_cohort"])
        saved = bootstrap.loc[bootstrap.repetition.eq(repetition)]
        compare_rules(saved, recomputed)
        audit = bootstrap_runs.loc[repetition]
        assert audit.unique_early_weeks == len(set(a)) and audit.unique_late_weeks == len(set(b))
        assert audit.eligible_evaluations == int(saved.eligible.sum())
        assert audit.flagged_evaluations == int(saved.triggered.sum())
    for row in flags.itertuples():
        for prefix, frame, minimum in [
            ("bootstrap", bootstrap, protocol["minimum_supported_resamples"]),
            ("threshold", sensitivity, 1),
        ]:
            part = frame.loc[frame.bus_route.eq(row.bus_route) & frame.family.eq(row.family)
                             & frame.day_type.eq(row.day_type) & frame.eligible]
            count = int((part.triggered.fillna(False) & part.direction.eq(row.direction)).sum())
            assert getattr(row, f"{prefix}_eligible_evaluations") == len(part)
            assert getattr(row, f"{prefix}_same_direction_flags") == count
            expected_value = count / len(part) if len(part) >= minimum else np.nan
            np.testing.assert_allclose(getattr(row, f"{prefix}_retention"), expected_value, equal_nan=True)

    queue = read("route_review_table")
    assert sorted(queue.bus_route) == routes and not queue.bus_route.duplicated().any()
    source_routes = set(issues.bus_route)
    for row in queue.itertuples():
        part = rules.loc[rules.bus_route.eq(row.bus_route)]
        signalled = flags.loc[flags.bus_route.eq(row.bus_route)]
        state = ("source_clarification" if row.bus_route in source_routes else
                 "insufficient_evidence" if not part.eligible.any() else
                 "planning_review" if len(signalled) else "no_rule_triggered")
        assert row.review_state == state
        assert row.flagged_evaluations == len(signalled)
        assert isinstance(row.evidence_summary, str) and row.evidence_summary.strip()
        expected_ids = set(signalled.evidence_id)
        saved_ids = set(row.review_evidence_ids.split("; ")) if pd.notna(row.review_evidence_ids) else set()
        assert saved_ids == expected_ids
        expected_source_ids = set(saved_issues.loc[saved_issues.bus_route.eq(row.bus_route), "evidence_id"])
        saved_source_ids = set(row.source_evidence_ids.split("; ")) if pd.notna(row.source_evidence_ids) else set()
        assert saved_source_ids == expected_source_ids
    assert queue.review_state.value_counts().to_dict() == manifest["state_counts"]
    for state, name in [("planning_review", "planning_review_queue"),
                         ("source_clarification", "source_clarification_queue")]:
        exported = read(name)
        assert set(exported.bus_route) == set(queue.loc[queue.review_state.eq(state), "bus_route"])
        assert "review_evidence_ids" in exported
    assert not flags.loc[flags.bus_route.isin(source_routes), "default_planning_queue"].any()
    assert not queue.automated_service_change.any()
    assert not protocol["composite_score"] and not protocol["automatic_service_change"]
    assert not manifest["ranking_uses_cluster_labels"] and not manifest["ranking_uses_forecasts"]
    forecast_context = read("forecast_context")
    predictions = pd.read_csv(DATA / "october_validation/additional_october_predictions.csv")
    for row in forecast_context.itertuples():
        part = predictions.loc[predictions.bus_route.eq(row.bus_route) & predictions.model.eq(row.strategy)]
        assert row.target_dates == len(part) == 14
        np.testing.assert_allclose(row.mae, (part.prediction - part.actual).abs().mean())
        assert not row.operationally_accepted

    notebook = nbformat.read(ROOT / "notebooks/new_york/10_explainable_route_review.ipynb", as_version=4)
    nbformat.validate(notebook)
    cells = [c for c in notebook.cells if c.cell_type == "code"]
    assert hashlib.sha256("\n\n".join(c.source for c in cells).encode()).hexdigest() == manifest["notebook_code_sha256"]
    for cell in cells:
        assert cell.execution_count is not None and cell.outputs
        assert not any(o.output_type == "error" for o in cell.outputs)
        assert not cell.metadata.get("jupyter", {}).get("outputs_hidden", False)
    result = {
        "inputs_verified": len(manifest["input_files"]), "products_verified": len(manifest["products"]),
        "earlier_artifacts_unchanged": len(manifest["protected_original_files"]), "routes": len(routes),
        "route_dates": len(members), "evaluations_recomputed": len(rules), "signals": len(flags),
        "state_counts": manifest["state_counts"],
        "threshold_settings_recomputed": sensitivity.variant.nunique(),
        "whole_week_resamples_recomputed": protocol["bootstrap_repetitions"],
        "code_cells": len(cells), "saved_outputs": sum(len(c.outputs) for c in cells),
        "figures": sum("image/png" in o.get("data", {}) for c in cells for o in c.outputs),
        "automatic_service_changes": False,
    }
    (ROOT / "reports/route_review/audit.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    run()
