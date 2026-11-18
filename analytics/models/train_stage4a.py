"""Stage 4a orchestrator: baselines, Ridge and Random Forest (notebook steps 22-34, 53, 55-56; spec 9.10).

Order is the safeguard (nothing about the test period can influence a choice):
  1. verify the Stage 3 feature version (sha256) and the period boundaries
  2. fit the 4 model pipelines on eligible TRAINING rows only
  3. score all 6 methods on the identical eligible VALIDATION rows; select the lowest validation MAE
     (a baseline may win; then it is served by its rule and there is no pipeline file)
  4. FREEZE: save every pipeline (joblib compress=3) + serving bundle + feature contract, check sizes, reload and
     confirm the reloaded pipelines reproduce the validation predictions exactly
  5. score the test period ONCE (a reused holdout: already examined while the method was developed)
  6. write metrics, per-route tables, the model manifest and the Stage 4a quality report

Usage (CMD, from the repo root):
    python -I analytics\\models\\train_stage4a.py --features data\\processed\\cta_ref__r20261113__gtfs8__to20260731\\features__delay1d --models analytics\\config\\models.json --sources analytics\\config\\sources.json --artifacts artifacts\\stage4a --out reports
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]  # `python -I` skips the script folder; add our own repo root
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import argparse  # noqa: E402
import io  # noqa: E402
import json  # noqa: E402
import platform  # noqa: E402
from datetime import datetime, timezone  # noqa: E402
from importlib.metadata import version as package_version  # noqa: E402

import joblib  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import sklearn  # noqa: E402

from analytics.features.model_features import KEY  # noqa: E402
from analytics.features.naming import (DEMAND_FEATURES, NEVER_PREDICTORS, NO_ACTUAL_REASON,  # noqa: E402
                                       NOTEBOOK_TO_SPEC, REQUIRED, SERVICE_FEATURES)
from analytics.features.schema import F, M  # noqa: E402
from analytics.models.baselines import BASELINE_RULES, baseline_predictor  # noqa: E402
from analytics.models.regressors import fit_candidates, make_predictor, training_rows  # noqa: E402
from analytics.models.report4a import write_report  # noqa: E402
from analytics.models.scoring import evaluate  # noqa: E402
from analytics.reconstruction.build_stage2 import git_commit, sha256  # noqa: E402

SPLITS = ["train", "validation", "test"]


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_feature_rows(features_dir: Path) -> tuple[pd.DataFrame, dict]:
    manifest = json.loads((features_dir / "features_manifest.json").read_text(encoding="utf-8"))
    rec = manifest["outputs"].get(F)
    if rec is None:
        raise SystemExit(f"{F} is not in the Stage 3 manifest; rebuild Stage 3 (schema >= 1.1.0)")
    if sha256(features_dir / F) != rec["sha256"]:
        raise SystemExit(f"{F} changed since Stage 3 recorded it; rebuild Stage 3")
    fr = pd.read_csv(features_dir / F, dtype={"route": str, "schedule_saved": str, "daytype": str},
                     parse_dates=["date"], keep_default_na=True)
    for c in ["eligible", "forecastable"]:
        fr[c] = fr[c].map({True: True, False: False, "True": True, "False": False}).astype(bool)
    if len(fr) != rec["rows"]:
        raise SystemExit("row count differs from the Stage 3 manifest")
    return fr, manifest


def check_periods(fr: pd.DataFrame, cfg: dict) -> dict:
    train_end, val_end = (pd.Timestamp(cfg["periods"][k]) for k in ["train_end", "validation_end"])
    expect = np.select([fr["date"].gt(val_end), fr["date"].gt(train_end)], ["test", "validation"], default="train")
    if not (fr["split"].to_numpy() == expect).all():
        raise SystemExit("feature-row split labels disagree with the periods in models.json")
    return {s: [str(fr.loc[fr["split"] == s, "date"].min().date()), str(fr.loc[fr["split"] == s, "date"].max().date())]
            for s in SPLITS}


def build_candidates(fr: pd.DataFrame, cfg: dict) -> dict:
    cands = {name: {"kind": "baseline", "columns": None, "predict": baseline_predictor(name)} for name in BASELINE_RULES}
    cands.update(fit_candidates(fr, cfg))
    return cands


def score_methods(frame: pd.DataFrame, cands: dict) -> tuple[pd.DataFrame, dict]:
    rows, preds = [], {}
    for name, c in cands.items():
        m, p = evaluate(frame, c["predict"])
        rows.append({"method": name, "kind": c["kind"], **m})
        preds[name] = p
    idx = [tuple(p.index) for p in preds.values()]
    if len(set(idx)) != 1:
        raise SystemExit("methods were scored on different rows; the comparison would not be on identical rows")
    return pd.DataFrame(rows), preds


def grouped_scores(frame: pd.DataFrame, preds: dict, by: str, methods: list[str] | None = None) -> pd.DataFrame:
    """Per-group metrics from precomputed predictions; withheld rows are counted, never scored."""
    rows = []
    for key, g in frame.groupby(by, dropna=False, sort=True):
        for method in methods or list(preds):
            p = preds[method]
            m, _ = evaluate(g, lambda r, p=p: p.loc[r.index].to_numpy())
            rows.append({by: key, "method": method, **m})
    return pd.DataFrame(rows)


def dump_info(obj, path: Path, compress: int) -> dict:
    joblib.dump(obj, path, compress=compress)
    buf = io.BytesIO()
    joblib.dump(obj, buf)  # same object, no compression: for the size comparison only (not written to disk)
    return {"file": path.as_posix(), "uncompressed_bytes": buf.getbuffer().nbytes,
            "compressed_bytes": path.stat().st_size, "compress": compress, "sha256": sha256(path)}


def freeze(cands: dict, selected: str, fr: pd.DataFrame, cfg: dict, art: Path, data_version: str,
           feature_sha: str, val_frame: pd.DataFrame, val_preds: dict) -> dict:
    models_dir = art / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    comp, limit = int(cfg["joblib_compress"]), int(cfg["max_model_file_bytes"])
    files = {}
    for name, c in cands.items():
        if c["kind"] != "baseline":
            files[f"models/{name}.joblib"] = dump_info(c["pipeline"], models_dir / f"{name}.joblib", comp)
    is_model = cands[selected]["kind"] != "baseline"
    bundle = {
        "selected_method": selected,
        "pipeline_file": f"models/{selected}.joblib" if is_model else None,
        "baseline_rule": BASELINE_RULES.get(selected),
        "feature_columns": cands[selected]["columns"],
        "required_fields": REQUIRED,
        "missing_history_policy": cfg["missing_history_policy"],
        "status_values": ["forecast", "withheld: <missing required fields>", f"withheld: {NO_ACTUAL_REASON}"],
        "training_end": cfg["periods"]["train_end"],
        "reporting_delay_days": 1,
        "unknown_route_handling": "one-hot encoder ignores unseen routes; history rules still apply",
        "prediction_floor": cfg["prediction_floor"],
        "schedule_inputs_required": True,
        "sklearn_version": sklearn.__version__,
        "artifact_version": cfg["artifact_version"],
        "data_version": data_version,
        "feature_rows_sha256": feature_sha,
    }
    files["models/serving_bundle.joblib"] = dump_info(bundle, models_dir / "serving_bundle.joblib", comp)
    for info in files.values():
        info["under_limit"] = info["compressed_bytes"] < limit
    too_big = [k for k, v in files.items() if not v["under_limit"]]
    if too_big:
        raise SystemExit(f"saved files at or above {limit:,} bytes: {too_big}")

    contract = {
        "artifact_version": cfg["artifact_version"], "data_version": data_version,
        "built_by": "analytics/features/model_features.py::build_features",
        "build_features_rules": [
            "target rows: every route/day in the forecast-time schedule (latest GTFS archive captured strictly before the target date)",
            "day_of_week (Monday = 0), month, is_weekend from the target date",
            "boardings_Nd_ago = boardings on the same route exactly N days earlier, N in 1, 7, 14, 21, 28 (exact-date lookup; missing stays missing, a recorded 0 stays 0)",
            "seasonal_count = number of available 7/14/21/28-day values (counted before filling)",
            "seasonal_mean = mean of the available 7/14/21/28-day values, only when at least two exist",
            "boardings_28d_available = 1 when the 28-day value exists, else 0",
            "boardings_28d_filled = 28-day value, or the mean of 7/14/21-day values when it is missing (Option 2)",
            "is_sunday_like_day = 1 when more than half of the day's scheduled bus trips belong to Sunday-only services (calendar.txt sunday=1, Monday-Friday=0) in the forecast-time archive",
            "scheduled_trips, scheduled_hours from the schedule saved before the target day (hours missing if any trip duration is invalid)",
        ],
        "eligibility": {"required_fields": REQUIRED,
                        "excluded_reasons": f"comma-joined names of missing required fields, or '{NO_ACTUAL_REASON}'"},
        "never_used_as_predictors": NEVER_PREDICTORS,
        "demand_features": DEMAND_FEATURES, "service_features": SERVICE_FEATURES,
        "notebook_to_spec_names": NOTEBOOK_TO_SPEC,
        "route_encoding": "OneHotEncoder(handle_unknown='ignore') fitted on eligible training rows; unseen routes get an all-zero encoding",
        "numeric_scaling": "StandardScaler fitted on eligible training rows",
        "prediction_floor": cfg["prediction_floor"],
        "availability": {"issue_time": "start of target day", "reporting_delay_days": 1,
                         "forecast_schedule_rule": "most recent schedule saved before the target day"},
    }
    contract_path = art / "feature_contract.json"
    contract_path.write_text(json.dumps(contract, indent=2), encoding="utf-8")

    # reload every compressed pipeline and confirm it reproduces the in-memory validation predictions EXACTLY
    reload_exact = {}
    eligible_val = val_frame.loc[val_frame["eligible"]]
    for name, c in cands.items():
        if c["kind"] == "baseline":
            continue
        again = make_predictor(joblib.load(models_dir / f"{name}.joblib"), c["columns"], cfg["prediction_floor"])
        reload_exact[name] = bool(np.array_equal(again(eligible_val), val_preds[name].to_numpy()))
    if not all(reload_exact.values()):
        raise SystemExit(f"a reloaded pipeline does not reproduce its predictions: {reload_exact}")
    vp = pd.concat([pd.DataFrame({"route": eligible_val["route"].to_numpy(), "date": eligible_val["date"].dt.strftime("%Y-%m-%d").to_numpy(),
                                  "method": name, "prediction": p.to_numpy()}) for name, p in val_preds.items()])
    vp.to_csv(art / "validation_predictions.csv", index=False, float_format="%.17g", lineterminator="\n")
    return {"files": files, "bundle": bundle, "contract_path": contract_path.as_posix(),
            "contract_sha256": sha256(contract_path), "reload_exact": reload_exact,
            "validation_predictions_sha256": sha256(art / "validation_predictions.csv"), "frozen_at": now()}


def score_test_once(test: pd.DataFrame, cands: dict, selected: str, train_routes: set[str], cfg: dict) -> dict:
    """Called exactly once, after freezing. Nothing returned here feeds back into any choice."""
    overall, preds = score_methods(test, cands)
    shown = list(dict.fromkeys([selected, *cands]))  # selected method first, then every frozen candidate
    t = test.assign(daytype=test["daytype"].fillna("(no record)"),
                    route_group=np.where(test["route"].isin(train_routes), "route seen in training", "route unseen in training"))
    by_daytype = grouped_scores(t, preds, "daytype", shown)
    by_seen = grouped_scores(t, preds, "route_group", shown)
    special = []
    for r in cfg["special_routes"]:
        g = test[test["route"] == r]
        for method in cands:
            if g.empty:
                special.append({"route": r, "method": method, "target_rows": 0, "scored_rows": 0, "withheld_rows": 0})
                continue
            m, _ = evaluate(g, lambda x, p=preds[method]: p.loc[x.index].to_numpy())
            special.append({"route": r, "method": method, **m})
    return {"overall": overall, "preds": preds, "by_daytype": by_daytype, "by_seen": by_seen,
            "special": pd.DataFrame(special), "unseen_routes": sorted(set(test["route"]) - train_routes),
            "scored_at": now()}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for a in ["--features", "--models", "--sources", "--artifacts", "--out"]:
        ap.add_argument(a, required=True, type=Path)
    args = ap.parse_args()
    cfg = json.loads(args.models.read_text(encoding="utf-8"))
    nref = json.loads(args.sources.read_text(encoding="utf-8"))["notebook_reference"]

    print("verifying Stage 3 feature rows ...", flush=True)
    fr, fmanifest = load_feature_rows(args.features)
    ranges = check_periods(fr, cfg)
    data_version = fmanifest["data_version"]
    feature_sha = sha256(args.features / F)
    matched = pd.read_csv(args.features / M, dtype={"route": str}, usecols=["route", "date", "split"], parse_dates=["date"])

    print("fitting Ridge and Random Forest on training rows ...", flush=True)
    cands = build_candidates(fr, cfg)
    train = training_rows(fr)
    train_routes = set(train["route"])

    print("scoring validation ...", flush=True)
    val = fr[fr["split"] == "validation"]
    vtable, vpreds = score_methods(val, cands)
    vtable = vtable.sort_values(cfg["selection_metric"], kind="mergesort").reset_index(drop=True)
    selected = vtable.iloc[0]["method"]
    print(f"selected on validation {cfg['selection_metric']}: {selected}", flush=True)

    print("freezing artifacts ...", flush=True)
    frozen = freeze(cands, selected, fr, cfg, args.artifacts, data_version, feature_sha, val, vpreds)

    print("scoring the test period once (reused holdout) ...", flush=True)
    test = fr[fr["split"] == "test"]
    tres = score_test_once(test, cands, selected, train_routes, cfg)

    per_route = pd.concat([grouped_scores(val, vpreds, "route").assign(split="validation"),
                           grouped_scores(test, tres["preds"], "route").assign(split="test")], ignore_index=True)
    withheld_by_route = (fr.loc[~fr["eligible"]].groupby(["split", "route", "excluded_reason"]).size()
                         .rename("rows").reset_index())

    runtime = {"python": platform.python_version(),
               **{p: package_version(p) for p in ["pandas", "numpy", "scikit-learn", "scipy", "joblib", "duckdb"]}}
    ctx = {"cfg": cfg, "nref": nref, "fr": fr, "matched": matched, "ranges": ranges, "data_version": data_version,
           "feature_sha": feature_sha, "fmanifest": fmanifest, "train_rows": len(train), "train_routes": train_routes,
           "validation": vtable, "selected": selected, "frozen": frozen, "test": tres, "per_route": per_route,
           "withheld_by_route": withheld_by_route, "runtime": runtime, "git_commit": git_commit(),
           "artifacts": args.artifacts}
    manifest = write_report(args.out, ctx)
    (args.artifacts / "model_manifest.json").write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    print(f"done -> {args.out / 'stage4a_quality_report.md'}; artifacts in {args.artifacts}")


if __name__ == "__main__":
    main()
