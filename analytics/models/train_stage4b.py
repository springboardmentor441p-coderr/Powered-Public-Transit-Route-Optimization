"""Stage 4b orchestrator: neural network models (an additional modelling experiment on top of Stage 4a).

Order is the safeguard (nothing about the test period can influence a choice):
  1. verify the Stage 3 feature rows, the raw ridership export and every frozen Stage 4a model file (sha256)
  2. build the 28-day windows for every feature row; the guard requires them to equal the Stage 3 lags
  3. split eligible TRAINING rows into the fit part and the early-stopping part (dates in neural.json);
     fit the preprocessor on the fit part only; train MLP, LSTM, GRU and 1D CNN with one recipe
  4. score all ten methods (2 baselines, 4 Stage 4a pipelines, 4 networks) on the identical eligible VALIDATION
     rows with the unchanged Stage 4a scoring; the Stage 4a methods must reproduce their stored predictions
     exactly; select the lowest validation MAE (and name the best network)
  5. FREEZE: save every network (joblib compress=3), check sizes, reload and require exact equality
  6. score the test period ONCE (a reused holdout)
  7. write the Stage 4b report and manifest. The Stage 4a serving bundle is never changed here.

Usage (CMD, from the repo root):
    python -I analytics\\models\\train_stage4b.py --features data\\processed\\cta_ref__r20261113__gtfs8__to20260731\\features__delay1d --neural analytics\\config\\neural.json --models analytics\\config\\models.json --sources analytics\\config\\sources.json --register data\\raw\\source_register.csv --stage4a artifacts\\stage4a --artifacts artifacts\\stage4b --out reports
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]  # `python -I` skips the script folder; add our own repo root
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import argparse  # noqa: E402
import csv  # noqa: E402
import json  # noqa: E402
import platform  # noqa: E402
import time  # noqa: E402
from importlib.metadata import version as package_version  # noqa: E402

import joblib  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from analytics.features.lags import to_history  # noqa: E402
from analytics.features.schema import F  # noqa: E402
from analytics.models import neural as N  # noqa: E402
from analytics.models.baselines import BASELINE_RULES, baseline_predictor  # noqa: E402
from analytics.models.regressors import MODEL_CANDIDATES, make_predictor, training_rows  # noqa: E402
from analytics.models.report4b import write_report  # noqa: E402
from analytics.models.sequences import build_sequences, check_against_lags  # noqa: E402
from analytics.models.train_stage4a import (check_periods, dump_info, grouped_scores, load_feature_rows,  # noqa: E402
                                            now, score_methods, score_test_once)
from analytics.reconstruction.build_stage2 import git_commit, sha256  # noqa: E402
from analytics.reconstruction.matching import load_ridership  # noqa: E402

SPLITS = ["train", "validation", "test"]


def load_history(register: Path, sources: dict, fmanifest: dict, cutoff: pd.Timestamp) -> tuple[pd.DataFrame, dict]:
    """The same raw ridership Stage 3 used (sha256 checked against the Stage 3 manifest), as a route/date history."""
    root = register.resolve().parent.parent.parent
    with open(register, newline="", encoding="utf-8") as f:
        rid = next(r for r in csv.DictReader(f)
                   if r["dataset_id"] == sources["ridership"]["dataset_id"] and r["is_primary"] == "True")
    path = root / rid["local_path"]
    expected = fmanifest["input_fingerprints"]["ridership"][rid["snapshot_id"]]
    if sha256(path) != expected:
        raise SystemExit("ridership export differs from the one Stage 3 used")
    rides, _ = load_ridership(path)
    rides = rides[rides["date"] <= cutoff.date()]
    return to_history(rides), {"snapshot_id": rid["snapshot_id"], "sha256": expected}


def load_stage4a(stage4a: Path, feature_sha: str, cfg4a: dict) -> tuple[dict, dict]:
    """Frozen Stage 4a methods, each file checked against its recorded sha256. Nothing is refitted."""
    m4a = json.loads((stage4a / "model_manifest.json").read_text(encoding="utf-8"))
    if m4a["input_fingerprints"]["feature_rows.csv"] != feature_sha:
        raise SystemExit("Stage 4a was trained on different feature rows; rerun Stage 4a first")
    cands = {name: {"kind": "baseline", "columns": None, "predict": baseline_predictor(name)} for name in BASELINE_RULES}
    for name, (kind, columns) in MODEL_CANDIDATES.items():
        rel = f"models/{name}.joblib"
        if sha256(stage4a / rel) != m4a["files"][rel]["sha256"]:
            raise SystemExit(f"{rel} changed since Stage 4a froze it")
        pipe = joblib.load(stage4a / rel)
        cands[name] = {"kind": kind, "columns": list(columns), "pipeline": pipe,
                       "predict": make_predictor(pipe, list(columns), cfg4a["prediction_floor"])}
    return cands, m4a


def check_stage4a_reproduced(stage4a: Path, m4a: dict, val: pd.DataFrame, vpreds: dict) -> dict:
    """Every Stage 4a method must give exactly the validation predictions Stage 4a stored."""
    path = stage4a / "validation_predictions.csv"
    if sha256(path) != m4a["validation_predictions_sha256"]:
        raise SystemExit("Stage 4a validation_predictions.csv changed since it was frozen")
    stored = pd.read_csv(path, dtype={"route": str}, parse_dates=["date"])
    rows = val.loc[val["eligible"], ["route", "date"]]
    out = {}
    for name in stored["method"].unique():
        s = rows.merge(stored[stored["method"] == name], on=["route", "date"], how="left", validate="one_to_one")
        out[name] = bool(np.array_equal(s["prediction"].to_numpy(dtype=float), vpreds[name].to_numpy()))
    if not all(out.values()):
        raise SystemExit(f"Stage 4a methods no longer reproduce their stored validation predictions: {out}")
    return out


def missing_days(fr: pd.DataFrame, observed: np.ndarray) -> list[dict]:
    out = []
    for s in SPLITS:
        m = (fr["split"].eq(s) & fr["eligible"]).to_numpy()
        o = observed[m]
        out.append({"split": s, "eligible rows": int(m.sum()), "window days": int(o.size),
                    "missing days": int((o == 0).sum()), "missing share %": round(100 * float((o == 0).mean()), 2),
                    "rows with any missing day": int((o == 0).any(axis=1).sum())})
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for a in ["--features", "--neural", "--models", "--sources", "--register", "--stage4a", "--artifacts", "--out"]:
        ap.add_argument(a, required=True, type=Path)
    args = ap.parse_args()
    ncfg = json.loads(args.neural.read_text(encoding="utf-8"))
    cfg4a = json.loads(args.models.read_text(encoding="utf-8"))
    sources = json.loads(args.sources.read_text(encoding="utf-8"))
    for k in ["train_end", "validation_end"]:
        if ncfg["periods"][k] != cfg4a["periods"][k]:
            raise SystemExit(f"neural.json {k} differs from models.json: the splits would not be identical")

    print("verifying inputs ...", flush=True)
    fr, fmanifest = load_feature_rows(args.features)
    ranges = check_periods(fr, cfg4a)
    feature_sha = sha256(args.features / F)
    hist, rid = load_history(args.register, sources, fmanifest, fr["date"].max())
    cands, m4a = load_stage4a(args.stage4a, feature_sha, cfg4a)

    print("building 28-day windows ...", flush=True)
    length = int(ncfg["sequence"]["length_days"])
    raw, observed = build_sequences(fr, hist, length)
    guard = check_against_lags(fr, raw, length)
    missing = missing_days(fr, observed)

    print("training the networks on the fit part ...", flush=True)
    fit, stop = N.training_parts(fr, ncfg)
    prep = N.NeuralPreprocessor().fit(fit, ncfg)

    def inputs(rows):
        r, o = raw[fr.index.get_indexer(rows.index)], observed[fr.index.get_indexer(rows.index)]
        seq, static = prep.transform(rows, r, o)
        return seq, static, prep.scale_target(rows["rides"])

    fit_in, stop_in = inputs(fit), inputs(stop)
    histories, summaries, models = [], {}, {}
    for name in N.ARCHITECTURES:
        t0 = time.time()
        model, h, summary = N.train_network(name, prep, fit_in, stop_in, ncfg)
        summary["train_seconds"] = round(time.time() - t0, 1)
        print(f"  {name}: {summary['epochs_run']} epochs, best {summary['best_epoch']}, "
              f"{summary['parameters']:,} parameters, {summary['train_seconds']} s", flush=True)
        histories += h
        summaries[name] = summary
        models[name] = model
        cands[name] = {"kind": "neural", "columns": None, "model": model,
                       "predict": N.make_nn_predictor(model, prep, hist, ncfg["prediction_floor"])}

    print("scoring validation (all ten methods, identical rows) ...", flush=True)
    val = fr[fr["split"] == "validation"]
    vtable, vpreds = score_methods(val, cands)
    reproduced = check_stage4a_reproduced(args.stage4a, m4a, val, vpreds)
    vtable = vtable.sort_values(ncfg["selection_metric"], kind="mergesort").reset_index(drop=True)
    selected = vtable.iloc[0]["method"]
    best_nn = vtable[vtable["kind"] == "neural"].iloc[0]["method"]
    print(f"lowest validation {ncfg['selection_metric']}: {selected}; best network: {best_nn}", flush=True)

    print("freezing the networks ...", flush=True)
    art = args.artifacts
    (art / "models").mkdir(parents=True, exist_ok=True)
    comp, limit = int(ncfg["joblib_compress"]), int(ncfg["max_model_file_bytes"])
    files, reload_exact = {}, {}
    eligible_val = val.loc[val["eligible"]]
    for name in N.ARCHITECTURES:
        rel = f"models/{name}.joblib"
        files[rel] = dump_info(N.network_payload(name, models[name], prep, ncfg, summaries[name]), art / rel, comp)
        files[rel]["under_limit"] = files[rel]["compressed_bytes"] < limit
        m2, p2 = N.load_network(joblib.load(art / rel))
        again = N.make_nn_predictor(m2, p2, hist, ncfg["prediction_floor"])(eligible_val)
        reload_exact[name] = bool(np.array_equal(again, vpreds[name].to_numpy()))
    if not all(v["under_limit"] for v in files.values()):
        raise SystemExit(f"saved files at or above {limit:,} bytes")
    if not all(reload_exact.values()):
        raise SystemExit(f"a reloaded network does not reproduce its predictions: {reload_exact}")
    vp = pd.concat([pd.DataFrame({"route": eligible_val["route"].to_numpy(),
                                  "date": eligible_val["date"].dt.strftime("%Y-%m-%d").to_numpy(),
                                  "method": name, "prediction": vpreds[name].to_numpy()}) for name in N.ARCHITECTURES])
    vp.to_csv(art / "validation_predictions.csv", index=False, float_format="%.17g", lineterminator="\n")
    pd.DataFrame(histories).to_csv(art / "training_history.csv", index=False, float_format="%.10g", lineterminator="\n")
    frozen = {"files": files, "reload_exact": reload_exact, "frozen_at": now(),
              "validation_predictions_sha256": sha256(art / "validation_predictions.csv"),
              "training_history_sha256": sha256(art / "training_history.csv")}

    print("scoring the test period once (reused holdout) ...", flush=True)
    test = fr[fr["split"] == "test"]
    train_routes = set(training_rows(fr)["route"])
    tres = score_test_once(test, cands, selected, train_routes, {**cfg4a, "special_routes": ncfg["special_routes"]})
    per_route = pd.concat([grouped_scores(val, vpreds, "route").assign(split="validation"),
                           grouped_scores(test, tres["preds"], "route").assign(split="test")], ignore_index=True)

    runtime = {"python": platform.python_version(),
               **{p: package_version(p) for p in ["torch", "pandas", "numpy", "scikit-learn", "joblib"]}}
    parts = [{"part": "fit (networks, encoder, scalers)", "dates": f"{fit['date'].min().date()}..{fit['date'].max().date()}",
              "eligible rows": len(fit)},
             {"part": "early stopping", "dates": f"{stop['date'].min().date()}..{stop['date'].max().date()}",
              "eligible rows": len(stop)},
             {"part": "validation (selection only)", "dates": "..".join(ranges["validation"]),
              "eligible rows": int(val["eligible"].sum())},
             {"part": "test (reused holdout, scored once)", "dates": "..".join(ranges["test"]),
              "eligible rows": int(test["eligible"].sum())}]
    ctx = {"ncfg": ncfg, "cfg4a": cfg4a, "ranges": ranges, "parts": parts, "stage4a_train_rows": len(training_rows(fr)),
           "data_version": fmanifest["data_version"], "feature_sha": feature_sha, "ridership": rid,
           "stage4a_manifest": m4a, "guard": guard, "missing": missing, "summaries": summaries,
           "prep": {"fitted_rows": prep.fitted_rows, "routes": len(prep.encoder.categories_[0]),
                    "boardings_mean": prep.mean, "boardings_std": prep.std},
           "validation": vtable, "selected": selected, "best_nn": best_nn, "reproduced": reproduced,
           "frozen": frozen, "test": tres, "per_route": per_route, "train_routes": train_routes,
           "route_sizes": (lambda m: {"min": float(m.min()), "min_route": m.idxmin(), "median": float(m.median()),
                                      "max": float(m.max()), "max_route": m.idxmax()})(fit.groupby("route")["rides"].mean()),
           "runtime": runtime, "git_commit": git_commit(), "artifacts": art}
    manifest = write_report(args.out, ctx)
    (art / "model_manifest.json").write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    print(f"done -> {args.out / 'stage4b_quality_report.md'}; artifacts in {art}")


if __name__ == "__main__":
    main()
