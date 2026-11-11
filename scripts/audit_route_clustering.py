"""Independently reconcile route grouping products with their frozen member observations."""

from pathlib import Path
import hashlib
import json

import nbformat
import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment
from sklearn.metrics import adjusted_rand_score, silhouette_score, silhouette_samples


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/processed/new_york/route_clustering"


def digest(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def run():
    manifest = json.loads((OUT / "manifest.json").read_text())
    protocol = manifest["protocol"]
    features, routes = protocol["features"], manifest["routes"]
    for path, record in manifest["products"].items():
        assert digest(ROOT / path) == record["sha256"], path
    for records in [manifest["input_files"], manifest["source_code"],
                    manifest["protected_original_files"]]:
        for path, expected in records.items():
            assert digest(ROOT / path) == expected, path
    assert digest(ROOT / "data/processed/new_york/feature_manifest.json") == manifest["feature_manifest_sha256"]

    def read(name, dates=None):
        return pd.read_csv(OUT / f"{name}.csv", parse_dates=dates or [])

    coverage = read("date_coverage", ["payment_date"])
    members = read("profile_members", ["payment_date"])
    profiles = read("route_profiles").sort_values("bus_route").reset_index(drop=True)
    assignments = read("route_assignments").sort_values("bus_route").reset_index(drop=True)
    assert manifest["grouping_status"] == "exploratory_only"
    assert assignments.grouping_status.eq("exploratory_only").all()
    assert assignments.bus_route.tolist() == profiles.bus_route.tolist() == routes
    assert not members.duplicated(["bus_route", "payment_date"]).any()
    assert len(members) == manifest["member_route_dates"] == len(routes) * coverage.included.sum()
    assert members.payment_date.nunique() == manifest["included_dates"]
    np.testing.assert_array_equal(coverage.payment_date, pd.date_range(protocol["window_start"], protocol["window_end"]))
    assert members.payment_date.between(protocol["window_start"], protocol["window_end"]).all()
    assert members.groupby("payment_date").bus_route.nunique().eq(len(routes)).all()
    assert members[["analysis_boardings", "scheduled_service_hours", "scheduled_departures",
                    "peak_boardings"]].notna().all().all()

    # Join the member grain back to the verified inputs, without using the profile helper.
    daily = pd.read_csv(ROOT / "data/processed/new_york/matched_daily_features.csv",
                        low_memory=False, parse_dates=["payment_date"])
    hourly = pd.read_csv(ROOT / "data/processed/new_york/matched_hourly_features.csv",
                         parse_dates=["payment_date", "local_hour"])
    daily = daily.loc[daily.bus_route.isin(routes)
                      & daily.payment_date.between(protocol["window_start"], protocol["window_end"])].copy()
    hourly = hourly.loc[hourly.bus_route.isin(routes)
                        & hourly.payment_date.between(protocol["window_start"], protocol["window_end"])].copy()
    assert not daily.duplicated(["bus_route", "payment_date"]).any()
    assert not hourly.duplicated(["bus_route", "local_hour"]).any()
    keys = ["bus_route", "payment_date"]
    actual = daily.set_index(keys).sort_index()
    saved = members.set_index(keys).sort_index()
    source_members = actual.reindex(saved.index)
    assert source_members.schedule_comparison_eligible.eq(True).all()
    for column in ["analysis_boardings", "scheduled_departures", "scheduled_service_hours"]:
        np.testing.assert_allclose(saved[column], source_members[column], rtol=1e-12, atol=1e-8)
    zero_service = members.loc[members.scheduled_service_hours.eq(0)].groupby("bus_route").size().reindex(
        routes, fill_value=0)
    positive_zero_service = members.loc[members.scheduled_service_hours.eq(0)
        & members.analysis_boardings.gt(0)].groupby("bus_route").size().reindex(routes, fill_value=0)
    np.testing.assert_array_equal(assignments.zero_service_dates, zero_service)
    np.testing.assert_array_equal(assignments.positive_boardings_zero_service_dates, positive_zero_service)
    np.testing.assert_array_equal(assignments.service_alignment_review, positive_zero_service.gt(0))
    assert int(positive_zero_service.gt(0).sum()) == manifest["service_alignment_review_routes"]
    hourly["peak"] = hourly.analysis_boardings.where(
        hourly.local_hour.dt.hour.isin([7, 8, 9, 16, 17, 18]), 0.)
    hour_days = hourly.groupby(keys).agg(rows=("local_hour", "size"),
                                        good=("analysis_boardings", "count"),
                                        hourly_sum=("analysis_boardings", "sum"), peak=("peak", "sum"))
    keep_hours = hour_days.reindex(saved.index)
    assert keep_hours.rows.eq(24).all() and keep_hours.good.eq(24).all()
    np.testing.assert_allclose(saved.analysis_boardings, keep_hours.hourly_sum, rtol=0, atol=1e-8)
    np.testing.assert_allclose(saved.peak_boardings, keep_hours.peak, rtol=0, atol=1e-8)
    all_days = actual.join(hour_days)
    eligible = (all_days.schedule_comparison_eligible.eq(True)
                & all_days.analysis_boardings.notna() & all_days.scheduled_departures.ge(0)
                & all_days.scheduled_service_hours.ge(0)
                & all_days.rows.eq(24) & all_days.good.eq(24)
                & np.isclose(all_days.analysis_boardings, all_days.hourly_sum, rtol=0, atol=1e-6))
    expected_dates = eligible.groupby(level="payment_date").agg(["sum", "size"])
    expected_dates = expected_dates.index[(expected_dates["sum"] == len(routes))
                                         & (expected_dates["size"] == len(routes))]
    assert set(expected_dates) == set(coverage.loc[coverage.included, "payment_date"])

    # Original-unit profile arithmetic, independently aggregated.
    by_type = members.groupby(["bus_route", "day_type"])
    means = by_type[["analysis_boardings", "scheduled_service_hours", "scheduled_departures"]].mean()
    indexed = profiles.set_index("bus_route")
    for kind in ["Weekday", "Saturday", "Sunday"]:
        values = means.xs(kind, level="day_type").reindex(routes)
        for target, source in [("boardings", "analysis_boardings"),
                               ("service_hours", "scheduled_service_hours"),
                               ("departures", "scheduled_departures")]:
            np.testing.assert_allclose(indexed[f"mean_{kind.lower()}_{target}"], values[source], rtol=1e-12)
        counts = by_type.size().xs(kind, level="day_type").reindex(routes)
        np.testing.assert_array_equal(indexed[f"{kind.lower()}_days"], counts)
        assert counts.ge(protocol["minimum_days"][kind]).all()
    wd = members.loc[members.day_type.eq("Weekday")].groupby("bus_route")
    np.testing.assert_allclose(indexed.weekday_peak_share,
                               wd.peak_boardings.sum() / wd.analysis_boardings.sum())
    for destination, metric in [("weekend_boarding_ratio", "boardings"),
                                 ("weekend_service_ratio", "service_hours")]:
        expected = (indexed[f"mean_saturday_{metric}"] + indexed[f"mean_sunday_{metric}"]) / (
            2 * indexed[f"mean_weekday_{metric}"])
        np.testing.assert_allclose(indexed[destination], expected)
    np.testing.assert_allclose(indexed.log_weekday_boardings, np.log1p(indexed.mean_weekday_boardings))
    np.testing.assert_allclose(indexed.log_weekday_service_hours, np.log1p(indexed.mean_weekday_service_hours))

    # Reconstruct scaled distances and assignments without loading a pickle.
    params = read("scaler_parameters").set_index("feature").loc[features]
    x = profiles[features].to_numpy()
    np.testing.assert_allclose(params.center, np.median(x, axis=0))
    np.testing.assert_allclose(params.scale, np.percentile(x, 75, axis=0) - np.percentile(x, 25, axis=0))
    np.testing.assert_allclose(params.weight, protocol["weights"])
    np.testing.assert_allclose(np.square(params.weight.iloc[:3]).sum(), 1.)
    np.testing.assert_allclose(np.square(params.weight.iloc[3:]).sum(), 1.)
    scaled = (x - params.center.to_numpy()) / params.scale.to_numpy() * params.weight.to_numpy()
    np.testing.assert_allclose(read("scaled_features").sort_values("bus_route")[features], scaled, atol=1e-12)
    centres = read("cluster_centres").sort_values("native_label")
    distances = np.linalg.norm(scaled[:, None, :] - centres[features].to_numpy()[None, :, :], axis=2)
    labels = assignments.native_label.to_numpy()
    np.testing.assert_array_equal(distances.argmin(axis=1), labels)
    np.testing.assert_allclose(assignments.centroid_distance, distances[np.arange(len(routes)), labels], atol=1e-7)
    np.testing.assert_allclose(assignments.silhouette, silhouette_samples(scaled, labels), atol=1e-10)
    np.testing.assert_allclose(manifest["silhouette"], silhouette_score(scaled, labels))
    for native in centres.native_label:
        np.testing.assert_allclose(scaled[labels == native].mean(axis=0),
                                   centres.set_index("native_label").loc[native, features].to_numpy(dtype=float), atol=1e-10)
    candidates = read("kmeans_candidates")
    eligible_candidates = candidates.loc[candidates.min_cluster_size.ge(protocol["minimum_cluster_size"])]
    if len(eligible_candidates):
        best = eligible_candidates.silhouette.max()
        selected = eligible_candidates.loc[
            eligible_candidates.silhouette.ge(best - protocol["silhouette_tolerance"]), "k"].min()
        assert selected == manifest["selected_k"]
        assert manifest["selection_status"] == "passes_descriptive_size_screen"
    else:
        assert manifest["selection_status"] == "no_partition_passes_size_screen_descriptive_only"
    assert assignments.group_id.nunique() == manifest["selected_k"]
    group_summary = read("group_summary").set_index("group_id")
    np.testing.assert_array_equal(group_summary.routes, assignments.groupby("group_id").size())
    for group, part in assignments.groupby("group_id"):
        representative = part.loc[part.centroid_distance.idxmin()]
        assert representative.representative
        assert part.representative.sum() == 1
        assert group_summary.loc[group, "representative_route"] == representative.bus_route

    # Recompute invariant stability scores and route retention from all saved refits.
    bootstrap = read("bootstrap_scores")
    saved_bootstrap = read("bootstrap_assignments")
    assert len(bootstrap) == protocol["bootstrap_repetitions"]
    matrices, aligned_matrices = [], []
    rng = np.random.default_rng(protocol["seed"])
    n_weeks = (members.payment_date - pd.to_timedelta(members.payment_date.dt.dayofweek, unit="D")).nunique()
    for row in bootstrap.itertuples():
        draws = rng.integers(0, n_weeks, size=n_weeks)
        assert row.sampled_unique_weeks == len(set(draws))
        if not row.valid:
            assert pd.notna(row.reason)
            continue
        part = saved_bootstrap.loc[saved_bootstrap.repetition.eq(row.repetition)].sort_values("bus_route")
        assert part.bus_route.tolist() == routes
        values = part.raw_label.to_numpy()
        np.testing.assert_allclose(row.ari, adjusted_rand_score(labels, values))
        matrix = np.array([[(labels == a)[values == b].sum()
                           for b in range(manifest["selected_k"])] for a in range(manifest["selected_k"])])
        a, b = linear_sum_assignment(-matrix)
        mapping = dict(zip(b, a))
        aligned = np.array([mapping[value] for value in values])
        np.testing.assert_array_equal(part.aligned_label, aligned)
        matrices.append(values)
        aligned_matrices.append(aligned)
    assert len(matrices) == manifest["valid_bootstraps"]
    retention = (np.array(aligned_matrices) == labels).mean(axis=0)
    np.testing.assert_allclose(assignments.bootstrap_retention, retention)
    matrices = np.array(matrices)
    expected_coassignment = (matrices[:, :, None] == matrices[:, None, :]).mean(axis=0)
    saved_coassignment = read("coassignment").pivot(
        index="bus_route", columns="peer_route", values="coassignment_frequency").loc[routes, routes]
    np.testing.assert_allclose(saved_coassignment, expected_coassignment)
    np.testing.assert_allclose(manifest["median_bootstrap_ari"], bootstrap.loc[bootstrap.valid, "ari"].median())
    nearest = np.sort(distances, axis=1)
    margin = (nearest[:, 1] - nearest[:, 0]) / np.maximum(nearest[:, 1], 1e-12)
    np.testing.assert_allclose(assignments.centroid_margin, margin, atol=1e-7)
    expected_review = ((retention < protocol["assignment_review_below"])
                       | (margin < protocol["margin_review_below"])
                       | (assignments.silhouette.to_numpy() < 0)
                       | (len(matrices) < protocol["minimum_valid_bootstraps"]))
    np.testing.assert_array_equal(assignments.group_membership_review, expected_review)
    assert int(expected_review.sum()) == manifest["membership_review_routes"]
    for prefix, label_name, score_name in [
        ("sensitivity", "variant", "ari_to_primary"), ("temporal", "period", "ari_to_full_window")
    ]:
        membership, scores = read(f"{prefix}_assignments"), read(f"{prefix}_scores")
        for row in scores.to_dict("records"):
            part = membership.loc[membership[label_name].eq(row[label_name])].sort_values("bus_route")
            assert part.bus_route.tolist() == routes
            np.testing.assert_allclose(row[score_name], adjusted_rand_score(labels, part.label))
    temporal = read("temporal_assignments")
    first = temporal.loc[temporal.period.eq("first_six_weeks")].sort_values("bus_route").label
    last = temporal.loc[temporal.period.eq("last_six_weeks")].sort_values("bus_route").label
    np.testing.assert_allclose(manifest["temporal_half_ari"], adjusted_rand_score(first, last))

    notebook = nbformat.read(ROOT / "notebooks/new_york/09_route_profiles_and_clustering.ipynb", as_version=4)
    nbformat.validate(notebook)
    code_cells = [cell for cell in notebook.cells if cell.cell_type == "code"]
    source = "\n\n".join(cell.source for cell in code_cells)
    assert hashlib.sha256(source.encode()).hexdigest() == manifest["notebook_code_sha256"]
    for cell in code_cells:
        assert cell.execution_count is not None and cell.outputs
        assert not any(output.output_type == "error" for output in cell.outputs)
        assert not cell.metadata.get("jupyter", {}).get("outputs_hidden", False)
    assert not manifest["operational_use"] and not manifest["crowding_or_efficiency_labels"]
    result = {
        "input_files_verified": len(manifest["input_files"]),
        "products_verified": len(manifest["products"]),
        "earlier_files_unchanged": len(manifest["protected_original_files"]),
        "routes": len(routes), "included_dates": manifest["included_dates"], "member_route_dates": len(members),
        "selected_groups": manifest["selected_k"], "silhouette": manifest["silhouette"],
        "bootstrap_refits_checked": len(matrices), "membership_review_routes": int(expected_review.sum()),
        "code_cells": len(code_cells), "saved_outputs": sum(len(cell.outputs) for cell in code_cells),
        "figures": sum("image/png" in output.get("data", {}) for cell in code_cells for output in cell.outputs),
        "operational_use_claimed": False,
    }
    destination = ROOT / "reports/route_clustering/audit.json"
    destination.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    run()
