"""GET /api/models/summary: the Data screen's model card, read from the committed model manifests
(artifacts/stage4a/model_manifest.json, artifacts/stage4b/model_manifest.json). Nothing is refitted or rescored.

What was tried (two baselines, two ridge, two random forests, four neural networks), what serves predictions, and how
much it beats the best baseline on validation and on the reused test period, each method with a plain label. The
results were measured on data up to the end of the test period, so under an earlier cutoff they are not shown.
"""
from __future__ import annotations

import json
from datetime import date

import psycopg
from fastapi import APIRouter, Depends, Query

from backend.app.db import cutoff_block, get_conn, permitted_through, resolve_version
from backend.app.labels import envelope
from backend.importer.import_data import REPO_ROOT

router = APIRouter(tags=["models"])
MANIFEST_4A = REPO_ROOT / "artifacts" / "stage4a" / "model_manifest.json"
MANIFEST_4B = REPO_ROOT / "artifacts" / "stage4b" / "model_manifest.json"
AFTER_CUTOFF = "the models were evaluated on data after the cutoff, so their results are not shown"

LABELS = {
    "last_week": "Same day last week",
    "seasonal_mean": "4-week average (same weekday 7, 14, 21 and 28 days earlier)",
    "ridge_demand": "Ridge regression, ride history",
    "ridge_service": "Ridge regression, ride history and scheduled service",
    "rf_demand": "Random forest, ride history",
    "rf_service": "Random forest, ride history and scheduled service",
    "mlp": "Neural network (multilayer perceptron)",
    "lstm": "Neural network (LSTM, last 28 days)",
    "gru": "Neural network (GRU, last 28 days)",
    "cnn": "Neural network (1D convolution, last 28 days)",
}
KINDS = {"baseline": "baseline rule", "ridge": "linear model", "rf": "tree ensemble", "neural": "neural network"}


def label(method: str) -> str:
    return LABELS.get(method, method.replace("_", " "))


def missing_words(reason: str) -> str:
    """'boardings_1d_ago, boardings_7d_ago' -> 'rides 1 day and 7 days earlier missing'."""
    if not reason.startswith("boardings"):
        return reason.replace("boardings", "rides")
    days = [p.strip().split("_")[1].rstrip("d") for p in reason.split(",")]
    return "rides " + " and ".join(f"{d} day{'' if d == '1' else 's'}" for d in days) + " earlier missing"


def _split(m: dict | None) -> dict | None:
    return None if m is None else {"mae": m["MAE"], "wape_percent": m["WAPE_percent"], "rmse": m["RMSE"],
                                   "scored_rows": m["scored_rows"], "withheld_rows": m["withheld_rows"],
                                   "coverage": m["coverage"]}


def gain(model: dict | None, base: dict | None) -> dict | None:
    """How much lower the model's MAE is than the baseline's (negative = the model is worse)."""
    if model is None or base is None:
        return None
    return {"model_mae": model["MAE"], "baseline_mae": base["MAE"], "mae_reduction": base["MAE"] - model["MAE"],
            "mae_reduction_percent": 100 * (base["MAE"] - model["MAE"]) / base["MAE"],
            "model_wape_percent": model["WAPE_percent"], "baseline_wape_percent": base["WAPE_percent"]}


@router.get("/api/models/summary")
def models_summary(cutoff: date | None = Query(None, description="use only service dates on or before this date"),
                   data_version: str | None = None, conn: psycopg.Connection = Depends(get_conn)) -> dict:
    v = resolve_version(conn, data_version)
    a = json.loads(MANIFEST_4A.read_text(encoding="utf-8"))
    b = json.loads(MANIFEST_4B.read_text(encoding="utf-8"))
    test_end = date.fromisoformat(a["periods"]["test"][1])
    if permitted_through(v, cutoff) < test_end:
        return envelope(v, cutoff_block(v, cutoff), available=False, reason=AFTER_CUTOFF)

    val = {m["method"]: m for m in b["validation_metrics"]}
    test = {m["method"]: m for m in b["test_metrics_reused_holdout"]}
    order = sorted(val, key=lambda k: val[k]["MAE"])
    selected = a["selected_method"]
    baselines = [k for k in order if val[k]["kind"] == "baseline"]
    networks = [k for k in order if val[k]["kind"] == "neural"]
    best_base, best_net = baselines[0], (networks[0] if networks else None)
    sel_val = {m["method"]: m for m in a["validation_metrics"]}[selected]
    sel_test = {m["method"]: m for m in a["test_metrics_reused_holdout"]}[selected]

    return envelope(
        v, cutoff_block(v, cutoff), available=True,
        artifact_version=a["artifact_version"], git_commit=a["git_commit"], created_at=a["created_at"],
        extra_experiment={"artifact_version": b["artifact_version"], "git_commit": b["git_commit"]},
        target_label="recorded rides per route per day, forecast at the start of the day",
        metric_label="mean absolute error (rides per route-day); lower is better",
        periods={"train": a["periods"]["train"], "validation": a["periods"]["validation"], "test": a["periods"]["test"]},
        test_status=a["test_status"],
        methods=[{"method": k, "label": label(k), "kind": val[k]["kind"],
                  "kind_label": KINDS.get(val[k]["kind"], val[k]["kind"]),
                  "validation": _split(val[k]), "test": _split(test.get(k))} for k in order],
        selected={"method": selected, "label": label(selected)},
        best_baseline={"method": best_base, "label": label(best_base)},
        best_network=None if best_net is None else {"method": best_net, "label": label(best_net),
                                                     "beats_selected": val[best_net]["MAE"] < val[selected]["MAE"]},
        gain={"validation": gain(val.get(selected), val.get(best_base)),
              "test": gain(test.get(selected), test.get(best_base))},
        withheld={"validation": [{"reason": missing_words(r), "rows": n} for r, n in sel_val["withheld_by_reason"].items()],
                  "test": [{"reason": missing_words(r), "rows": n} for r, n in sel_test["withheld_by_reason"].items()]},
        selection_note="the method with the lowest validation error was chosen before the test period was scored",
    )
