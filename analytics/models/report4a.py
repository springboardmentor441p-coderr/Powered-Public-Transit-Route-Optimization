"""Stage 4a quality report (markdown + JSON) and the model manifest. Reads results only; makes no choices."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from analytics.features.model_features import KEY
from analytics.features.naming import NO_ACTUAL_REASON
from analytics.reconstruction.report import _fmt, _table, compare

SPLITS = ["train", "validation", "test"]
METRICS = ["MAE", "RMSE", "WAPE_percent"]
REUSED = ("**Reused holdout.** June-July 2026 was already examined while the method was developed (mentor notebook), "
          "so these are reused-holdout results, not an untouched test. The serving method and every setting were "
          "fixed on validation before this scoring ran; nothing was tuned on these numbers.")

# Step 28: our Stage 3 features vs the notebook's build_features (item, ours, notebook, effect)
COMPARISON = [
    ("Target rows", "matched rides on the descriptive schedule (28,374)",
     "every route/day in the forecast-time schedule (28,312); rides left-joined", "different population (section 1)"),
    ("Scheduled days without rides", "not in the table", f"kept, withheld as `{NO_ACTUAL_REASON}`", "+24 withheld rows"),
    ("2025-11-23", "86 rows; only the schedule model withheld them", "not a target (no archive saved before it)", "-86 rows"),
    ("Sunday-like flag", "`is_sunday_holiday_service_day`: Sunday or observed federal holiday (fixed list)",
     "`is_sunday_like_day`: more than half of the date's scheduled bus trips are Sunday-only services",
     "different rule; both known at issue time; both disagree with daytype U on 0 rows (Stage 3 report, section 6)"),
    ("Required fields", "demand: 1/7/14/21-day lags + 28-day donor; schedule model adds valid trips/hours (trips > 0)",
     "one list for every method: 1/7/14/21-day lags, `boardings_28d_filled`, `scheduled_trips`, `scheduled_hours`",
     "demand-only model also needs the schedule, so all methods share identical rows"),
    ("Withheld-reason format", "`missing_rides_7_days_before;...`", "comma-joined field names, or `no recorded boardings`",
     "format only"),
    ("28-day lag", "overwritten with the filled value", "raw `boardings_28d_ago` kept; fill in `boardings_28d_filled`",
     "raw value stays auditable"),
    ("Names", "`rides_<k>_days_before`, `available_same_weekday_observations`, `past_four_same_weekdays_mean`, "
     "`rides_28_days_before_available`, `scheduled_service_hours`",
     "`boardings_<k>d_ago`, `seasonal_count`, `seasonal_mean`, `boardings_28d_available`, `scheduled_hours`", "rename only"),
    ("Feature order", "28-day flag appended last", "notebook order (route, calendar, flag, lags, 28d filled/available, "
     "seasonal count/mean, then schedule)", "order affects Random Forest tie-breaking"),
    ("Split edges", "train 2025-11-23..2026-03-31, validation Apr-May, test Jun-Jul",
     "train <= 2026-03-31 < validation <= 2026-05-31 < test", "identical once the 2025-11-23 row rule applies"),
    ("Route key", "trimmed, case kept", "trimmed and upper-cased", "0 effect (no lower-case route ids)"),
    ("Trip-hours validity", "endpoint/sequence rules; hours rounded to 1e-6",
     "also rejects times going backwards and departure < arrival; unrounded",
     "0 trips affected in these feeds (eligible counts match exactly); rounding difference below 1e-6 hours"),
    ("Rides dtype", "nullable integer", "float", "none"),
]


def _metric_cells(df: pd.DataFrame, cols=METRICS) -> pd.DataFrame:
    out = df.copy()
    for c in cols:
        if c in out:
            out[c] = out[c].map(lambda v: "unavailable" if v is None or pd.isna(v) else round(float(v), 3))
    if "coverage" in out:
        out["coverage"] = out["coverage"].map(lambda v: "" if v is None or pd.isna(v) else f"{100 * v:.1f}%")
    if "withheld_by_reason" in out:
        out["withheld_by_reason"] = out["withheld_by_reason"].map(
            lambda d: "; ".join(f"{k}: {v}" for k, v in d.items()) if isinstance(d, dict) and d else "")
    return out


def _records(df: pd.DataFrame) -> list[dict]:
    return json.loads(df.to_json(orient="records", date_format="iso"))


def row_counts(fr: pd.DataFrame, matched: pd.DataFrame, nref: dict) -> tuple[list[dict], pd.DataFrame, list[dict], dict]:
    comps, rows = [], []
    fkeys = set(zip(fr["route"], fr["date"]))
    dropped = matched[[k not in fkeys for k in zip(matched["route"], matched["date"])]]
    for s in SPLITS:
        g = fr[fr["split"] == s]
        tgt, elig = len(g), int(g["eligible"].sum())
        comps.append(compare(f"{s} target rows", nref["split_rows"][s]["target"], tgt, "notebook"))
        comps.append(compare(f"{s} eligible rows", nref["split_rows"][s]["eligible"], elig, "notebook"))
        m = int((matched["split"] == s).sum())
        d = int((dropped["split"] == s).sum())
        nr = int(g["rides"].isna().sum())
        rows.append({"split": s, "spec matched rows": m, "minus: no archive saved before the date": -d,
                     "plus: scheduled, no recorded boardings": nr, "= target rows (ours)": m - d + nr,
                     "notebook target": nref["split_rows"][s]["target"], "eligible (ours)": elig,
                     "notebook eligible": nref["split_rows"][s]["eligible"], "withheld (ours)": tgt - elig})
    recon = pd.DataFrame(rows)
    with_rides = set(zip(fr.loc[fr["rides"].notna(), "route"], fr.loc[fr["rides"].notna(), "date"]))
    identity = {
        "target identity holds in every split": bool((recon["= target rows (ours)"] ==
                                                       [int((fr["split"] == s).sum()) for s in SPLITS]).all()),
        "rows with rides == spec matched rows minus the dropped rows (as key sets)":
            with_rides == set(zip(matched["route"], matched["date"])) - set(zip(dropped["route"], dropped["date"])),
        "dates of dropped matched rows": sorted(dropped["date"].dt.strftime("%Y-%m-%d").unique().tolist()),
    }
    reasons = (fr.loc[~fr["eligible"]].groupby(["split", "excluded_reason"]).size().rename("rows").reset_index()
               .sort_values(["split", "rows"], ascending=[True, False]))
    return comps, recon, _records(reasons), identity


def honesty_lines(table: pd.DataFrame, period: str) -> list[str]:
    base = table[table["kind"] == "baseline"].sort_values("MAE", kind="mergesort")
    best = base.iloc[0]
    out = []
    for _, r in table[table["kind"] != "baseline"].iterrows():
        verdict = "**loses to**" if r["MAE"] > best["MAE"] else "beats"
        out.append(f"- {period}: `{r['method']}` {verdict} the best baseline `{best['method']}` on MAE "
                   f"({r['MAE']:.2f} vs {best['MAE']:.2f}; WAPE {r['WAPE_percent']:.2f}% vs {best['WAPE_percent']:.2f}%).")
    return out


def write_report(out_dir: Path, ctx: dict) -> dict:
    cfg, fr, sel, frozen, tres = ctx["cfg"], ctx["fr"], ctx["selected"], ctx["frozen"], ctx["test"]
    vt = ctx["validation"]
    created = datetime.now(timezone.utc).isoformat(timespec="seconds")
    comps, recon, reasons, identity = row_counts(fr, ctx["matched"], ctx["nref"])
    n_mis = sum(c["result"] == "MISMATCH" for c in comps)
    sel_kind = vt.set_index("method").loc[sel, "kind"]
    base_best = vt[vt["kind"] == "baseline"].iloc[0]

    files = pd.DataFrame([{"file": k, "uncompressed bytes": v["uncompressed_bytes"], "saved bytes (compress=3)": v["compressed_bytes"],
                           "saved MB": round(v["compressed_bytes"] / 1e6, 3), "under 20 MB": v["under_limit"],
                           "sha256 of saved file (first 16)": v["sha256"][:16]} for k, v in frozen["files"].items()])
    vcols = ["method", "kind", "target_rows", "scored_rows", "withheld_rows", "coverage", *METRICS]
    tcols = vcols
    special = tres["special"]
    scols = ["route", "method", "target_rows", "scored_rows", "withheld_rows", "withheld_by_reason", "MAE", "WAPE_percent"]
    by_dt = tres["by_daytype"][["daytype", "method", "target_rows", "scored_rows", "withheld_rows", *METRICS]]
    by_seen = tres["by_seen"][["route_group", "method", "target_rows", "scored_rows", "withheld_rows", *METRICS]]

    L = ["# Stage 4a quality report: baselines, Ridge and Random Forest", "",
         f"Generated {created} by `analytics/models/train_stage4a.py`. Conventions follow the mentor's reference "
         "notebook where it differs from spec v3.8. No neural networks in this stage.", "",
         f"- Data version: `{ctx['data_version']}`; feature rows sha256 `{ctx['feature_sha'][:16]}`",
         f"- Code version: git `{ctx['git_commit']}`; artifact version `{cfg['artifact_version']}`",
         f"- Periods: train {ctx['ranges']['train'][0]}..{ctx['ranges']['train'][1]}, validation "
         f"{ctx['ranges']['validation'][0]}..{ctx['ranges']['validation'][1]}, test {ctx['ranges']['test'][0]}.."
         f"{ctx['ranges']['test'][1]} ({cfg['periods']['test_status']})",
         f"- Settings (fixed in `analytics/config/models.json` before the run): Ridge alpha {cfg['ridge']['alpha']}; "
         f"Random Forest {cfg['random_forest']['n_estimators']} trees, max_depth {cfg['random_forest']['max_depth']}, "
         f"min_samples_leaf {cfg['random_forest']['min_samples_leaf']}, seed {cfg['seed']}; route one-hot "
         "(unknown routes ignored); numeric inputs standardized on training rows only; predictions floored at 0",
         f"- Row counts vs the notebook: **{len(comps) - n_mis} MATCH, {n_mis} MISMATCH**", "",
         f"## Selected serving method: `{sel}` ({sel_kind})", ""]
    if sel_kind == "baseline":
        L += [f"**A baseline won.** `{sel}` has the lowest validation MAE of all six methods, so it is served by its "
              f"fixed rule (`{frozen['bundle']['baseline_rule']}`) and the serving bundle has no pipeline file.", ""]
    else:
        L += [f"`{sel}` has the lowest validation MAE ({vt.iloc[0]['MAE']:.2f}) of the six methods; the best baseline "
              f"is `{base_best['method']}` ({base_best['MAE']:.2f}).", ""]
    L += ["Model vs best baseline (honest comparison; a loss is reported, not hidden):", "",
          *honesty_lines(vt, "validation"), *honesty_lines(tres["overall"], "test (reused holdout)"), "",
          "## 1. Row counts vs the notebook", "",
          "| check | notebook | ours | result | difference |", "|---|---:|---:|---|---:|",
          *[f"| {c['metric']} | {_fmt(c['spec'])} | {_fmt(c['ours'])} | **{c['result']}** | {c['difference']} |" for c in comps], "",
          "Why our earlier Stage 3 matched counts (spec 9.10.3: 14,501 / 6,859 / 7,014) differ from these: the "
          "notebook's target rows are the route/days in the **forecast-time** schedule. The 86 matched rows on "
          f"{', '.join(identity['dates of dropped matched rows'])} have no archive saved before that day, so they "
          "cannot be forecast; scheduled days with no recorded boardings are kept as targets and withheld.", "",
          *_table(recon), "",
          f"- Identity holds in every split: **{identity['target identity holds in every split']}**; the rows with "
          f"recorded boardings are exactly the spec matched rows minus the dropped rows (compared as key sets): "
          f"**{identity['rows with rides == spec matched rows minus the dropped rows (as key sets)']}**.",
          "- Eligibility uses one required-field list for all six methods, so every method is scored on the **same** "
          "rows: the common-row population and each method's own population coincide (spec 9.10.3 asks for both).", "",
          "Withheld reasons:", "", *_table(pd.DataFrame(reasons)), "",
          "## 2. Our Stage 3 features vs the notebook's `build_features` (aligned in Step 29)", "",
          "| # | item | our Stage 3 (before) | notebook (now used) | effect |", "|---|---|---|---|---|",
          *[f"| {i} | {a} | {b} | {c} | {d} |" for i, (a, b, c, d) in enumerate(COMPARISON, 1)], "",
          "## 3. Validation (identical eligible rows; selection uses MAE)", "",
          *_table(_metric_cells(vt[vcols])), "",
          f"Training: {ctx['train_rows']:,} eligible rows, {len(ctx['train_routes'])} routes.", "",
          "## 4. Saved artifacts (frozen before the test scoring)", "",
          f"Every `.joblib` file is saved with `joblib.dump(..., compress=3)`; compression changes the file encoding, "
          f"not the model. The 20 MB limit ({cfg['max_model_file_bytes']:,} bytes) is checked on the saved file. "
          "The uncompressed size is a dump of the same object into memory.", "",
          *_table(files), "",
          "Reloaded compressed pipelines reproduce the in-memory validation predictions exactly: " +
          ", ".join(f"`{k}` {v}" for k, v in frozen["reload_exact"].items()) + ".", "",
          f"`feature_contract.json` sha256 `{frozen['contract_sha256'][:16]}`; frozen at {frozen['frozen_at']}.", "",
          "## 5. Test period (scored once)", "", REUSED, "",
          f"Scored at {tres['scored_at']}, after freezing at {frozen['frozen_at']}.", "",
          *_table(_metric_cells(tres["overall"][tcols])), "",
          "### By reported day type (the daytype is used for reporting only, never as an input)", "",
          *_table(_metric_cells(by_dt)), "",
          "### Routes 10 and 130 (unseen in training; few rows, so percentages are noisy)", "",
          "Zero scored rows would mean unavailable metrics, not zero error.", "",
          *_table(_metric_cells(special[scols] if len(special.columns) >= len(scols) else special)), "",
          f"### Known vs unseen routes (unseen in test: {', '.join(tres['unseen_routes']) or 'none'})", "",
          *_table(_metric_cells(by_seen)), "",
          "## 6. Notes and limits", "",
          "- Settings and the selection rule were fixed before any result was read; the test period was scored once, "
          "after the artifacts were frozen and hashed.",
          "- The test period is a reused holdout (see section 5); no claim is made from it without that label.",
          "- Library versions differ from the notebook's run (see the model manifest). Baselines and Ridge are "
          "deterministic arithmetic; Random Forest tree-building can differ slightly between scikit-learn versions.",
          "- Boardings are daily counts: they say nothing about crowding. Scheduled service is not operated service.",
          "- Per-route results: `reports/stage4a_per_route_evaluation.csv`; withheld rows by route and reason: "
          "`reports/stage4a_withheld_by_route.csv`.", ""]
    if n_mis:
        L += ["## Mismatches", "", *[f"- {c['metric']}: notebook {_fmt(c['spec'])}, ours {_fmt(c['ours'])}"
                                     for c in comps if c["result"] == "MISMATCH"], ""]
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "stage4a_quality_report.md").write_text("\n".join(L), encoding="utf-8")
    per_route = ctx["per_route"].copy()
    per_route["withheld_by_reason"] = per_route["withheld_by_reason"].map(lambda d: json.dumps(d, sort_keys=True))
    per_route.to_csv(out_dir / "stage4a_per_route_evaluation.csv", index=False, lineterminator="\n")
    ctx["withheld_by_route"].to_csv(out_dir / "stage4a_withheld_by_route.csv", index=False, lineterminator="\n")

    results = {"row_count_comparisons": comps, "reconciliation": _records(recon), "reconciliation_identity": identity,
               "withheld_reasons": reasons, "validation": _records(vt), "selected_method": sel,
               "selected_kind": sel_kind, "test_reused_holdout": {"overall": _records(tres["overall"]),
                                                                  "by_daytype": _records(tres["by_daytype"]),
                                                                  "special_routes": _records(special),
                                                                  "known_vs_unseen": _records(tres["by_seen"]),
                                                                  "unseen_routes": tres["unseen_routes"],
                                                                  "status": cfg["periods"]["test_status"]},
               "files": frozen["files"], "reload_exact": frozen["reload_exact"]}
    (out_dir / "stage4a_quality_checks.json").write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")

    return {"artifact_version": cfg["artifact_version"], "created_at": created, "git_commit": ctx["git_commit"],
            "code": "analytics/models/train_stage4a.py", "data_version": ctx["data_version"],
            "input_fingerprints": {"feature_rows.csv": ctx["feature_sha"],
                                   "features_manifest.json outputs": {k: v["sha256"] for k, v in ctx["fmanifest"]["outputs"].items()}},
            "settings": cfg, "periods": ctx["ranges"], "training_rows": ctx["train_rows"],
            "training_routes": len(ctx["train_routes"]), "selected_method": sel, "selected_kind": sel_kind,
            "serving_bundle": frozen["bundle"], "files": frozen["files"],
            "feature_contract": {"file": "feature_contract.json", "sha256": frozen["contract_sha256"]},
            "validation_predictions_sha256": frozen["validation_predictions_sha256"],
            "reload_reproduces_validation_predictions": frozen["reload_exact"],
            "validation_metrics": _records(vt), "test_metrics_reused_holdout": _records(tres["overall"]),
            "test_status": cfg["periods"]["test_status"], "frozen_at": frozen["frozen_at"],
            "test_scored_at": tres["scored_at"], "runtime": ctx["runtime"],
            "key_columns": KEY}
