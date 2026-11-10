"""K-Means and DBSCAN clustering of scheduled route feature profiles.

Clusters describe similarities in supplied timetable and stop-network features.
They do not predict demand or describe congestion, occupancy, efficiency, or
actual operating performance.
"""

from __future__ import annotations

import argparse
import json
import importlib
import math
import warnings
from pathlib import Path
from typing import Any

import joblib
import matplotlib
import numpy as np
import polars as pl
from matplotlib import pyplot as plt
from sklearn.cluster import DBSCAN, KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import davies_bouldin_score, silhouette_score
from sklearn.neighbors import NearestNeighbors
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, StandardScaler
from sklearn.impute import SimpleImputer

RANDOM_SEED = 42
SILHOUETTE_SAMPLE_SIZE = 2000
KMEANS_CANDIDATES = tuple(range(2, 11))
DBSCAN_EPS_QUANTILES = (0.50, 0.60, 0.70, 0.80, 0.90, 0.95, 0.98)
MIN_DBSCAN_INLIER_FRACTION = 0.10

BASE_CONTINUOUS_FEATURES = (
    "total_scheduled_trip_records",
    "unique_stop_count",
    "average_first_stop_headway_seconds",
    "peak_departure_share",
    "scheduled_service_span_seconds",
    "shared_stop_ratio",
)
BASE_BINARY_INDICATORS = (
    "headway_missing",
    "service_span_missing",
    "shared_stop_ratio_missing",
    "peak_departure_share_missing",
)
LOG_FEATURE_NAMES = (
    "total_scheduled_trip_records",
    "unique_stop_count",
    "average_first_stop_headway_seconds",
    "scheduled_service_span_seconds",
)


def _log_selected_features(values: np.ndarray, indices: tuple[int, ...]) -> np.ndarray:
    """Apply log1p only to positively scaled volume/time dimensions."""
    transformed = np.asarray(values, dtype=np.float64).copy()
    for index in indices:
        # Preserve NaN so the downstream training-only imputer can handle it.
        valid = np.isfinite(transformed[:, index])
        if np.any(transformed[valid, index] < 0):
            raise ValueError("Log-scaled route features must be nonnegative")
        transformed[valid, index] = np.log1p(transformed[valid, index])
    return transformed


def _make_preprocessor(feature_columns: tuple[str, ...]) -> list[tuple[str, Any]]:
    log_indices = tuple(index for index, name in enumerate(feature_columns) if name in LOG_FEATURE_NAMES)
    transform_function = _log_selected_features
    if __name__ == "__main__":
        # A `python -m` entry point runs as __main__; use the package-imported
        # copy so persisted sklearn pipelines remain loadable in another process.
        transform_function = importlib.import_module("routeranker.clustering.route_clusters")._log_selected_features
    return [
        ("log1p", FunctionTransformer(transform_function, kw_args={"indices": log_indices}, validate=False)),
        ("imputer", SimpleImputer(strategy="median", keep_empty_features=True)),
        ("scaler", StandardScaler()),
    ]


def _new_kmeans_pipeline(feature_columns: tuple[str, ...], clusters: int, seed: int) -> Pipeline:
    return Pipeline(_make_preprocessor(feature_columns) + [
        ("clusterer", KMeans(n_clusters=clusters, random_state=seed, n_init=20, algorithm="lloyd")),
    ])


def _new_dbscan_pipeline(feature_columns: tuple[str, ...], eps: float, min_samples: int) -> Pipeline:
    return Pipeline(_make_preprocessor(feature_columns) + [
        ("clusterer", DBSCAN(eps=eps, min_samples=min_samples, metric="euclidean", algorithm="auto")),
    ])


def _safe_silhouette(matrix: np.ndarray, labels: np.ndarray, seed: int) -> tuple[float | None, int, str | None]:
    unique = np.unique(labels)
    if len(unique) < 2 or len(unique) >= len(labels):
        return None, 0, "Silhouette requires at least two clusters and fewer clusters than observations."
    sample_size = min(SILHOUETTE_SAMPLE_SIZE, len(labels))
    try:
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="Could not find the number of physical cores.*")
            score = float(silhouette_score(matrix, labels, metric="euclidean", sample_size=sample_size, random_state=seed))
        return score, sample_size, None
    except ValueError as exc:
        return None, 0, str(exc)


def _safe_davies_bouldin(matrix: np.ndarray, labels: np.ndarray) -> float | None:
    unique = np.unique(labels)
    if len(unique) < 2 or len(unique) >= len(labels):
        return None
    try:
        return float(davies_bouldin_score(matrix, labels))
    except ValueError:
        return None


def _cluster_sizes(labels: np.ndarray, noise_label: int | None = None) -> list[dict[str, int]]:
    values, counts = np.unique(labels, return_counts=True)
    return [
        {"cluster_id": int(label), "route_count": int(count)}
        for label, count in zip(values, counts)
        if noise_label is None or int(label) != noise_label
    ]


def _evaluate_kmeans_candidate(matrix: np.ndarray, labels: np.ndarray, estimator: KMeans, seed: int) -> dict[str, Any]:
    score, sample_size, reason = _safe_silhouette(matrix, labels, seed)
    return {
        "algorithm": "KMeans",
        "n_clusters": int(len(np.unique(labels))),
        "silhouette_score": score,
        "silhouette_sample_size": sample_size,
        "silhouette_note": reason,
        "davies_bouldin_index": _safe_davies_bouldin(matrix, labels),
        "noise_count": 0,
        "inlier_count": int(len(labels)),
        "inertia": float(estimator.inertia_),
        "cluster_sizes": _cluster_sizes(labels),
    }


def _evaluate_dbscan_candidate(
    matrix: np.ndarray,
    labels: np.ndarray,
    eps: float,
    min_samples: int,
    seed: int,
) -> dict[str, Any]:
    noise_count = int(np.sum(labels == -1))
    inliers = labels != -1
    inlier_labels = labels[inliers]
    score, sample_size, reason = _safe_silhouette(matrix[inliers], inlier_labels, seed) if inliers.any() else (None, 0, "DBSCAN marked every route as noise.")
    cluster_count = int(len(set(inlier_labels.tolist())))
    inlier_count = int(inliers.sum())
    min_inliers = max(2 * min_samples, math.ceil(MIN_DBSCAN_INLIER_FRACTION * len(labels)))
    eligible = cluster_count >= 2 and inlier_count >= min_inliers and score is not None
    return {
        "algorithm": "DBSCAN",
        "eps": float(eps),
        "min_samples": int(min_samples),
        "n_clusters": cluster_count,
        "silhouette_score": score,
        "silhouette_sample_size": sample_size,
        "silhouette_note": reason,
        "davies_bouldin_index": _safe_davies_bouldin(matrix[inliers], inlier_labels) if cluster_count >= 2 else None,
        "noise_count": noise_count,
        "noise_fraction": noise_count / len(labels),
        "inlier_count": inlier_count,
        "selection_eligible": eligible,
        "selection_rule": f"At least two non-noise clusters, a valid silhouette, and at least {MIN_DBSCAN_INLIER_FRACTION:.0%} inliers (minimum {min_inliers} routes).",
        "cluster_sizes": _cluster_sizes(labels, noise_label=-1),
    }


def _profile_interpretation(profile: dict[str, Any], baseline: dict[str, float], algorithm: str) -> str:
    """Build restrained descriptions from median schedule-feature comparisons."""
    if algorithm == "DBSCAN" and profile["cluster_id"] == -1:
        return "Sparse in the selected standardized schedule-feature space at the chosen DBSCAN radius; noise is not a data-quality or service-performance judgment."
    descriptors: list[str] = []
    for key, label in (
        ("median_total_scheduled_trip_records", "scheduled trip-record volume"),
        ("median_unique_stop_count", "stop count per route"),
        ("median_peak_departure_share", "share of template-week departures in the defined peak windows"),
        ("median_scheduled_service_span_hours", "scheduled service span"),
        ("median_shared_stop_ratio", "fraction of stops shared with another route"),
    ):
        value = profile.get(key)
        reference = baseline.get(key)
        if value is None or reference is None or math.isclose(value, reference, rel_tol=0.05, abs_tol=1e-9):
            continue
        direction = "above" if value > reference else "below"
        descriptors.append(f"{label} {direction} the active-route median")
    miss_rate = profile.get("headway_missing_rate", 0.0)
    if miss_rate >= 0.50:
        descriptors.append("headways unavailable for at least half the routes")
    elif profile.get("median_average_first_stop_headway_seconds") is not None:
        headway = profile["median_average_first_stop_headway_seconds"]
        baseline_headway = baseline.get("median_average_first_stop_headway_seconds")
        if baseline_headway and not math.isclose(headway, baseline_headway, rel_tol=0.10, abs_tol=1):
            direction = "shorter" if headway < baseline_headway else "longer"
            descriptors.append(f"{direction} median scheduled first-stop headway than the active-route median")
    if not descriptors:
        return "Median values are close to the active-route baseline across the profiled schedule features."
    return "; ".join(descriptors[:3]) + ". These describe schedule features only."


def _profile_clusters(
    raw_routes: pl.DataFrame,
    active_ids: list[str],
    model_labels: dict[str, np.ndarray],
) -> pl.DataFrame:
    """Summarize each cluster from the original, non-normalized feature rows."""
    active = raw_routes.filter(pl.col("route_id").is_in(active_ids)).with_columns(
        (
            pl.col("peak_scheduled_departures_per_template_week")
            / (pl.col("peak_scheduled_departures_per_template_week") + pl.col("off_peak_scheduled_departures_per_template_week"))
        ).alias("peak_departure_share")
    )
    profile_columns = {
        "median_total_scheduled_trip_records": pl.col("total_scheduled_trip_records").median(),
        "median_unique_stop_count": pl.col("unique_stop_count").median(),
        "median_average_first_stop_headway_seconds": pl.col("average_first_stop_headway_seconds").median(),
        "headway_missing_rate": pl.col("headway_missing").mean(),
        "median_peak_departure_share": pl.col("peak_departure_share").median(),
        "median_peak_scheduled_departures_per_template_week": pl.col("peak_scheduled_departures_per_template_week").median(),
        "median_off_peak_scheduled_departures_per_template_week": pl.col("off_peak_scheduled_departures_per_template_week").median(),
        "median_scheduled_service_span_hours": pl.col("scheduled_service_span_seconds").median() / 3600.0,
        "median_shared_stop_ratio": pl.col("shared_stop_ratio").median(),
    }
    baseline = {
        "median_total_scheduled_trip_records": float(active["total_scheduled_trip_records"].median()),
        "median_unique_stop_count": float(active["unique_stop_count"].median()),
        "median_average_first_stop_headway_seconds": float(active["average_first_stop_headway_seconds"].median()),
        "median_peak_departure_share": float(active["peak_departure_share"].median()),
        "median_scheduled_service_span_hours": float(active["scheduled_service_span_seconds"].median() / 3600.0),
        "median_shared_stop_ratio": float(active["shared_stop_ratio"].median()),
    }
    results: list[dict[str, Any]] = []
    for algorithm, labels in model_labels.items():
        prediction = pl.DataFrame({"route_id": active_ids, "cluster_id": labels.astype(np.int64)})
        joined = active.join(prediction, on="route_id", how="inner")
        for row in joined.group_by("cluster_id").agg(
            pl.len().alias("route_count"), *[expression.alias(name) for name, expression in profile_columns.items()]
        ).sort("cluster_id").iter_rows(named=True):
            profile = {
                "algorithm": algorithm,
                "cluster_id": int(row["cluster_id"]),
                "cluster_name": "DBSCAN noise" if algorithm == "DBSCAN" and int(row["cluster_id"]) == -1 else f"{algorithm} cluster {int(row['cluster_id'])}",
                "route_count": int(row["route_count"]),
                **{key: (float(value) if value is not None else None) for key, value in row.items() if key not in {"cluster_id", "route_count"}},
            }
            profile["interpretation"] = _profile_interpretation(profile, baseline, algorithm)
            results.append(profile)
    return pl.DataFrame(results, infer_schema_length=None)


def _distribution_profile(raw: pl.DataFrame, normalized: pl.DataFrame, active_mask: np.ndarray) -> tuple[pl.DataFrame, dict[str, Any]]:
    """Inspect raw distributions and missingness before model fitting."""
    quality_columns = (
        "total_scheduled_trip_records", "unique_stop_count", "average_first_stop_headway_seconds",
        "headway_interval_count", "peak_scheduled_departures_per_template_week",
        "off_peak_scheduled_departures_per_template_week", "scheduled_service_span_seconds",
        "peak_departure_share", "shared_stop_ratio", "headway_missing", "service_span_missing",
        "shared_stop_ratio_missing", "peak_departure_share_missing",
    )
    raw = raw.with_columns(
        (pl.col("peak_scheduled_departures_per_template_week") /
         (pl.col("peak_scheduled_departures_per_template_week") + pl.col("off_peak_scheduled_departures_per_template_week")))
        .alias("peak_departure_share")
    ).with_columns(pl.col("peak_departure_share").is_null().cast(pl.Int8).alias("peak_departure_share_missing"))
    active = raw.filter(pl.Series("active", active_mask))
    rows: list[dict[str, Any]] = []
    for feature in quality_columns:
        for population, frame in (("all_routes", raw), ("routes_with_trip_records", active)):
            series = frame[feature]
            observed = series.drop_nulls()
            rows.append({
                "feature": feature,
                "population": population,
                "row_count": frame.height,
                "missing_count": series.null_count(),
                "missing_rate": series.null_count() / frame.height if frame.height else 0.0,
                "minimum": observed.min() if observed.len() else None,
                "q25": observed.quantile(0.25) if observed.len() else None,
                "median": observed.median() if observed.len() else None,
                "q75": observed.quantile(0.75) if observed.len() else None,
                "maximum": observed.max() if observed.len() else None,
                "distinct_observed_values": observed.n_unique(),
            })
    normalized_nulls = {column: normalized[column].null_count() for column in normalized.columns if normalized[column].null_count()}
    profile = {
        "total_route_rows": raw.height,
        "routes_with_trip_records": active.height,
        "routes_without_trip_records": raw.height - active.height,
        "normalized_input_rows": normalized.height,
        "normalized_input_null_counts": normalized_nulls,
        "active_headway_missing_count": active["average_first_stop_headway_seconds"].null_count(),
        "active_headway_missing_indicator_count": int(active["headway_missing"].sum()),
        "feature_quality_inspected_before_fit": True,
    }
    return pl.DataFrame(rows), profile


def _write_charts(
    matrix: np.ndarray,
    route_ids: list[str],
    kmeans_labels: np.ndarray,
    dbscan_labels: np.ndarray,
    output_dir: Path,
    seed: int,
) -> tuple[pl.DataFrame, dict[str, float]]:
    """Fit a two-component PCA for visualization and save coordinates/charts."""
    pca = PCA(n_components=2, svd_solver="full")
    coordinates = pca.fit_transform(matrix)
    coord = pl.DataFrame({
        "route_id": route_ids,
        "kmeans_cluster_id": kmeans_labels.astype(np.int64),
        "dbscan_cluster_id": dbscan_labels.astype(np.int64),
        "pca_component_1": coordinates[:, 0],
        "pca_component_2": coordinates[:, 1],
    })
    coord.write_csv(output_dir / "pca_cluster_coordinates.csv")
    coord.write_parquet(output_dir / "pca_cluster_coordinates.parquet", compression="zstd")
    variance = {"component_1_explained_variance_ratio": float(pca.explained_variance_ratio_[0]), "component_2_explained_variance_ratio": float(pca.explained_variance_ratio_[1])}

    charts = output_dir / "charts"
    charts.mkdir(parents=True, exist_ok=True)
    matplotlib.use("Agg")
    fig, axes = plt.subplots(1, 2, figsize=(15, 6))
    for axis, labels, title, noise in (
        (axes[0], kmeans_labels, "K-Means route clusters", False),
        (axes[1], dbscan_labels, "DBSCAN route clusters (noise shown separately)", True),
    ):
        for cluster_id in sorted(set(map(int, labels))):
            mask = labels == cluster_id
            axis.scatter(
                coordinates[mask, 0], coordinates[mask, 1],
                s=11 if noise and cluster_id == -1 else 14,
                alpha=0.62,
                label="Noise" if noise and cluster_id == -1 else f"Cluster {cluster_id}",
            )
        axis.set_title(title)
        axis.set_xlabel(f"PCA 1 ({variance['component_1_explained_variance_ratio']:.1%} variance)")
        axis.set_ylabel(f"PCA 2 ({variance['component_2_explained_variance_ratio']:.1%} variance)")
        axis.legend(loc="best", fontsize="small", markerscale=1.5)
    fig.suptitle("PCA view of standardized scheduled-service features (visualization only)")
    fig.tight_layout()
    fig.savefig(charts / "route_cluster_pca_comparison.png", dpi=170)
    plt.close(fig)

    # Feature magnitude plot shows the selected standardized inputs, not cluster quality.
    variance_df = pl.DataFrame({"component": ["PCA 1", "PCA 2"], "explained_variance_ratio": [variance["component_1_explained_variance_ratio"], variance["component_2_explained_variance_ratio"]]})
    variance_df.write_csv(output_dir / "pca_explained_variance.csv")
    return coord, variance


def _markdown_report(report: dict[str, Any], output_path: Path) -> None:
    """Create a detailed, non-operational interpretation of model results."""
    quality = report["feature_quality"]
    lines = [
        "# RouteRanker Phase 4: unsupervised route clustering", "",
        "## Scope and interpretation", "",
        "The models group routes by supplied schedule and stop-network features. Cluster descriptions are evidence-based summaries of GTFS timetable patterns; they do not predict passenger demand and do not assess crowding, congestion, efficiency, or actual operational performance.",
        "K-Means labels are arbitrary identifiers. DBSCAN label -1 means the route was not assigned to a dense group at the selected feature-space radius; it is not a GTFS error or a poor-service label.", "",
        "## Feature quality before fitting", "",
        f"- Phase 3 route rows: {quality['total_route_rows']:,}; normalized rows read and ID-aligned: {quality['normalized_input_rows']:,}.",
        f"- Routes with trip records used for fitting: {quality['routes_with_trip_records']:,}.",
        f"- Routes without trip records preserved in predictions but excluded from fitting: {quality['routes_without_trip_records']:,}.",
        f"- Eligible routes missing raw average headway: {quality['active_headway_missing_count']:,}; the corresponding headway_missing indicator is retained.",
        "- Phase 3 normalized features were inspected but not used directly: their scaler was fitted over active and inactive routes together. A fresh imputer and scaler were fitted only on eligible routes to avoid carrying that population mix into model fitting.",
        "- Raw distributions and missingness are in `feature_quality_profile.csv`; selected-feature correlation checks are in `selected_feature_correlations.csv`.", "",
        "## Selected features", "",
        "- Log1p scheduled trip-record count: volume of route trip definitions.",
        "- Log1p unique stop count: stop-network size.",
        "- Log1p average first-stop headway seconds: mean timetable gap; missing values are median-imputed and `headway_missing` is included as a separate feature.",
        "- Peak-departure share: peak-window template-week trips divided by peak plus off-peak template-week trips; peak windows are 07:00-10:00 and 16:00-19:00.",
        "- Log1p scheduled service span: earliest first-stop departure to latest terminal arrival.",
        "- Shared-stop ratio: fraction of a route's stops also used by another route.",
        "- `headway_missing`: explicit missingness signal for routes without enough comparable scheduled starts.",
        "- Log transforms reduce skew in nonnegative volume and time features. The imputer and z-score scaler are fitted on eligible routes only; fitted parameters are saved in `model_parameters.json`.", "",
        "### Excluded fields", "",
    ]
    lines += [f"- {item}" for item in report["feature_selection"]["excluded"]]
    lines += ["", "## Selected model results", ""]
    for result in report["selected_models"]:
        size_summary = ", ".join(
            "{}={:,}".format(item["cluster_id"], item["route_count"])
            for item in result["cluster_sizes"]
        )
        lines += [
            f"### {result['algorithm']}", "",
            f"- Clusters: {result['n_clusters']:,}.",
            f"- Cluster sizes: {size_summary}.",
            f"- Silhouette score: {result['silhouette_score'] if result['silhouette_score'] is not None else 'not mathematically valid'} (sample size {result['silhouette_sample_size']:,}).",
            f"- Davies-Bouldin index: {result['davies_bouldin_index'] if result['davies_bouldin_index'] is not None else 'not mathematically valid'}.",
        ]
        if result["algorithm"] == "DBSCAN":
            lines += [f"- Noise/outlier count: {result['noise_count']:,}.", f"- Selected eps: {result['eps']:.6f}; min_samples: {result['min_samples']}."]
        lines.append("")
    lines += ["## Cluster profiles", "", "Profiles use original, non-normalized GTFS-derived features. Interpretations are comparative schedule summaries, not service-quality judgments.", ""]
    lines += ["| Algorithm | Cluster | Routes | Median trip records | Median stops | Median headway (sec) | Headway missing | Median peak share | Median span (h) | Interpretation |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
    for profile in report["cluster_profiles"]:
        def show(key: str, digits: int = 2) -> str:
            value = profile.get(key)
            return "-" if value is None else f"{value:.{digits}f}"
        interpretation = str(profile["interpretation"]).replace("|", "&#124;")
        lines.append(
            f"| {profile['algorithm']} | {profile['cluster_id']} | {profile['route_count']:,} | {show('median_total_scheduled_trip_records')} | {show('median_unique_stop_count')} | {show('median_average_first_stop_headway_seconds', 1)} | {profile['headway_missing_rate']:.1%} | {show('median_peak_departure_share', 3)} | {show('median_scheduled_service_span_hours', 2)} | {interpretation} |"
        )
    lines += ["", "## Model comparison", ""]
    lines.append("K-Means candidates and DBSCAN radius candidates are listed in the evaluation CSV files. K-Means was selected by highest sampled silhouette among k=2..10. DBSCAN radius candidates were derived from k-nearest-neighbor distance quantiles; selection requires a valid silhouette, at least two non-noise clusters, and at least 10% inliers. Metrics are internal fit diagnostics, not ground-truth validation.")
    lines += ["", "## Limitations", "",
              "- Headways are estimates from scheduled first-stop trip departures, not observed service regularity or passenger waiting times.",
              "- Missing headways were imputed for clustering and marked with a feature indicator. The raw feature data and quality profile retain the original missingness.",
              "- calendar_dates.txt is absent, so date-specific service exceptions are unavailable.",
              "- frequencies.txt is absent, so frequency-based service patterns cannot be represented.",
              "- shapes.txt is absent, so clusters use stop counts and shared-stop ratios rather than route lengths or geographic coverage.",
              "- One feed snapshot, one city/operator, and no ridership or operational observations limit cluster interpretation and generalization.",
              "- No labels exist for external validation; silhouette and Davies-Bouldin scores are descriptive internal metrics.", "",
              "## Outputs", ""]
    lines += [f"- `{path}`" for path in report["output_files"]]
    lines.append("")
    output_path.write_text("\n".join(lines), encoding="utf-8")


def run_route_clustering(
    features_dir: str | Path,
    output_dir: str | Path,
    random_seed: int = RANDOM_SEED,
) -> dict[str, Any]:
    """Fit K-Means and DBSCAN from validated Phase 3 route feature datasets."""
    features_dir, output_dir = Path(features_dir).resolve(), Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    required = (
        "route_features.parquet", "route_features_normalized.parquet",
        "feature_engineering_report.json", "feature_validation_report.json", "normalization_parameters.json",
    )
    missing = [name for name in required if not (features_dir / name).is_file()]
    if missing:
        raise FileNotFoundError(f"Missing verified Phase 3 feature inputs: {missing}")
    phase3_report = json.loads((features_dir / "feature_engineering_report.json").read_text(encoding="utf-8"))
    phase3_validation = json.loads((features_dir / "feature_validation_report.json").read_text(encoding="utf-8"))
    if phase3_report.get("status") != "passed" or phase3_validation.get("status") != "passed":
        raise ValueError("Phase 3 feature engineering and validation reports must both have passed status")

    raw = pl.read_parquet(features_dir / "route_features.parquet")
    normalized = pl.read_parquet(features_dir / "route_features_normalized.parquet")
    if raw.height != normalized.height or set(raw["route_id"].to_list()) != set(normalized["route_id"].to_list()):
        raise ValueError("Raw and normalized Phase 3 route rows/IDs do not align")
    required_columns = {
        "route_id", "total_scheduled_trip_records", "unique_stop_count", "average_first_stop_headway_seconds",
        "peak_scheduled_departures_per_template_week", "off_peak_scheduled_departures_per_template_week",
        "scheduled_service_span_seconds", "shared_stop_ratio", "headway_missing", "service_span_missing",
        "shared_stop_ratio_missing",
    }
    missing_columns = sorted(required_columns - set(raw.columns))
    if missing_columns:
        raise ValueError(f"Phase 3 raw route features are missing columns: {missing_columns}")
    if normalized.null_count().select(pl.sum_horizontal(pl.all())).item() != 0:
        raise ValueError("Phase 3 normalized route feature dataset unexpectedly contains nulls")

    active_mask = (raw["total_scheduled_trip_records"] > 0).to_numpy()
    quality_table, quality = _distribution_profile(raw, normalized, active_mask)
    quality_table.write_csv(output_dir / "feature_quality_profile.csv")
    quality["phase3_validation_checks"] = phase3_validation.get("check_count")
    quality["phase3_validation_status"] = phase3_validation.get("status")
    quality["phase3_normalized_rows_used_for_fit"] = False
    quality["headway_indicator_matches_headway_nulls"] = int(
        (raw.filter(pl.Series("active", active_mask))["average_first_stop_headway_seconds"].is_null().cast(pl.Int8)
         != raw.filter(pl.Series("active", active_mask))["headway_missing"].cast(pl.Int8)).sum()
    ) == 0

    active = raw.filter(pl.Series("active", active_mask)).with_columns(
        (
            pl.col("peak_scheduled_departures_per_template_week")
            / (pl.col("peak_scheduled_departures_per_template_week") + pl.col("off_peak_scheduled_departures_per_template_week"))
        ).alias("peak_departure_share")
    ).with_columns(pl.col("peak_departure_share").is_null().cast(pl.Int8).alias("peak_departure_share_missing"))
    active_ids = active["route_id"].to_list()
    if not quality["headway_indicator_matches_headway_nulls"]:
        raise ValueError("headway_missing indicators do not match raw headway missingness")
    indicator_columns = ["headway_missing", "service_span_missing", "shared_stop_ratio_missing", "peak_departure_share_missing"]
    included_indicators: list[str] = []
    excluded_constant_indicators: list[str] = []
    for column in indicator_columns:
        if active[column].n_unique() > 1:
            included_indicators.append(column)
        else:
            excluded_constant_indicators.append(column)
    feature_columns = tuple(BASE_CONTINUOUS_FEATURES + tuple(included_indicators))
    candidate_input = active.select(list(feature_columns))
    x_raw = candidate_input.to_numpy().astype(np.float64, copy=False)
    if np.isinf(x_raw).any():
        raise ValueError("Selected route feature inputs contain infinite values")
    if x_raw.shape[0] < max(KMEANS_CANDIDATES) + 1:
        raise ValueError("Too few active routes to evaluate the configured K-Means candidates")

    # Fit quality summaries and correlations before any model is trained.
    selected_pre_log = _log_selected_features(x_raw, tuple(index for index, name in enumerate(feature_columns) if name in LOG_FEATURE_NAMES))
    imputer_for_inspection = SimpleImputer(strategy="median", keep_empty_features=True)
    inspection_values = imputer_for_inspection.fit_transform(selected_pre_log)
    correlation_rows: list[dict[str, Any]] = []
    correlation_matrix = np.corrcoef(inspection_values, rowvar=False)
    for left, left_name in enumerate(feature_columns):
        for right in range(left, len(feature_columns)):
            right_name = feature_columns[right]
            value = float(correlation_matrix[left, right])
            correlation_rows.append({"feature_a": left_name, "feature_b": right_name, "pearson_correlation_after_log_and_median_imputation": value})
    pl.DataFrame(correlation_rows).write_csv(output_dir / "selected_feature_correlations.csv")

    selection = {
        "included": [
            {"feature": name, "reason": reason}
            for name, reason in (
                ("total_scheduled_trip_records", "Log-scaled schedule volume dimension."),
                ("unique_stop_count", "Log-scaled stop-network size."),
                ("average_first_stop_headway_seconds", "Log-scaled scheduled departure spacing; missing raw values are imputed."),
                ("peak_departure_share", "Peak/off-peak balance without duplicating the two highly correlated raw counts."),
                ("scheduled_service_span_seconds", "Log-scaled timetable envelope from first departure to final arrival."),
                ("shared_stop_ratio", "Bounded network overlap proportion."),
                ("headway_missing", "Retains the fact that a headway was not estimable after imputation."),
                ("service_span_missing", "Retains missing scheduled service-span information where it varies."),
                ("shared_stop_ratio_missing", "Retains missing route overlap information where it varies."),
                ("peak_departure_share_missing", "Retains missing peak/off-peak calendar departure information where it varies."),
            ) if name in feature_columns
        ],
        "excluded": [
            "route_id and route names: identifiers/labels, not route schedule characteristics.",
            "route_type: constant value in this supplied feed, so it cannot separate routes.",
            "first/last departure clock times: cyclical/time-of-day values and partly redundant with the selected departure-share and service-span features.",
            "peak_scheduled_departures_per_template_week and off_peak_scheduled_departures_per_template_week as separate dimensions: their raw counts are highly correlated with total trip records (active-feed Pearson correlations about 0.984 and 0.994); use their peak share instead.",
            "headway_interval_count: closely reflects the number of schedule trip records and the reliability/sample size of the headway estimate, rather than an independent service characteristic.",
            "shared_stop_count: duplicates route size; use shared_stop_ratio instead.",
            *[f"{column}: constant among routes eligible for fitting in this feed, so it carries no clustering information; retained in raw Phase 3 features and quality report." for column in excluded_constant_indicators],
            "routes with zero scheduled trip records: excluded from model fitting as they have no schedule characteristics to compare; retained in prediction output with an explicit exclusion status.",
        ],
        "input_feature_columns": list(feature_columns),
        "log1p_columns": [name for name in feature_columns if name in LOG_FEATURE_NAMES],
        "phase3_normalized_features_used_for_fit": False,
        "phase3_normalized_features_note": "Read and checked for row/ID alignment and missingness, but not used for fitting because Phase 3 scaling included no-service route rows. This phase refits imputation and scaling on active routes only.",
        "headway_missing_count_in_training": int(active["headway_missing"].sum()),
        "headway_missing_values_median_imputed": True,
        "headway_missing_indicator_included": "headway_missing" in feature_columns,
    }
    (output_dir / "feature_selection.json").write_text(json.dumps(selection, indent=2, ensure_ascii=False), encoding="utf-8")
    (output_dir / "feature_quality_report.json").write_text(json.dumps(quality, indent=2, ensure_ascii=False), encoding="utf-8")

    kmeans_candidates: list[dict[str, Any]] = []
    kmeans_models: dict[int, Pipeline] = {}
    for k in KMEANS_CANDIDATES:
        pipeline = Pipeline(_make_preprocessor(feature_columns) + [
            ("clusterer", KMeans(n_clusters=k, random_state=random_seed, n_init=20, algorithm="lloyd")),
        ])
        labels = pipeline.fit_predict(x_raw)
        scaled = pipeline[:-1].transform(x_raw)
        metrics = _evaluate_kmeans_candidate(scaled, labels, pipeline.named_steps["clusterer"], random_seed)
        metrics["k"] = k
        kmeans_candidates.append(metrics)
        kmeans_models[k] = pipeline
    valid_kmeans = [item for item in kmeans_candidates if item["silhouette_score"] is not None]
    selected_kmeans_metrics = max(valid_kmeans, key=lambda item: (item["silhouette_score"], -item["k"]))
    selected_k = int(selected_kmeans_metrics["k"])
    kmeans_pipeline = kmeans_models[selected_k]
    kmeans_labels = kmeans_pipeline.named_steps["clusterer"].labels_.astype(np.int64)
    kmeans_scaled = kmeans_pipeline[:-1].transform(x_raw)

    min_samples = len(feature_columns) + 1
    min_samples = max(5, min_samples)
    neighbors = NearestNeighbors(n_neighbors=min_samples, metric="euclidean", n_jobs=1).fit(kmeans_scaled)
    kth_distances = neighbors.kneighbors(kmeans_scaled, return_distance=True)[0][:, -1]
    eps_values = sorted({float(np.quantile(kth_distances, q)) for q in DBSCAN_EPS_QUANTILES if float(np.quantile(kth_distances, q)) > 0})
    if not eps_values:
        eps_values = [float(np.max(kth_distances)) if np.max(kth_distances) > 0 else 0.5]
    dbscan_candidates: list[dict[str, Any]] = []
    for eps in eps_values:
        clusterer = DBSCAN(eps=eps, min_samples=min_samples, metric="euclidean", algorithm="auto")
        labels = clusterer.fit_predict(kmeans_scaled)
        metrics = _evaluate_dbscan_candidate(kmeans_scaled, labels, eps, min_samples, random_seed)
        dbscan_candidates.append(metrics)
    eligible_dbscan = [item for item in dbscan_candidates if item["selection_eligible"]]
    if eligible_dbscan:
        selected_dbscan_metrics = max(eligible_dbscan, key=lambda item: (item["silhouette_score"], -item["noise_fraction"], item["eps"]))
        dbscan_selection_note = "Highest sampled silhouette among candidates passing the documented inlier/cluster guardrail."
    else:
        selected_dbscan_metrics = max(dbscan_candidates, key=lambda item: (item["inlier_count"], item["n_clusters"], -item["eps"]))
        dbscan_selection_note = "No radius passed the silhouette/inlier guardrail; selected the candidate retaining the most inliers, then clusters. Interpret metrics cautiously."
    selected_eps = float(selected_dbscan_metrics["eps"])
    dbscan_pipeline = _new_dbscan_pipeline(feature_columns, selected_eps, min_samples)
    dbscan_labels = dbscan_pipeline.fit_predict(x_raw).astype(np.int64)
    dbscan_scaled = dbscan_pipeline[:-1].transform(x_raw)

    # Persist exact fitted preprocessing alongside each final estimator.
    joblib.dump({
        "pipeline": kmeans_pipeline,
        "feature_columns": list(feature_columns),
        "log1p_columns": selection["log1p_columns"],
        "training_route_count": len(active_ids),
        "random_seed": random_seed,
        "selected_k": selected_k,
    }, output_dir / "kmeans_model.joblib")
    joblib.dump({
        "pipeline": dbscan_pipeline,
        "feature_columns": list(feature_columns),
        "log1p_columns": selection["log1p_columns"],
        "training_route_count": len(active_ids),
        "min_samples": min_samples,
        "eps": selected_eps,
        "note": "DBSCAN does not expose predict for new points; refit to recluster a changed route population.",
    }, output_dir / "dbscan_model.joblib")

    # Profiles are computed from raw, unscaled Phase 3 features.
    profile_frame = _profile_clusters(raw, active_ids, {"KMeans": kmeans_labels, "DBSCAN": dbscan_labels})
    profile_frame.write_csv(output_dir / "cluster_profiles.csv")
    profile_frame.write_parquet(output_dir / "cluster_profiles.parquet", compression="zstd")

    predictions_map = pl.DataFrame({
        "route_id": active_ids,
        "kmeans_cluster_id": kmeans_labels,
        "dbscan_cluster_id": dbscan_labels,
        "fit_status": ["clustered" if label != -1 else "dbscan_noise" for label in dbscan_labels],
    })
    all_predictions = raw.select("route_id", "total_scheduled_trip_records").join(predictions_map, on="route_id", how="left").with_columns(
        pl.when(pl.col("total_scheduled_trip_records") == 0)
        .then(pl.lit("excluded_no_scheduled_trip_records"))
        .otherwise(pl.col("fit_status"))
        .alias("fit_status")
    )
    all_predictions.write_csv(output_dir / "cluster_predictions.csv")
    all_predictions.write_parquet(output_dir / "cluster_predictions.parquet", compression="zstd")

    model_matrix = pl.DataFrame({"route_id": active_ids})
    model_matrix = model_matrix.with_columns([
        pl.Series(f"{name}_standardized", kmeans_scaled[:, index])
        for index, name in enumerate(feature_columns)
    ])
    model_matrix.write_csv(output_dir / "standardized_model_matrix.csv")
    model_matrix.write_parquet(output_dir / "standardized_model_matrix.parquet", compression="zstd")

    _, pca_variance = _write_charts(kmeans_scaled, active_ids, kmeans_labels, dbscan_labels, output_dir, random_seed)
    kmeans_sizes = selected_kmeans_metrics["cluster_sizes"]
    dbscan_sizes = _cluster_sizes(dbscan_labels, noise_label=-1)
    dbscan_size_records = dbscan_sizes + (
        [{"cluster_id": -1, "route_count": int(np.sum(dbscan_labels == -1))}]
        if np.any(dbscan_labels == -1) else []
    )
    cluster_size_rows = [
        {"algorithm": "KMeans", **row, "is_noise": False} for row in kmeans_sizes
    ] + [
        {"algorithm": "DBSCAN", **row, "is_noise": row["cluster_id"] == -1} for row in dbscan_size_records
    ]
    pl.DataFrame(cluster_size_rows).write_csv(output_dir / "cluster_sizes.csv")
    dbscan_evaluation = dict(selected_dbscan_metrics)
    dbscan_evaluation["cluster_sizes"] = dbscan_size_records
    dbscan_evaluation["selection_note"] = dbscan_selection_note
    selected_models = [selected_kmeans_metrics, dbscan_evaluation]
    pl.DataFrame([
        {
            "algorithm": result["algorithm"],
            "n_clusters": result["n_clusters"],
            "silhouette_score": result["silhouette_score"],
            "silhouette_sample_size": result["silhouette_sample_size"],
            "davies_bouldin_index": result["davies_bouldin_index"],
            "noise_count": result["noise_count"],
            "inlier_count": result["inlier_count"],
            "k": result.get("k"),
            "eps": result.get("eps"),
            "min_samples": result.get("min_samples"),
        }
        for result in selected_models
    ]).write_csv(output_dir / "model_comparison.csv")
    pl.DataFrame(kmeans_candidates).drop("cluster_sizes", "silhouette_note").write_csv(output_dir / "kmeans_candidate_metrics.csv")
    pl.DataFrame(dbscan_candidates).drop("cluster_sizes", "silhouette_note", "selection_rule").write_csv(output_dir / "dbscan_candidate_metrics.csv")

    parameters = {
        "random_seed": random_seed,
        "eligible_route_count": len(active_ids),
        "excluded_no_trip_route_count": raw.height - len(active_ids),
        "feature_columns": list(feature_columns),
        "log1p_features": selection["log1p_columns"],
        "imputation": "median, fit only on routes with at least one scheduled trip record",
        "scaling": "StandardScaler z-score, fit only on routes with at least one scheduled trip record after log1p and imputation",
        "silhouette_sample_size": SILHOUETTE_SAMPLE_SIZE,
        "kmeans": {"candidate_k": list(KMEANS_CANDIDATES), "selected_k": selected_k, "n_init": 20, "random_state": random_seed},
        "dbscan": {"eps_candidates": eps_values, "eps_quantiles": list(DBSCAN_EPS_QUANTILES), "selected_eps": selected_eps, "min_samples": min_samples, "metric": "euclidean", "selection_note": dbscan_selection_note},
        "dbscan_inlier_guardrail": f"At least {MIN_DBSCAN_INLIER_FRACTION:.0%} of active routes, at least 2 clusters, and a valid silhouette for candidate selection.",
        "pca_explained_variance": pca_variance,
        "phase3_normalized_dataset_used_for_inspection_only": True,
    }
    (output_dir / "model_parameters.json").write_text(json.dumps(parameters, indent=2), encoding="utf-8")
    quality["selected_feature_columns"] = list(feature_columns)
    quality["excluded_constant_indicators"] = excluded_constant_indicators
    (output_dir / "feature_quality_report.json").write_text(json.dumps(quality, indent=2), encoding="utf-8")

    report = {
        "status": "completed",
        "feature_quality": quality,
        "feature_selection": selection,
        "selected_models": selected_models,
        "cluster_profiles": profile_frame.to_dicts(),
        "pca_explained_variance": pca_variance,
        "output_files": [
            "kmeans_model.joblib", "dbscan_model.joblib", "cluster_predictions.csv", "cluster_predictions.parquet",
            "cluster_sizes.csv", "cluster_profiles.csv", "cluster_profiles.parquet", "model_comparison.csv",
            "kmeans_candidate_metrics.csv", "dbscan_candidate_metrics.csv", "feature_quality_profile.csv",
            "feature_quality_report.json", "selected_feature_correlations.csv", "feature_selection.json",
            "standardized_model_matrix.csv", "standardized_model_matrix.parquet", "model_parameters.json",
            "pca_cluster_coordinates.csv", "pca_cluster_coordinates.parquet", "pca_explained_variance.csv",
            "charts/route_cluster_pca_comparison.png", "machine_learning_report.json", "machine_learning_report.md",
        ],
    }
    (output_dir / "machine_learning_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    _markdown_report(report, output_dir / "machine_learning_report.md")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Cluster scheduled route feature profiles with K-Means and DBSCAN.")
    parser.add_argument("--features", type=Path, default=Path("data/processed/features"), help="Phase 3 route feature outputs")
    parser.add_argument("--output", type=Path, default=Path("data/processed/clustering"), help="Phase 4 model outputs")
    parser.add_argument("--seed", type=int, default=RANDOM_SEED, help="Reproducible random seed")
    args = parser.parse_args()
    result = run_route_clustering(args.features, args.output, args.seed)
    print(json.dumps({"status": result["status"], "active_routes": result["feature_quality"]["routes_with_trip_records"], "selected_models": result["selected_models"], "output_directory": str(args.output)}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

