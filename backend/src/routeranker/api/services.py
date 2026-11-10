"""Read-only domain services joining verified Phase 1-4 outputs."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib
import polars as pl

from .data_access import DataRepository, DatasetUnavailable


class RecordNotFound(LookupError):
    """Requested route or stop ID is not in the processed feed."""


class InvalidFilter(ValueError):
    """A validly encoded filter has incompatible values."""


class RouteRankerService:
    """Application services over cached processed GTFS and analysis tables."""

    def __init__(self, repository: DataRepository):
        self.repo = repository

    def routes(self) -> pl.DataFrame:
        routes = self.repo.frame("gtfs", "routes.parquet")
        summary = self.repo.frame("eda", "route_summary.csv").select(
            "route_id", "trip_count", "stop_count", "template_week_trip_count",
            "first_service_time", "last_service_time",
        )
        predictions = self.repo.frame("clustering", "cluster_predictions.parquet").select(
            "route_id", "kmeans_cluster_id", "dbscan_cluster_id", "fit_status",
        )
        features = self.repo.frame("features", "route_features.parquet").select(
            "route_id", "average_first_stop_headway_seconds",
        )
        return routes.join(summary, on="route_id", how="left").join(features, on="route_id", how="left").join(predictions, on="route_id", how="left")

    def route(self, route_id: str) -> dict[str, Any]:
        row = self.routes().filter(pl.col("route_id") == route_id)
        if row.is_empty():
            raise RecordNotFound(f"Route '{route_id}' was not found")
        return row.row(0, named=True)

    def route_features(self, route_id: str) -> dict[str, Any]:
        self.route(route_id)
        raw = self.repo.frame("features", "route_features.parquet")
        row = raw.filter(pl.col("route_id") == route_id)
        if row.is_empty():
            raise DatasetUnavailable("Route feature dataset has no matching route record")
        return row.row(0, named=True)

    def route_cluster(self, route_id: str) -> dict[str, Any]:
        self.route(route_id)
        prediction = self.repo.frame("clustering", "cluster_predictions.parquet").filter(pl.col("route_id") == route_id)
        if prediction.is_empty():
            raise DatasetUnavailable("Cluster assignment dataset has no matching route record")
        return prediction.select("route_id", "kmeans_cluster_id", "dbscan_cluster_id", "fit_status").row(0, named=True)

    def list_routes(
        self, limit: int, offset: int, query: str | None = None,
        min_trips: int | None = None, max_trips: int | None = None,
        min_stops: int | None = None, max_headway_seconds: float | None = None,
        min_headway_seconds: float | None = None, algorithm: str | None = None,
        cluster_id: int | None = None,
    ) -> dict[str, Any]:
        if min_trips is not None and max_trips is not None and min_trips > max_trips:
            raise InvalidFilter("min_trips must be less than or equal to max_trips")
        frame = self.routes()
        if query:
            term = query.casefold()
            frame = frame.filter(
                pl.col("route_id").str.to_lowercase().str.contains(term, literal=True)
                | pl.col("route_short_name").fill_null("").str.to_lowercase().str.contains(term, literal=True)
                | pl.col("route_long_name").fill_null("").str.to_lowercase().str.contains(term, literal=True)
            )
        for column, value, op in (
            ("trip_count", min_trips, "ge"), ("trip_count", max_trips, "le"),
            ("stop_count", min_stops, "ge"),
        ):
            if value is not None:
                frame = frame.filter(pl.col(column) >= value if op == "ge" else pl.col(column) <= value)
        if max_headway_seconds is not None:
            frame = frame.filter(pl.col("average_first_stop_headway_seconds").is_not_null()
                                 & (pl.col("average_first_stop_headway_seconds") <= max_headway_seconds))
        if min_headway_seconds is not None:
            frame = frame.filter(pl.col("average_first_stop_headway_seconds").is_not_null()
                                 & (pl.col("average_first_stop_headway_seconds") >= min_headway_seconds))
        if cluster_id is not None:
            algorithm = algorithm or "kmeans"
            column = "kmeans_cluster_id" if algorithm == "kmeans" else "dbscan_cluster_id"
            frame = frame.filter(pl.col(column) == cluster_id)
        elif algorithm:
            raise InvalidFilter("algorithm requires cluster_id")
        total = frame.height
        return {"items": frame.slice(offset, limit).to_dicts(), "total": total, "limit": limit, "offset": offset}

    def compare_routes(self, route_ids: list[str]) -> list[dict[str, Any]]:
        if len(set(route_ids)) != len(route_ids):
            raise InvalidFilter("route_ids must not contain duplicates")
        frame = self.routes().filter(pl.col("route_id").is_in(route_ids))
        found = set(frame["route_id"].to_list())
        absent = [route_id for route_id in route_ids if route_id not in found]
        if absent:
            raise RecordNotFound(f"Unknown route ID(s): {', '.join(absent)}")
        return frame.to_dicts()

    def stops(self) -> pl.DataFrame:
        return self.repo.frame("eda", "stop_summary.csv")

    def list_stops(self, limit: int, offset: int, query: str | None = None, min_routes: int | None = None) -> dict[str, Any]:
        frame = self.stops()
        if query:
            term = query.casefold()
            frame = frame.filter(
                pl.col("stop_id").str.to_lowercase().str.contains(term, literal=True)
                | pl.col("stop_name").fill_null("").str.to_lowercase().str.contains(term, literal=True)
            )
        if min_routes is not None:
            frame = frame.filter(pl.col("route_count") >= min_routes)
        total = frame.height
        return {"items": frame.slice(offset, limit).to_dicts(), "total": total, "limit": limit, "offset": offset}

    def stop(self, stop_id: str) -> dict[str, Any]:
        frame = self.stops().filter(pl.col("stop_id") == stop_id)
        if frame.is_empty():
            raise RecordNotFound(f"Stop '{stop_id}' was not found")
        return frame.row(0, named=True)

    def routes_at_stop(self, stop_id: str) -> list[dict[str, Any]]:
        self.stop(stop_id)
        links = self.repo.frame("eda", "route_stop_coverage.parquet").filter(pl.col("stop_id") == stop_id)
        routes = self.repo.frame("gtfs", "routes.parquet").select("route_id", "route_short_name", "route_long_name")
        return links.join(routes, on="route_id", how="left").sort("route_id").to_dicts()

    def stop_route_counts(self, limit: int, offset: int) -> dict[str, Any]:
        frame = self.stops().select("stop_id", "stop_name", "route_count").sort("stop_id")
        return {"items": frame.slice(offset, limit).to_dicts(), "total": frame.height, "limit": limit, "offset": offset}

    def dataset_statistics(self) -> dict[str, Any]:
        gtfs = self.repo.document("gtfs", "data_quality_report.json")
        eda = self.repo.document("eda", "eda_report.json")
        return {
            "gtfs_quality_status": gtfs.get("status"),
            "dataset_totals": eda.get("totals", {}),
            "scheduled_service_level": eda.get("service_level", {}),
            "headway_diagnostics": eda.get("headways", {}),
            "time_of_day": eda.get("time_of_day", {}),
            "data_quality": eda.get("data_quality", {}),
            "limitations": eda.get("limitations", {}),
            "interpretation": "Counts and headways describe supplied scheduled GTFS service, not passenger demand or actual operations.",
        }

    def route_statistics(self) -> dict[str, Any]:
        routes = self.repo.frame("eda", "route_summary.csv")
        return {"route_count": routes.height, "routes_with_trips": routes.filter(pl.col("trip_count") > 0).height,
                "scheduled_trip_records": int(routes["trip_count"].sum()), "median_stops_per_route": routes["stop_count"].median()}

    def stop_statistics(self) -> dict[str, Any]:
        stops = self.stops()
        return {"stop_count": stops.height, "stops_with_scheduled_trips": stops.filter(pl.col("trip_count") > 0).height,
                "stops_served_by_routes": stops.filter(pl.col("route_count") > 0).height,
                "median_routes_per_stop": stops["route_count"].median()}

    def scheduled_by_hour(self) -> list[dict[str, Any]]:
        return self.repo.frame("eda", "scheduled_trips_by_service_hour.csv").sort("service_hour").to_dicts()

    def headway_summary(self, route_id: str | None = None) -> dict[str, Any]:
        frame = self.repo.frame("eda", "route_service_headways.csv")
        if route_id is not None:
            self.route(route_id)
            frame = frame.filter(pl.col("route_id") == route_id)
        valid = frame.filter(pl.col("mean_headway_seconds").is_not_null())
        return {"route_id": route_id, "groups_with_estimates": valid.height,
                "groups_without_estimates": frame.height - valid.height,
                "median_of_group_medians_seconds": valid["median_headway_seconds"].median() if valid.height else None,
                "mean_of_group_means_seconds": valid["mean_headway_seconds"].mean() if valid.height else None,
                "note": "Estimated from scheduled first-stop departures; not observed regularity or passenger waiting time."}

    def similarities(self, route_id: str | None, limit: int) -> list[dict[str, Any]]:
        path = self.repo.path("eda", "route_pair_overlap.parquet")
        if not path.is_file():
            raise DatasetUnavailable(f"Required dataset is unavailable: {path}")
        lazy = pl.scan_parquet(path)
        if route_id is not None:
            self.route(route_id)
            lazy = lazy.filter((pl.col("route_id_a") == route_id) | (pl.col("route_id_b") == route_id))
        return lazy.sort("jaccard_similarity", descending=True).head(limit).collect().to_dicts()

    def cluster_summaries(self) -> list[dict[str, Any]]:
        sizes = self.repo.frame("clustering", "cluster_sizes.csv")
        profiles = self.repo.frame("clustering", "cluster_profiles.parquet")
        profile_map = {(r["algorithm"], int(r["cluster_id"])): r for r in profiles.to_dicts()}
        return [{**row, "cluster_id": int(row["cluster_id"]), "route_count": int(row["route_count"]),
                 "is_noise": bool(row["is_noise"]), "profile": profile_map.get((row["algorithm"], int(row["cluster_id"]))) }
                for row in sizes.to_dicts()]

    def model_metrics(self) -> list[dict[str, Any]]:
        frame = self.repo.frame("clustering", "model_comparison.csv")
        return frame.to_dicts()

    def model_metadata(self) -> list[dict[str, Any]]:
        result = []
        for name in ("kmeans_model.joblib", "dbscan_model.joblib"):
            path = self.repo.path("clustering", name)
            if not path.is_file():
                raise DatasetUnavailable(f"Saved model is unavailable: {path}")
            fitted = _load_saved_model(str(path))
            result.append({"model": name.removesuffix("_model.joblib"), "feature_columns": fitted.get("feature_columns", []),
                           "training_route_count": fitted.get("training_route_count"), "selected_k": fitted.get("selected_k"),
                           "eps": fitted.get("eps"), "min_samples": fitted.get("min_samples"),
                           "new_route_behavior": "The saved K-Means pipeline supports prediction with the trained feature schema; its fitted median imputer handles missing numeric inputs." if name.startswith("kmeans") else "DBSCAN does not predict assignments for unseen routes; refit the clustering population."})
        return result


@lru_cache(maxsize=4)
def _load_saved_model(path: str) -> dict[str, Any]:
    """Load a trusted, locally generated joblib artifact only once per process."""
    try:
        model = joblib.load(Path(path))
    except Exception as exc:
        raise DatasetUnavailable(f"Could not load saved model artifact: {path}") from exc
    if not isinstance(model, dict):
        raise DatasetUnavailable("Saved model artifact has an unexpected structure")
    return model
