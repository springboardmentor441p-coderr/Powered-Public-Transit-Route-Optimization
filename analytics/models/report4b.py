"""Stage 4b quality report (an additional modelling experiment: neural networks), JSON checks, per-route table and
the model manifest. Reads results only; makes no choices."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from analytics.models.report4a import METRICS, REUSED, _metric_cells, _records
from analytics.reconstruction.report import _table

CORE = ["method", "kind", "target_rows", "scored_rows", "withheld_rows", "coverage", *METRICS]


def versus(table: pd.DataFrame, period: str) -> list[str]:
    """Each network against rf_demand and against the best baseline of the same period, plainly."""
    t = table.set_index("method")
    base = table[table["kind"] == "baseline"].sort_values("MAE", kind="mergesort").iloc[0]
    out = []
    for name, r in t[t["kind"] == "neural"].iterrows():
        for ref_name in ["rf_demand", base["method"]]:
            ref = t.loc[ref_name]
            verdict = "**loses to**" if r["MAE"] > ref["MAE"] else "beats"
            label = "the Random Forest" if ref_name == "rf_demand" else "the best baseline"
            out.append(f"- {period}: `{name}` {verdict} {label} `{ref_name}` on MAE ({r['MAE']:.2f} vs "
                       f"{ref['MAE']:.2f}; WAPE {r['WAPE_percent']:.2f}% vs {ref['WAPE_percent']:.2f}%).")
    return out


def test_observations(tres: dict, best_nn: str) -> list[str]:
    """Patterns seen in the test period, computed from the results. Reported only; nothing feeds back into a choice."""
    seen, day = tres["by_seen"], tres["by_daytype"]
    out = ["", "Observed in the test period (reused holdout; reported, not used for any choice):", ""]
    unseen = seen[seen["route_group"] == "route unseen in training"].set_index("method")
    if len(unseen) and unseen["scored_rows"].iloc[0] > 0:
        nets = unseen[unseen["kind"] == "neural"] if "kind" in unseen else unseen.loc[[m for m in unseen.index
                                                                                          if m in ("mlp", "lstm", "gru", "cnn")]]
        cells = ", ".join(f"`{m}` {r['WAPE_percent']:.1f}%" for m, r in nets.iterrows())
        sp = tres["special"].set_index(["route", "method"])
        worst = nets["WAPE_percent"].idxmax()
        per_route = "; ".join(f"route {r}: `{worst}` {sp.loc[(r, worst), 'WAPE_percent']:.1f}% vs `rf_demand` "
                              f"{sp.loc[(r, 'rf_demand'), 'WAPE_percent']:.1f}%" for r in tres["unseen_routes"]
                              if (r, worst) in sp.index)
        out.append(f"- **Unseen routes are the networks' weakest case.** On routes never seen in training "
                   f"({', '.join(tres['unseen_routes'])}; {int(unseen['scored_rows'].iloc[0])} rows) the WAPE is {cells}, "
                   f"against `rf_demand` {unseen.loc['rf_demand', 'WAPE_percent']:.1f}% ({per_route}). An unseen route "
                   "gets an all-zero route code; the networks appear to rely on that code more than on the route's own "
                   "28 days, while the Random Forest leans on the lags.")
    d = day[day["scored_rows"] > 0].set_index(["daytype", "method"])
    pair = "; ".join(f"{dt}: `{best_nn}` {d.loc[(dt, best_nn), 'WAPE_percent']:.2f}% vs `rf_demand` "
                     f"{d.loc[(dt, 'rf_demand'), 'WAPE_percent']:.2f}%"
                     for dt in ["W", "A", "U"] if (dt, best_nn) in d.index)
    out.append(f"- **Best network by day type (WAPE):** {pair}. A likely contributor on weekends: `month` in June-July "
               "lies outside the November-March range the networks learned from; a network extrapolates, a tree caps.")
    for dt, g in day[day["scored_rows"] > 0].groupby("daytype"):
        top = g.sort_values("WAPE_percent", kind="mergesort").iloc[0]
        if top["method"] in ("mlp", "lstm", "gru", "cnn"):
            out.append(f"- **One slice where a network is lowest:** on day type {dt}, `{top['method']}` has the lowest "
                       f"WAPE of all ten methods ({top['WAPE_percent']:.2f}%). One test slice; it changes nothing.")
    return out


def reasons(vtable: pd.DataFrame, tres: dict | None = None, best_nn: str | None = None,
            route_sizes: dict | None = None, fit_rows: int | None = None, train_rows: int | None = None,
            routes: int | None = None) -> list[str]:
    t = vtable.set_index("method")
    nn_best = t[t["kind"] == "neural"]["MAE"].min()
    base_best = t[t["kind"] == "baseline"]["MAE"].min()
    if nn_best <= t.loc["rf_demand", "MAE"]:
        return ["No network loses to the Random Forest on validation, so no explanation of a loss is needed."]
    size = (f"In the fit part, route averages range from {route_sizes['min']:,.0f} boardings a day (route "
            f"{route_sizes['min_route']}) to {route_sizes['max']:,.0f} (route {route_sizes['max_route']}), median "
            f"{route_sizes['median']:,.0f}." if route_sizes else "Route averages differ by two orders of magnitude.")
    days = f"about {fit_rows / routes:.0f} days per route for {routes} routes" if fit_rows and routes else "few days per route"
    out = [f"Every network loses to `rf_demand` on validation"
           + (" and to the best baseline as well." if nn_best > base_best else
              ", although at least one beats the best baseline."),
           "", "Likely reasons (not proven; each would need its own experiment):", "",
           f"- **Little data for a network.** The networks learn from {fit_rows:,} rows, fewer than the Random "
           f"Forest's {train_rows:,}, because three weeks are held back for early stopping. That is only {days}.",
           f"- **Very different route sizes.** {size} One shared scale makes small routes' errors tiny in the loss, "
           "so the network attends mostly to the big routes.",
           "- **The Random Forest's inputs are already the useful summaries.** Same-weekday lags and the seasonal mean "
           "carry most of the signal; a tree splits on them directly, while a network must learn them from 28 raw "
           "days.",
           "- **Loss vs metric.** The networks minimise squared error (MSE) but are ranked by MAE.",
           "- **Settings fixed in advance.** Architectures and learning settings were chosen once, before any result, "
           "and not tuned. That is deliberate (so validation stays a fair selection set), but it means these are "
           "untuned networks."]
    if tres is not None:
        out += test_observations(tres, best_nn)
    return out


def write_report(out_dir: Path, ctx: dict) -> dict:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    ncfg, vt, tres = ctx["ncfg"], ctx["validation"], ctx["test"]
    sel, best_nn = ctx["selected"], ctx["best_nn"]
    m4a = ctx["stage4a_manifest"]
    fit_rows = ctx["parts"][0]["eligible rows"]
    test_overall = tres["overall"].sort_values("MAE", kind="mergesort").reset_index(drop=True)

    L = ["# Stage 4b quality report: neural network models (an additional modelling experiment)", "",
         f"Generated {now} by `analytics/models/train_stage4b.py`. An additional modelling experiment on top of the "
         "mentor's reference work (Stage 4a): four small neural networks (MLP, LSTM, GRU, 1D CNN) that read the "
         "route's last 28 days, compared with the two baselines and the four Stage 4a models on identical rows.", "",
         f"- Data version: `{ctx['data_version']}`; feature rows sha256 `{ctx['feature_sha'][:16]}`; raw ridership "
         f"`{ctx['ridership']['snapshot_id']}` (sha256 `{ctx['ridership']['sha256'][:16]}`)",
         f"- Code version: git `{ctx['git_commit']}`; artifact version `{ncfg['artifact_version']}`; "
         f"Stage 4a artifacts `{m4a['artifact_version']}` (frozen files checked by sha256, nothing refitted)",
         f"- Settings fixed in `analytics/config/neural.json` before any network was trained: seed {ncfg['seed']}, "
         f"Adam lr {ncfg['training']['learning_rate']}, batch {ncfg['training']['batch_size']}, MSE on the scaled "
         f"target, at most {ncfg['training']['max_epochs']} epochs, early-stopping patience "
         f"{ncfg['training']['early_stopping_patience']}, CPU, deterministic algorithms, one thread",
         f"- Scoring: the unchanged Stage 4a module (`analytics/models/scoring.py`)", "",
         "## Summary", "",
         f"- Lowest validation MAE of all ten methods: **`{sel}`** ({vt.iloc[0]['MAE']:.2f}).",
         f"- Best network on validation: **`{best_nn}`** ({vt.set_index('method').loc[best_nn, 'MAE']:.2f}).",
         f"- Serving: the Stage 4a serving bundle (`{m4a['selected_method']}`) is **unchanged**. "
         + ("A network has the lowest validation MAE; changing the serving method needs a separate decision."
            if vt.iloc[0]["kind"] == "neural" else "No network beat it on validation."), "",
         "Each network against the Random Forest and the best baseline (a loss is stated, not hidden):", "",
         *versus(vt, "validation"), *versus(test_overall, "test (reused holdout)"), ""]

    L += ["## 1. Rows: identical to Stage 4a, with the training period split in time", "",
          *_table(pd.DataFrame(ctx["parts"])), "",
          f"- **The networks learn from fewer rows than the Stage 4a models:** {fit_rows:,} instead of "
          f"{ctx['stage4a_train_rows']:,} ({100 * fit_rows / ctx['stage4a_train_rows']:.1f}%). The last three weeks of "
          "training are held back to decide when to stop. This is an honest trade for a fair comparison: validation is "
          "never used for training or stopping and serves only for selection, exactly as for the Random Forest.",
          f"- The route encoder, calendar scaler and boardings scaler are fitted on the fit part only "
          f"({ctx['prep']['fitted_rows']:,} rows, {ctx['prep']['routes']} routes; boardings mean "
          f"{ctx['prep']['boardings_mean']:.1f}, std {ctx['prep']['boardings_std']:.1f}).",
          "- Eligibility and splits are read from `feature_rows.csv` unchanged; all ten methods are scored on the same "
          "rows, which Stage 4a's `score_methods` checks.", "",
          "28-day windows (exact calendar dates D-28..D-1). Guard: the window's D-1/7/14/21/28 positions equal the "
          "Stage 3 lag columns: " + ", ".join(f"`{k}` {v}" for k, v in ctx["guard"].items()) + ".", "",
          "Missing days inside eligible windows (value = scaled placeholder, `observed` = 0; never 0 boardings):", "",
          *_table(pd.DataFrame(ctx["missing"])), ""]

    arch = pd.DataFrame([{"network": k, "parameters": v["parameters"], "epochs run": v["epochs_run"],
                          "best epoch": v["best_epoch"], "best early-stopping loss (scaled MSE)": round(v["best_stop_loss"], 5),
                          "training seconds": v["train_seconds"]} for k, v in ctx["summaries"].items()])
    L += ["## 2. Networks", "",
          "All four use one recipe: same seed (reset before each), optimiser, batch size, loss, epoch limit and "
          "patience. The best early-stopping epoch's weights are restored.", "", *_table(arch), ""]

    show = _metric_cells(vt[CORE])
    L += ["## 3. Validation: all ten methods on the identical rows (selection)", "", *_table(show), "",
          "- The Stage 4a methods reproduce their stored validation predictions exactly: "
          + ", ".join(f"`{k}` {v}" for k, v in ctx["reproduced"].items()) + ".",
          f"- Selection rule: lowest validation {ncfg['selection_metric']}. Lowest overall: `{sel}`; best network: "
          f"`{best_nn}`.", ""]

    shown = list(dict.fromkeys([sel, best_nn, "rf_demand", "seasonal_mean", *vt["method"]]))
    L += ["## 4. Test period (reused holdout, scored once)", "", REUSED, "",
          *_table(_metric_cells(test_overall[CORE])), "", "### By reported day type", "",
          *_table(_metric_cells(tres["by_daytype"][tres["by_daytype"]["method"].isin(shown)]
                                [["daytype", "method", "scored_rows", *METRICS]])), "",
          "### Routes seen vs unseen in training", "",
          *_table(_metric_cells(tres["by_seen"][["route_group", "method", "scored_rows", *METRICS]])), "",
          f"Unseen routes in the test period: {', '.join(tres['unseen_routes']) or 'none'}.", "",
          "### Routes 10 and 130, separately", ""]
    sp = tres["special"]
    for r in ncfg["special_routes"]:
        g = sp[sp["route"] == r]
        L += [f"Route {r}:", "", *_table(_metric_cells(g[[c for c in ["method", "target_rows", "scored_rows",
                                                                       "withheld_rows", *METRICS] if c in g]])), ""]

    files = pd.DataFrame([{"file": k, "uncompressed bytes": v["uncompressed_bytes"], "saved bytes": v["compressed_bytes"],
                           "compress": v["compress"], "under 20 MB": v["under_limit"],
                           "reload reproduces validation exactly": ctx["frozen"]["reload_exact"][k.split("/")[1][:-7]],
                           "sha256": v["sha256"][:16]} for k, v in ctx["frozen"]["files"].items()])
    L += ["## 5. Saved files", "",
          "Each file holds the weights as numpy arrays, the fitted preprocessor and the architecture settings "
          "(joblib, compress=3). They were frozen before the test period was scored.", "", *_table(files), "",
          "## 6. Why the networks win or lose", "",
          *reasons(vt, tres, best_nn, ctx.get("route_sizes"), fit_rows, ctx["stage4a_train_rows"],
                   ctx["prep"]["routes"]), "",
          "## 7. Reproducibility", "",
          "- Fixed seed reset before each network; seeded shuffling; `torch.use_deterministic_algorithms(True)`; one "
          "intra-op and one inter-op thread (the equivalent of Stage 4a's `n_jobs=1`); CPU; float32.",
          "- Predictions run one row at a time, so a row's forecast does not depend on which other rows are predicted "
          "with it (float32 results otherwise depend on the batch size).",
          f"- Validation predictions sha256 `{ctx['frozen']['validation_predictions_sha256'][:16]}`; training history "
          f"sha256 `{ctx['frozen']['training_history_sha256'][:16]}`. A rerun must give the same values.",
          "- Runtime: " + ", ".join(f"{k} {v}" for k, v in ctx["runtime"].items()), ""]

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "stage4b_quality_report.md").write_text("\n".join(L), encoding="utf-8")
    ctx["per_route"].to_csv(out_dir / "stage4b_per_route_evaluation.csv", index=False, float_format="%.6f",
                            lineterminator="\n")
    checks = {"generated_at": now, "artifact_version": ncfg["artifact_version"], "parts": ctx["parts"],
              "guard": ctx["guard"], "missing_days": ctx["missing"], "networks": ctx["summaries"],
              "stage4a_reproduced": ctx["reproduced"], "reload_exact": ctx["frozen"]["reload_exact"],
              "files": ctx["frozen"]["files"], "selected_lowest_validation_mae": sel, "best_network": best_nn,
              "validation": _records(vt.drop(columns="withheld_by_reason")),
              "test_reused_holdout": _records(test_overall.drop(columns="withheld_by_reason"))}
    (out_dir / "stage4b_quality_checks.json").write_text(json.dumps(checks, indent=2, default=str), encoding="utf-8")
    return {"artifact_version": ncfg["artifact_version"], "created_at": now, "git_commit": ctx["git_commit"],
            "code": "analytics/models/train_stage4b.py", "description": "additional modelling experiment: neural networks",
            "data_version": ctx["data_version"],
            "input_fingerprints": {"feature_rows.csv": ctx["feature_sha"], "ridership": ctx["ridership"],
                                   "stage4a_model_manifest_artifact_version": m4a["artifact_version"]},
            "settings": ncfg, "parts": ctx["parts"], "preprocessor": ctx["prep"], "networks": ctx["summaries"],
            "selected_lowest_validation_mae": sel, "best_network": best_nn,
            "serving": f"unchanged: Stage 4a serving bundle ({m4a['selected_method']})",
            "files": ctx["frozen"]["files"], "reload_reproduces_validation_predictions": ctx["frozen"]["reload_exact"],
            "validation_predictions_sha256": ctx["frozen"]["validation_predictions_sha256"],
            "training_history_sha256": ctx["frozen"]["training_history_sha256"],
            "validation_metrics": _records(vt.drop(columns="withheld_by_reason")),
            "test_metrics_reused_holdout": _records(test_overall.drop(columns="withheld_by_reason")),
            "test_status": ncfg["periods"]["test_status"], "frozen_at": ctx["frozen"]["frozen_at"],
            "test_scored_at": tres["scored_at"], "runtime": ctx["runtime"]}
