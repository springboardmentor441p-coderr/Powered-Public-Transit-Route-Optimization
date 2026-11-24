"""
Autonomous Continuous Training (CT) & Self-Upgrading Engine for RouteRanker.
1. Fetches fresh online ridership data (fetch_online_data.py).
2. Re-runs ETL & feature engineering if new data arrives or force_retrain=True.
3. Trains Challenger models in artifacts_staging/.
4. Evaluates Challenger WAPE against Champion (artifacts/training_metrics.json).
5. Backs up Champion, promotes Challenger if WAPE improves or stays within tolerance,
   normalizes artifact_path references, logs audit entry to reports/retrain_history.jsonl,
   and notifies FastAPI backend (/api/models/reload) to hot-swap models in memory.
"""
import os
import sys
import json
import shutil
import importlib
from datetime import datetime, timezone
from pathlib import Path
import requests

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
os.chdir(ROOT_DIR)

from analytics.fetch_online_data import fetch_latest_ridership
import train_models

PROD_DIR = ROOT_DIR / "artifacts"
STAGING_DIR = ROOT_DIR / "artifacts_staging"
BACKUP_DIR = ROOT_DIR / "artifacts_backup"
REPORTS_DIR = ROOT_DIR / "reports"
HISTORY_LOG = REPORTS_DIR / "retrain_history.jsonl"


def _run_etl_steps():
    etl_modules = [
        "analytics.01_source_register",
        "analytics.02_clean_boardings",
        "analytics.03_gtfs_calendar_expansion",
        "analytics.04_snapshot_selection_and_join",
        "analytics.05_route_structure_and_overlap",
        "analytics.build_reference_datasets",
    ]
    for mod_name in etl_modules:
        mod = importlib.import_module(mod_name)
        if hasattr(mod, "run"):
            mod.run()


def _get_service_wape(metrics: dict) -> float:
    sel = metrics.get("matched_service", {}).get("selected_serving_model", "ridge")
    wape = metrics.get("matched_service", {}).get("models", {}).get(sel, {}).get("test", {}).get("wape_pct")
    return float(wape) if wape is not None else float("inf")


def _append_audit_log(entry: dict):
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def run_autonomous_cycle(force_retrain: bool = False, wape_tolerance_pct: float = 0.25, api_url: str = "http://localhost:8000") -> dict:
    started_at = datetime.now(timezone.utc).isoformat()
    fetch_res = fetch_latest_ridership()

    if not fetch_res.get("updated") and not force_retrain:
        summary = {
            "timestamp_utc": started_at,
            "status": "skipped_no_new_data",
            "fetch_detail": fetch_res,
            "promoted": False,
        }
        _append_audit_log(summary)
        return summary

    # Run ETL feature pipeline if new online data was fetched
    if fetch_res.get("updated"):
        _run_etl_steps()

    # Train Challenger in staging directory
    if STAGING_DIR.exists():
        shutil.rmtree(STAGING_DIR, ignore_errors=True)
    STAGING_DIR.mkdir(parents=True, exist_ok=True)

    version_tag = f"v4.0-auto-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    train_models.run(
        artifacts_dir=str(STAGING_DIR),
        processed_dir=str(ROOT_DIR / "data" / "processed"),
        reports_dir=str(REPORTS_DIR),
        model_version=version_tag,
    )

    prod_metrics_path = PROD_DIR / "training_metrics.json"
    new_metrics_path = STAGING_DIR / "training_metrics.json"

    new_metrics = json.loads(new_metrics_path.read_text(encoding="utf-8"))
    new_wape = _get_service_wape(new_metrics)

    old_wape = float("inf")
    if prod_metrics_path.exists():
        old_metrics = json.loads(prod_metrics_path.read_text(encoding="utf-8"))
        old_wape = _get_service_wape(old_metrics)

    # Champion vs. Challenger Gate
    if new_wape <= old_wape + wape_tolerance_pct:
        # Backup current production artifacts
        if PROD_DIR.exists():
            ts_backup = BACKUP_DIR / datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            ts_backup.mkdir(parents=True, exist_ok=True)
            for item in PROD_DIR.glob("*"):
                if item.is_file():
                    shutil.copy2(item, ts_backup / item.name)

        PROD_DIR.mkdir(parents=True, exist_ok=True)
        # Rewrite staging artifact paths in training_metrics.json to point to production artifacts/
        for family in ("demand_only", "matched_service"):
            models_dict = new_metrics.get(family, {}).get("models", {})
            for m_name, m_info in models_dict.items():
                m_info["artifact_path"] = str(PROD_DIR / f"{family}_{m_name}.joblib")
        new_metrics_path.write_text(json.dumps(new_metrics, indent=2), encoding="utf-8")

        for item in STAGING_DIR.glob("*"):
            if item.is_file():
                shutil.copy2(item, PROD_DIR / item.name)

        # Trigger live hot-reload in FastAPI if running
        reload_status = "not_called"
        try:
            r = requests.post(f"{api_url}/api/models/reload", timeout=5)
            reload_status = f"http_{r.status_code}"
        except Exception as e:
            reload_status = f"offline ({e})"

        summary = {
            "timestamp_utc": started_at,
            "status": "promoted",
            "model_version": version_tag,
            "old_wape_pct": None if old_wape == float("inf") else old_wape,
            "new_wape_pct": new_wape,
            "fetch_detail": fetch_res,
            "api_reload": reload_status,
            "promoted": True,
        }
    else:
        summary = {
            "timestamp_utc": started_at,
            "status": "rejected_degraded_accuracy",
            "model_version": version_tag,
            "old_wape_pct": old_wape,
            "new_wape_pct": new_wape,
            "fetch_detail": fetch_res,
            "promoted": False,
        }

    shutil.rmtree(STAGING_DIR, ignore_errors=True)
    _append_audit_log(summary)
    return summary


if __name__ == "__main__":
    force = "--force" in sys.argv
    res = run_autonomous_cycle(force_retrain=force)
    print(json.dumps(res, indent=2))
