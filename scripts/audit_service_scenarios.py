"""Verify paired baselines, scenario formulas, limits and transfer conservation independently."""

from pathlib import Path
import hashlib
import json
import nbformat
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/processed/new_york"
OUT = DATA / "service_scenarios"


def digest(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def run():
    manifest = json.loads((OUT / "manifest.json").read_text())
    protocol = manifest["protocol"]
    for mapping in ["input_files", "source_code", "protected_original_files"]:
        for path, expected in manifest[mapping].items():
            assert digest(ROOT / path) == expected, path
    for path, record in manifest["products"].items():
        assert digest(ROOT / path) == record["sha256"], path

    def read(name, scenarios=False):
        return pd.read_csv(OUT / f"{name}.csv", dtype={
            "retention_limit_pass": "boolean", "added_hours_limit_pass": "boolean"
        } if scenarios else None)

    members = pd.read_csv(DATA / "route_clustering/profile_members.csv", parse_dates=["payment_date"])
    review = pd.read_csv(DATA / "route_review/route_review_table.csv").set_index("bus_route")
    baseline = read("scenario_baselines").set_index(["bus_route", "day_type"]).sort_index()
    assert not members.duplicated(["bus_route", "payment_date"]).any()
    assert len(members) == manifest["member_route_dates"]
    assert members.payment_date.nunique() == manifest["common_dates"]
    assert members.groupby("payment_date").bus_route.nunique().eq(len(manifest["routes"])).all()
    assert members.payment_date.min() == pd.Timestamp(protocol["window_start"])
    assert members.payment_date.max() == pd.Timestamp(protocol["window_end"])
    assert len(baseline) == manifest["baseline_profiles"] == len(manifest["routes"]) * 3
    raw_daily = pd.read_csv(DATA / "matched_daily_features.csv", low_memory=False, parse_dates=["payment_date"])
    source = raw_daily.set_index(["bus_route", "payment_date"])
    paired = members.set_index(["bus_route", "payment_date"])
    source = source.reindex(paired.index)
    assert source.schedule_comparison_eligible.eq(True).all()
    for column in ["analysis_boardings", "scheduled_departures", "scheduled_service_hours"]:
        np.testing.assert_allclose(paired[column], source[column], rtol=1e-12, atol=1e-8)
    grouped = members.groupby(["bus_route", "day_type"])
    for saved, column in [("total_boardings", "analysis_boardings"),
                           ("total_departures", "scheduled_departures"), ("total_bus_hours", "scheduled_service_hours")]:
        np.testing.assert_allclose(baseline[saved], grouped[column].sum().sort_index(), rtol=1e-12)
    np.testing.assert_array_equal(baseline.observed_dates, grouped.size().sort_index())
    for field, total in [("mean_boardings", "total_boardings"), ("mean_departures", "total_departures"),
                          ("mean_bus_hours", "total_bus_hours")]:
        np.testing.assert_allclose(baseline[field], baseline[total] / baseline.observed_dates)
    issues = members.loc[members.analysis_boardings.gt(0) & members.scheduled_service_hours.eq(0)]
    source_routes = set(issues.bus_route) | set(review.loc[review.review_state.eq("source_clarification")].index)
    for (route, kind), row in baseline.iterrows():
        part = grouped.get_group((route, kind))
        dates_hash = hashlib.sha256("\n".join(sorted(part.payment_date.dt.strftime("%Y-%m-%d"))).encode()).hexdigest()
        assert row.observation_dates_sha256 == dates_hash
        assert pd.Timestamp(row.first_date) == part.payment_date.min()
        assert pd.Timestamp(row.last_date) == part.payment_date.max()
        assert pd.Timestamp(review.loc[route, "review_period_start"]) == members.payment_date.min()
        assert pd.Timestamp(review.loc[route, "review_period_end"]) == members.payment_date.max()
        expected_eligible = (route not in source_routes and review.loc[route, "review_state"] != "insufficient_evidence"
                             and row.observed_dates >= protocol["minimum_days"][kind]
                             and row.total_departures > 0 and row.total_bus_hours > 0)
        assert row.baseline_eligible == expected_eligible
        expected_trip_rate = row.total_boardings / row.total_departures if expected_eligible else np.nan
        expected_hour_rate = row.total_boardings / row.total_bus_hours if expected_eligible else np.nan
        np.testing.assert_allclose(row.boardings_per_departure, expected_trip_rate, equal_nan=True)
        np.testing.assert_allclose(row.boardings_per_bus_hour, expected_hour_rate, equal_nan=True)
    assert int(baseline.baseline_eligible.sum()) == manifest["eligible_profiles"]
    assert int((~baseline.baseline_eligible).sum()) == manifest["withheld_profiles"]

    checked_rows = 0

    def check_rows(frame):
        nonlocal checked_rows
        for row in frame.itertuples():
            base = baseline.loc[(row.bus_route, row.day_type)]
            assert row.baseline_id == base.baseline_id
            assert row.observation_dates_sha256 == base.observation_dates_sha256
            assert row.baseline_eligible == base.baseline_eligible
            assert row.frequency_factor > 0 and row.demand_factor >= 0
            np.testing.assert_allclose([row.mean_departures, row.mean_bus_hours, row.mean_boardings],
                                       [base.mean_departures, base.mean_bus_hours, base.mean_boardings])
            if not base.baseline_eligible:
                for field in ["scenario_mean_departures", "scenario_mean_bus_hours", "scenario_mean_boardings",
                              "scenario_boardings_per_departure", "scenario_boardings_per_bus_hour",
                              "delta_mean_departures", "delta_mean_bus_hours"]:
                    assert pd.isna(getattr(row, field))
                assert pd.isna(row.retention_limit_pass) and pd.isna(row.added_hours_limit_pass)
                assert row.arithmetic_status == "withheld"
            else:
                n = base.mean_departures * row.frequency_factor
                h = base.mean_bus_hours * row.frequency_factor
                d = base.mean_boardings * row.demand_factor
                np.testing.assert_allclose([row.scenario_mean_departures, row.scenario_mean_bus_hours,
                                           row.scenario_mean_boardings], [n, h, d])
                np.testing.assert_allclose([row.delta_mean_departures, row.delta_mean_bus_hours],
                                           [n - base.mean_departures, h - base.mean_bus_hours], atol=1e-9)
                np.testing.assert_allclose([row.scenario_boardings_per_departure, row.scenario_boardings_per_bus_hour],
                                           [d / n, d / h])
                for field in ["boardings_per_departure", "boardings_per_bus_hour"]:
                    expected_change = row.demand_factor / row.frequency_factor - 1 if base.mean_boardings > 0 else np.nan
                    np.testing.assert_allclose(getattr(row, f"change_{field}_fraction"), expected_change,
                                               atol=1e-10, equal_nan=True)
                retention = row.frequency_factor >= row.minimum_retained_fraction - 1e-12
                assert bool(row.retention_limit_pass) == retention
                if pd.isna(row.max_added_bus_hours):
                    assert pd.isna(row.added_hours_limit_pass)
                    expected_status = "within_retention_limit_budget_unspecified"
                else:
                    within = h - base.mean_bus_hours <= row.max_added_bus_hours + 1e-10
                    assert bool(row.added_hours_limit_pass) == within
                    expected_status = ("within_declared_arithmetic_limits" if within else "exceeds_added_hours_limit")
                if not retention:
                    expected_status = "below_retained_service_limit"
                assert row.arithmetic_status == expected_status
            assert row.timetable_feasibility == "not_assessed"
            assert not row.automatic_service_change
            checked_rows += 1

    tables = {}
    for name in ["frequency_comparisons", "focus_comparison", "budget_sensitivity", "demand_sensitivity",
                 "transfer_comparisons", "constraint_examples"]:
        tables[name] = read(name, scenarios=True)
        check_rows(tables[name])
    frequencies = tables["frequency_comparisons"]
    assert len(frequencies) == manifest["frequency_cases"] == len(baseline) * len(protocol["frequency_factors"])
    assert not frequencies.case_id.duplicated().any()
    assert set(frequencies.frequency_factor) == set(protocol["frequency_factors"])
    assert frequencies.demand_factor.eq(1.).all()
    assert frequencies.arithmetic_status.value_counts().to_dict() == manifest["status_counts"]
    counts = frequencies.groupby(["day_type", "frequency_factor", "arithmetic_status"]).size().rename("cases").reset_index()
    saved_counts = read("case_summary")
    pd.testing.assert_frame_equal(saved_counts.sort_values(list(counts.columns[:-1])).reset_index(drop=True),
                                   counts.sort_values(list(counts.columns[:-1])).reset_index(drop=True))
    assert len(tables["budget_sensitivity"]) == len(protocol["budget_limits"]) * len(protocol["frequency_factors"])
    assert len(tables["demand_sensitivity"]) == len(protocol["demand_factors"]) * len(protocol["frequency_factors"])
    assert tables["demand_sensitivity"].bus_route.eq(protocol["focus_route"]).all()
    identity = frequencies.loc[frequencies.frequency_factor.eq(1.) & frequencies.baseline_eligible]
    np.testing.assert_allclose(identity.delta_mean_bus_hours, 0.)
    np.testing.assert_allclose(identity.delta_mean_departures, 0.)

    transfer = tables["transfer_comparisons"]
    summary = read("transfer_summary")
    assert len(summary) == manifest["transfer_cases"] == len(protocol["transfer_cases"])
    for case in protocol["transfer_cases"]:
        rows = transfer.loc[transfer.case_id.eq(case["case_id"])]
        assert set(rows.bus_route) == {case["donor"], case["recipient"]} and len(rows) == 2
        assert rows.observation_dates_sha256.nunique() == 1
        a = rows.loc[rows.transfer_role.eq("donor")].iloc[0]
        b = rows.loc[rows.transfer_role.eq("recipient")].iloc[0]
        assert a.bus_route == case["donor"] and b.bus_route == case["recipient"]
        np.testing.assert_allclose([a.delta_mean_bus_hours, b.delta_mean_bus_hours],
                                   [-case["hours"], case["hours"]], atol=1e-9)
        np.testing.assert_allclose(rows.scenario_mean_bus_hours.sum(), rows.mean_bus_hours.sum(), atol=1e-9)
        np.testing.assert_allclose(rows.scenario_mean_boardings, rows.mean_boardings)
        total = summary.loc[summary.case_id.eq(case["case_id"])].iloc[0]
        np.testing.assert_allclose([total.baseline_total_mean_bus_hours, total.scenario_total_mean_bus_hours],
                                   [rows.mean_bus_hours.sum(), rows.scenario_mean_bus_hours.sum()])
        np.testing.assert_allclose(total.net_mean_bus_hours_change, 0., atol=1e-9)
        np.testing.assert_allclose(total.net_mean_departures_change, rows.delta_mean_departures.sum(), atol=1e-9)
        assert total.retention_limits_pass == bool(rows.retention_limit_pass.all())
        assert total.timetable_feasibility == "not_assessed" and not total.automatic_service_change
    overlap = pd.read_csv(DATA / "route_overlap.csv")
    pair = {protocol["transfer_cases"][0]["donor"], protocol["transfer_cases"][0]["recipient"]}
    pair_context = overlap.loc[overlap.route_a.isin(pair) & overlap.route_b.isin(pair)].reset_index(drop=True)
    pd.testing.assert_frame_equal(read("transfer_corridor_context"), pair_context)
    for flag in ["operational_feasibility_established", "forecast_used_as_demand", "demand_response_estimated",
                  "passenger_benefit_measured", "integer_timetable_generated", "automatic_service_change"]:
        assert not manifest[flag]
    notebook = nbformat.read(ROOT / "notebooks/new_york/11_service_frequency_scenarios.ipynb", as_version=4)
    nbformat.validate(notebook)
    code_cells = [c for c in notebook.cells if c.cell_type == "code"]
    source_hash = hashlib.sha256("\n\n".join(c.source for c in code_cells).encode()).hexdigest()
    assert source_hash == manifest["notebook_code_sha256"]
    for cell in code_cells:
        assert cell.execution_count is not None and cell.outputs
        assert not any(o.output_type == "error" for o in cell.outputs)
        assert not cell.metadata.get("jupyter", {}).get("outputs_hidden", False)
    result = {
        "inputs_verified": len(manifest["input_files"]), "products_verified": len(manifest["products"]),
        "earlier_artifacts_unchanged": len(manifest["protected_original_files"]),
        "baseline_profiles": len(baseline), "eligible_profiles": manifest["eligible_profiles"],
        "withheld_profiles": manifest["withheld_profiles"], "frequency_cases": len(frequencies),
        "scenario_rows_formula_checked": checked_rows, "status_counts": manifest["status_counts"],
        "transfer_cases_conserved": len(summary),
        "code_cells": len(code_cells), "saved_outputs": sum(len(c.outputs) for c in code_cells),
        "figures": sum("image/png" in o.get("data", {}) for c in code_cells for o in c.outputs),
        "operational_feasibility_claimed": False, "automatic_service_changes": False,
    }
    (ROOT / "reports/service_scenarios/audit.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    run()
