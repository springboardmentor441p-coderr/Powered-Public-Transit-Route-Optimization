"""Pin dashboard inputs only after checking their upstream analytical fingerprints."""
import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data/processed/new_york"

TABLES = {
    "daily": "matched_daily_features.csv", "hourly": "matched_hourly_features.csv",
    "map_routes": "map_route_shapes.csv", "map_shapes": "map_shapes.csv",
    "overlap": "route_overlap.csv", "crosswalk": "route_crosswalk.csv",
    "members": "route_clustering/profile_members.csv", "date_coverage": "route_clustering/date_coverage.csv",
    "groups": "route_clustering/route_assignments.csv", "group_sensitivity": "route_clustering/sensitivity_scores.csv",
    "review": "route_review/route_review_table.csv", "signals": "route_review/review_signals.csv",
    "rules": "route_review/rule_evaluations.csv", "source_issues": "route_review/source_issue_dates.csv",
    "review_profiles": "route_review/route_day_type_evidence.csv",
    "review_sensitivity": "route_review/threshold_sensitivity_summary.csv",
    "baselines": "service_scenarios/scenario_baselines.csv",
    "forecast_scores": "october_validation/additional_october_scores.csv",
    "forecast_predictions": "october_validation/additional_october_predictions.csv",
    "forecast_coverage": "october_validation/interval_coverage.csv",
}
DOCUMENTS = {
    "cleaning": "cleaning_manifest.json",
    "features": "feature_manifest.json", "group_manifest": "route_clustering/manifest.json",
    "review_manifest": "route_review/manifest.json", "scenario_manifest": "service_scenarios/manifest.json",
    "forecast_manifest": "october_validation/october_manifest.json",
    "forecast_profile": "october_validation/experimental_profile.json",
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    documents = {key: json.loads((BASE / name).read_text(encoding="utf-8")) for key, name in DOCUMENTS.items()}
    products = {}
    for key, manifest in documents.items():
        if key == "forecast_profile":
            continue
        parent = (BASE / DOCUMENTS[key]).parent
        for name, details in manifest["products"].items():
            path = ROOT / name if "/" in name else parent / (name + ".csv")
            products[path.resolve()] = details
    profile = BASE / DOCUMENTS["forecast_profile"]
    if sha(profile) != documents["forecast_manifest"]["experimental_profile_sha256"]:
        raise ValueError("Forecast profile hash differs from its upstream manifest")
    # Cross-check documented lineage, not just individual CSVs.
    for key in ["group_manifest", "review_manifest", "scenario_manifest"]:
        for name, expected in documents[key].get("input_files", {}).items():
            if sha(ROOT / name) != expected:
                raise ValueError(f"Upstream input changed: {name}")
    tables = {}
    for alias, name in TABLES.items():
        path = BASE / name
        expected = products[path.resolve()]["sha256"]
        if sha(path) != expected:
            raise ValueError(f"Analytical product changed: {name}")
        frame = pd.read_csv(path, low_memory=False)
        tables[alias] = {"path": path.relative_to(ROOT).as_posix(), "sha256": expected,
                         "rows": len(frame), "columns": list(frame.columns)}
    return {"version": 1, "scope": "Manhattan historical planning study",
            "geometry_snapshot": "manhattan_20260903", "tables": tables,
            "documents": {key: {"path": (BASE / name).relative_to(ROOT).as_posix(), "sha256": sha(BASE / name)}
                          for key, name in DOCUMENTS.items()}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Replace the catalog after upstream revalidation")
    args = parser.parse_args()
    path = ROOT / "documentation/dashboard_data_manifest.json"
    if path.exists() and not args.refresh:
        raise SystemExit("Catalog already exists; use --refresh only after revalidating the upstream analysis")
    result = build()
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"Pinned {len(result['tables'])} tables and {len(result['documents'])} documents")
