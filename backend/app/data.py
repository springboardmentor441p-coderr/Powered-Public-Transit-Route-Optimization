"""Startup data loader for the FastAPI backend.

Reads ONLY from app_data/ so the running app never touches raw data/,
reports/, or test_features.parquet.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
APP_DATA_DIR = ROOT / "app_data"


def clean_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Convert DataFrame to list of dicts with NaN/inf replaced by None (never 0)."""
    records = df.to_dict(orient="records")
    cleaned: list[dict[str, Any]] = []
    for row in records:
        out: dict[str, Any] = {}
        for k, v in row.items():
            if v is None:
                out[k] = None
            elif isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                out[k] = None
            elif pd.isna(v):
                out[k] = None
            elif hasattr(v, "item"):
                val = v.item()
                if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
                    out[k] = None
                else:
                    out[k] = val
            else:
                out[k] = v
        cleaned.append(out)
    return cleaned


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


@dataclass
class AppDataStore:
    app_data_dir: Path
    version: dict[str, Any]
    overview: dict[str, Any]
    optimization_thresholds: dict[str, Any]
    route_groups_meta: dict[str, Any]
    route_geometries: dict[str, Any]
    network_daily: pd.DataFrame
    network_hourly: pd.DataFrame
    routes_summary: pd.DataFrame
    route_hourly_pattern: pd.DataFrame
    route_time_band_performance: pd.DataFrame
    route_overlap_pairs: pd.DataFrame
    route_thresholds: pd.DataFrame
    route_coverage: pd.DataFrame
    review_list: pd.DataFrame
    step8_candidate_scenarios: pd.DataFrame
    step8_merge_checks: pd.DataFrame
    step9_reallocation: pd.DataFrame
    obs_review_hourly: pd.DataFrame
    # Evaluation tables
    val_forecast_comparison: pd.DataFrame
    val_forecast_weekly: pd.DataFrame
    val_forecast_by_route_hgb: pd.DataFrame
    val_forecast_by_route_4wk: pd.DataFrame
    val_classification_comparison: pd.DataFrame
    test_forecast_overall: pd.DataFrame
    test_forecast_by_week: pd.DataFrame
    test_forecast_by_route: pd.DataFrame
    test_forecast_by_day_type: pd.DataFrame
    test_forecast_by_time_band: pd.DataFrame
    test_classification_overall: pd.DataFrame
    test_classification_by_route_official: pd.DataFrame
    test_classification_by_route_rule_b: pd.DataFrame
    october_forecast_summary: pd.DataFrame
    october_forecast_by_day: pd.DataFrame
    october_forecast_by_route: pd.DataFrame
    october_classification_summary: pd.DataFrame
    october_diagnostic_checks: pd.DataFrame
    october_hourly_forecast_vs_actual: pd.DataFrame
    # Clustering CSVs
    route_groups_assigned: pd.DataFrame
    route_groups_profiles: pd.DataFrame
    route_groups_k_selection: pd.DataFrame
    route_groups_k2_vs_k3: pd.DataFrame
    route_groups_dbscan: pd.DataFrame

    @property
    def valid_routes(self) -> set[str]:
        return set(self.routes_summary["route"].astype(str).tolist())


def load_app_data(data_dir: Path | None = None) -> AppDataStore:
    """Load all exported app_data/ files into memory once at startup."""
    d = data_dir or APP_DATA_DIR
    if not d.exists():
        raise FileNotFoundError(
            f"Missing app_data directory at {d}. Run `python -m src.export_app_data` first."
        )

    return AppDataStore(
        app_data_dir=d,
        version=_read_json(d / "version.json"),
        overview=_read_json(d / "overview.json"),
        optimization_thresholds=_read_json(d / "optimization_thresholds.json"),
        route_groups_meta=_read_json(d / "route_groups.json"),
        route_geometries=_read_json(d / "route_geometries.json"),
        network_daily=pd.read_csv(d / "network_daily.csv"),
        network_hourly=pd.read_csv(d / "network_hourly.csv"),
        routes_summary=pd.read_csv(d / "routes_summary.csv"),
        route_hourly_pattern=pd.read_csv(d / "route_hourly_pattern.csv"),
        route_time_band_performance=pd.read_csv(d / "route_time_band_performance.csv"),
        route_overlap_pairs=pd.read_csv(d / "route_overlap_pairs.csv"),
        route_thresholds=pd.read_csv(d / "route_thresholds.csv"),
        route_coverage=pd.read_csv(d / "route_coverage.csv"),
        review_list=pd.read_csv(d / "review_list.csv"),
        step8_candidate_scenarios=pd.read_csv(d / "step8_candidate_scenarios.csv"),
        step8_merge_checks=pd.read_csv(d / "step8_shared_corridor_merge_checks.csv"),
        step9_reallocation=pd.read_csv(d / "step9_budget_neutral_reallocation.csv"),
        obs_review_hourly=pd.read_parquet(d / "obs_review_hourly_distribution.parquet"),
        val_forecast_comparison=pd.read_csv(d / "validation_forecast_comparison.csv"),
        val_forecast_weekly=pd.read_csv(d / "validation_forecast_weekly.csv"),
        val_forecast_by_route_hgb=pd.read_csv(d / "validation_forecast_by_route_hgb.csv"),
        val_forecast_by_route_4wk=pd.read_csv(d / "validation_forecast_by_route_4wk.csv"),
        val_classification_comparison=pd.read_csv(d / "validation_classification_comparison.csv"),
        test_forecast_overall=pd.read_csv(d / "test_forecast_overall.csv"),
        test_forecast_by_week=pd.read_csv(d / "test_forecast_by_week.csv"),
        test_forecast_by_route=pd.read_csv(d / "test_forecast_by_route.csv"),
        test_forecast_by_day_type=pd.read_csv(d / "test_forecast_by_day_type.csv"),
        test_forecast_by_time_band=pd.read_csv(d / "test_forecast_by_time_band.csv"),
        test_classification_overall=pd.read_csv(d / "test_classification_overall.csv"),
        test_classification_by_route_official=pd.read_csv(
            d / "test_classification_by_route_official.csv"
        ),
        test_classification_by_route_rule_b=pd.read_csv(
            d / "test_classification_by_route_rule_b.csv"
        ),
        october_forecast_summary=pd.read_csv(d / "october_forecast_summary.csv"),
        october_forecast_by_day=pd.read_csv(d / "october_forecast_by_day.csv"),
        october_forecast_by_route=pd.read_csv(d / "october_forecast_by_route.csv"),
        october_classification_summary=pd.read_csv(d / "october_classification_summary.csv"),
        october_diagnostic_checks=pd.read_csv(d / "october_diagnostic_checks.csv"),
        october_hourly_forecast_vs_actual=pd.read_parquet(
            d / "october_hourly_forecast_vs_actual.parquet"
        ),
        route_groups_assigned=pd.read_csv(d / "route_groups_assigned.csv"),
        route_groups_profiles=pd.read_csv(d / "route_groups_profiles.csv"),
        route_groups_k_selection=pd.read_csv(d / "route_groups_k_selection.csv"),
        route_groups_k2_vs_k3=pd.read_csv(d / "route_groups_k2_vs_k3.csv"),
        route_groups_dbscan=pd.read_csv(d / "route_groups_dbscan.csv"),
    )

