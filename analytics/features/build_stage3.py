"""Stage 3 orchestrator: feature contracts (spec 9.9, 9.10.2-9.10.4, 9.14.3). No model is trained.

Reads the raw ridership export and the Stage 2 data version, and writes to
data/processed/<stage-2 data version>/features__delay<d>d/:
    daily_forecasting_features.csv            16 columns, spec 9.9.1
    expanded_demand_service_features.csv      22 columns, spec 9.9.2
    forecast_schedule_inputs.csv              forecast-input schedule selection (spec 9.14.3)
    policy_eligibility_demand.csv / policy_eligibility_matched.csv   Option 1 / Option 2 status per row
    lag_absence_by_route_split.csv            missing history per route/split/lag
    feature_schema.json, features_manifest.json
and reports/stage3_quality_report.md + stage3_quality_checks.json.

Usage (CMD, from the repo root):
    python -I analytics\\features\\build_stage3.py --config analytics\\config\\sources.json --features analytics\\config\\features.json --register data\\raw\\source_register.csv --out reports
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
from datetime import date, datetime, timedelta, timezone  # noqa: E402

import pandas as pd  # noqa: E402

from analytics.features import forecast_schedule as fs  # noqa: E402
from analytics.features.lags import (add_calendar, add_exact_lags, add_seasonal, observed_holidays,  # noqa: E402
                                     sunday_holiday_service_day, to_history)
from analytics.features.naming import LAG_EXPORT  # noqa: E402
from analytics.features.preprocess import prepare, withheld_counts  # noqa: E402
from analytics.features.schema import D, M, build_schema, classify_missing_lag, export_columns, lag_absence_table  # noqa: E402
from analytics.features.splits import SPLITS, assign_split, date_overlap, parse_ranges  # noqa: E402
from analytics.reconstruction.build_stage2 import git_commit, sha256  # noqa: E402
from analytics.reconstruction.gtfs_tables import bus_crosswalk, open_snapshot  # noqa: E402
from analytics.reconstruction.matching import load_ridership  # noqa: E402
from analytics.reconstruction.report import _fmt, _table, compare  # noqa: E402
from analytics.reconstruction.snapshot_select import archive_available_from, select_snapshot  # noqa: E402

KEY = ["route", "date"]


def iso(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s).dt.strftime("%Y-%m-%d")


def write_csv(df: pd.DataFrame, path: Path, outputs: dict) -> None:
    out = df.copy()
    for c in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[c]):
            out[c] = iso(out[c])
    out.to_csv(path, index=False, lineterminator="\n")
    outputs[path.name] = {"rows": len(out), "columns": len(out.columns), "sha256": sha256(path)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for a in ["--config", "--features", "--register", "--out"]:
        ap.add_argument(a, required=True, type=Path)
    args = ap.parse_args()
    cfg = json.loads(args.config.read_text(encoding="utf-8"))
    fcfg = json.loads(args.features.read_text(encoding="utf-8"))
    ref = cfg["stage3_reference"]
    root = args.register.resolve().parent.parent.parent
    delay = int(fcfg["reporting_delay_days"])
    lags, seasonal = fcfg["lags_days"], fcfg["seasonal_lags_days"]
    w_start, w_end = (date.fromisoformat(x) for x in fcfg["target_window"])
    observance_rule = fcfg["sunday_service_holidays"].get("observance_rule", "actual_date")
    holidays = observed_holidays({date.fromisoformat(h["date"]): h["name"]
                                  for h in fcfg["sunday_service_holidays"]["dates"]}, observance_rule)
    demand_ranges = parse_ranges(fcfg["splits"]["demand_only"])
    matched_ranges = parse_ranges(fcfg["splits"]["matched"])

    # ---------------------------------------------------------------- inputs: raw ridership + Stage 2 version
    with open(args.register, newline="", encoding="utf-8") as f:
        register = list(csv.DictReader(f))
    rid = next(r for r in register if r["dataset_id"] == cfg["ridership"]["dataset_id"] and r["is_primary"] == "True")
    s2_end = date.fromisoformat(cfg["stage2_reference"]["analysis_period"][1])
    s2_version = f"cta_ref__r{rid['snapshot_id'][-8:]}__gtfs{len(cfg['gtfs']['archives'])}__to{s2_end:%Y%m%d}"
    s2_dir = root / "data" / "processed" / s2_version
    s2_manifest_path = s2_dir / "manifest.json"
    if not s2_manifest_path.exists():
        raise SystemExit(f"Stage 2 data version {s2_version} not found; run build_stage2.py first")
    s2 = json.loads(s2_manifest_path.read_text(encoding="utf-8"))
    print("verifying Stage 2 outputs and raw ridership ...", flush=True)
    for fname, o in s2["outputs"].items():
        if sha256(s2_dir / fname) != o["sha256"]:
            raise SystemExit(f"{fname} changed since Stage 2 recorded it; rebuild Stage 2")
    if sha256(root / rid["local_path"]) != s2["input_fingerprints"][rid["snapshot_id"]]:
        raise SystemExit("ridership export differs from the one Stage 2 used")
    gtfs_reg = {r["snapshot_id"]: r for r in register if r["dataset_id"] == cfg["gtfs"]["dataset_id"]}
    archives_cfg = sorted(cfg["gtfs"]["archives"], key=lambda a: a["captured"])
    archives = [{"snapshot_id": a["snapshot_id"], "captured": date.fromisoformat(a["captured"])} for a in archives_cfg]
    captured = {a["snapshot_id"]: a["captured"] for a in archives}
    extracted = {sid: root / Path(gtfs_reg[sid]["local_path"]).parent / "extracted" for sid in captured}

    # ---------------------------------------------------------------- Step 19-20: demand features
    print("building exact-date lags ...", flush=True)
    rides_all, _ = load_ridership(root / rid["local_path"])
    rides_all = rides_all[rides_all["date"] <= w_end]  # rows dated on/before the cutoff; earlier history kept
    hist = to_history(rides_all)
    feat = add_calendar(add_seasonal(add_exact_lags(hist, lags, delay), seasonal, fcfg["seasonal_min_observations"]))
    feat = feat[(feat["date"] >= pd.Timestamp(w_start)) & (feat["date"] <= pd.Timestamp(w_end))].copy()  # after lookups
    feat["split"] = assign_split(feat["date"], demand_ranges)
    daily = feat[export_columns(D)].reset_index(drop=True)

    # ---------------------------------------------------------------- Step 21: matched demand + schedule
    s2_matched = pd.read_csv(s2_dir / "expanded_matched_utilization.csv", dtype={"route": str, "route_id": str})
    s2_matched["date"] = pd.to_datetime(s2_matched["date"])
    mm = feat.drop(columns="split").merge(
        s2_matched[["route", "date", "rides", "scheduled_trips", "scheduled_service_hours", "duration_complete",
                    "snapshot_id"]].rename(columns={"rides": "_rides_s2", "snapshot_id": "source_snapshot"}),
        on=KEY, how="inner", validate="one_to_one")
    if len(mm) != len(s2_matched):
        raise SystemExit(f"{len(s2_matched) - len(mm)} Stage 2 matched rows have no feature row")
    if not (mm["rides"].astype("Int64") == mm["_rides_s2"].astype("Int64")).all():
        raise SystemExit("rides differ between the features and the Stage 2 matched table")
    mm["service_date"] = mm["date"]
    mm["scheduled_trips"] = mm["scheduled_trips"].astype("Int64")
    mm["scheduled_service_hours"] = mm["scheduled_service_hours"].astype("Float64")
    mm["archive_available_from"] = pd.to_datetime(mm["source_snapshot"].map(lambda s: archive_available_from(captured[s])))
    mm["split"] = assign_split(mm["date"], matched_ranges)
    matched = mm[export_columns(M)].sort_values(KEY).reset_index(drop=True)

    # ---------------------------------------------------------------- forecast-input schedule (spec 9.14.3)
    print("forecast-input schedule selection ...", flush=True)
    p_start, p_end = (date.fromisoformat(x) for x in cfg["stage2_reference"]["analysis_period"])
    pairs = fs.selection_pairs(p_start, p_end, archives)
    sched = pd.read_csv(s2_dir / "expanded_scheduled_route_day_service.csv", dtype={"route": str, "route_id": str})
    sched["date"] = pd.to_datetime(sched["date"]).dt.date
    boundary_service = fs.rebuild_boundary_service(pairs, extracted)
    tgt = matched[KEY].assign(date=matched["date"].dt.date)
    finputs = fs.forecast_inputs(tgt, sched, boundary_service, pairs, captured)
    fi = finputs.merge(matched[KEY + ["scheduled_trips", "scheduled_service_hours"]].assign(date=matched["date"].dt.date),
                       on=KEY, how="left", validate="one_to_one")
    fi["differs_from_descriptive"] = ~(
        (fi["forecast_scheduled_trips"].astype("Float64") == fi["scheduled_trips"].astype("Float64")).fillna(False)
        & ((fi["forecast_scheduled_service_hours"].astype("Float64") - fi["scheduled_service_hours"].astype("Float64"))
           .abs() < 1e-6).fillna(False))
    boundary_rows = []
    for _, p in pairs[pairs["boundary"]].iterrows():
        g = fi[fi["date"] == p["date"]]
        boundary_rows.append({
            "date": str(p["date"]), "descriptive archive": p["descriptive_snapshot"],
            "forecast archive": p["forecast_snapshot"] or "none (no earlier archive)",
            "matched rows": len(g), "available": int((g["forecast_schedule_status"] == "available").sum()),
            "trip diffs": int(((g["forecast_scheduled_trips"].astype("Float64") != g["scheduled_trips"].astype("Float64"))
                               & g["forecast_scheduled_trips"].notna()).sum()),
            "hours diffs": int((((g["forecast_scheduled_service_hours"].astype("Float64")
                                  - g["scheduled_service_hours"].astype("Float64")).abs() > 1e-6)
                                & g["forecast_scheduled_service_hours"].notna()).sum()),
            "status": ", ".join(f"{k} {v}" for k, v in g["forecast_schedule_status"].value_counts().items())})
    boundary_table = pd.DataFrame(boundary_rows)

    # ---------------------------------------------------------------- missing-history classification (matched)
    print("classifying missing history ...", flush=True)
    crosswalks = {}
    for sid, ext in extracted.items():
        con, _ = open_snapshot(ext)
        crosswalks[sid] = set(bus_crosswalk(con, sid)["route"])
        con.close()
    sched_keys = set(zip(sched["route"], sched["date"]))
    classes = {}
    for k in [1, 28]:
        col = LAG_EXPORT[k]
        miss = matched[matched[col].isna()]
        ctx = [classify_missing_lag(r, (d - pd.Timedelta(days=k)).date(),
                                    select_snapshot((d - pd.Timedelta(days=k)).date(), archives), sched_keys, crosswalks)
               for r, d in zip(miss["route"], miss["date"])]
        classes[k] = {"total": len(miss), "by_context": pd.Series(ctx, dtype="string").value_counts().to_dict(),
                      "by_route": miss["route"].value_counts().to_dict(),
                      "by_split": miss["split"].value_counts().to_dict()}

    # ---------------------------------------------------------------- Step 23: policies
    print("applying Option 1 / Option 2 ...", flush=True)
    prep = {
        ("demand", p): prepare(daily, p, set(holidays), with_schedule=False) for p in ["option_1", "option_2"]}
    for p in ["option_1", "option_2"]:
        prep[("matched", p)] = prepare(matched, p, set(holidays), with_schedule=True)
        mf = matched.merge(fi[KEY + fs.FORECAST_COLS].assign(date=pd.to_datetime(fi["date"])), on=KEY, how="left",
                           validate="one_to_one")
        prep[("matched_forecast_schedule", p)] = prepare(
            mf, p, set(holidays), with_schedule=True,
            schedule_cols=("forecast_scheduled_trips", "forecast_scheduled_service_hours"))
    withheld = {f"{t}/{p}": withheld_counts(df) for (t, p), df in prep.items()}

    def elig_table(t):
        o1, o2 = prep[(t, "option_1")], prep[(t, "option_2")]
        out = pd.DataFrame({"route": o1["route"], "date": o1["date"], "split": o1["split"],
                            "eligible_option_1": o1["eligible"], "withheld_reason_option_1": o1["withheld_reason"],
                            "eligible_option_2": o2["eligible"], "withheld_reason_option_2": o2["withheld_reason"],
                            "rides_28_days_before_option_2": o2["rides_28_days_before"].round(6),
                            "rides_28_days_before_available": o2["rides_28_days_before_available"]})
        if t == "matched":
            fo = prep[("matched_forecast_schedule", "option_2")]
            out["eligible_option_2_forecast_schedule"] = fo["eligible"].values
            out["withheld_reason_option_2_forecast_schedule"] = fo["withheld_reason"].values
        return out
    elig_demand, elig_matched = elig_table("demand"), elig_table("matched")

    special = []
    for route in ["10", "130"]:
        for p in ["option_1", "option_2"]:
            g = prep[("matched", p)][prep[("matched", p)]["route"] == route]
            special.append({"route": route, "policy": p, "matched rows": len(g),
                            "splits": ", ".join(sorted(g["split"].unique())),
                            "eligible": int(g["eligible"].sum()), "withheld": int((~g["eligible"]).sum()),
                            "missing 28-day lag": int(g["rides_28_days_before"].isna().sum()) if p == "option_1"
                            else int((g["rides_28_days_before_available"] == 0).sum())})

    # ---------------------------------------------------------------- holiday predictor vs reported daytype
    dd = daily.assign(calendar_value=sunday_holiday_service_day(daily["date"], set(holidays)))
    per_date = dd.groupby("date").agg(calendar_value=("calendar_value", "first"),
                                      reported_U=("daytype", lambda s: int((s == "U").sum())),
                                      reported_other=("daytype", lambda s: int((s != "U").sum())),
                                      daytypes=("daytype", lambda s: ",".join(f"{k}:{v}" for k, v in s.value_counts().items())))
    disagree = per_date[((per_date["calendar_value"] == 1) & (per_date["reported_other"] > 0))
                        | ((per_date["calendar_value"] == 0) & (per_date["reported_U"] > 0))].reset_index()
    disagree_table = pd.DataFrame({
        "date": iso(disagree["date"]), "weekday": pd.to_datetime(disagree["date"]).dt.day_name(),
        "calendar says Sunday/holiday": disagree["calendar_value"],
        "holiday in list": [holidays.get(d.date(), "") for d in pd.to_datetime(disagree["date"])],
        "reported daytypes (route counts)": disagree["daytypes"]})
    row_disagree = int((dd["calendar_value"] != dd["is_sunday_holiday_daytype"]).sum())

    # ---------------------------------------------------------------- reference comparisons
    C = [compare("daily_forecasting_features rows", ref["daily_forecasting_features_rows"], len(daily), "9.3.3"),
         compare("daily_forecasting_features columns", 16, len(daily.columns), "9.9.1"),
         compare("expanded_demand_service_features columns", 22, len(matched.columns), "9.9.2")]
    for s in SPLITS:
        C.append(compare(f"demand-only {s} rows", ref["demand_only_split_rows"][s], int((daily["split"] == s).sum()), "9.10.3"))
    for s in SPLITS:
        C.append(compare(f"matched {s} rows", ref["matched_split_rows"][s], int((matched["split"] == s).sum()), "9.10.3"))
    we = ref["worked_example"]
    wrow = daily[(daily["route"] == we["route"]) & (daily["date"] == pd.Timestamp(we["date"]))]
    for k in ["rides", "day_of_week", *LAG_EXPORT.values(), "seasonal_lag_observations", "past_four_same_weekdays_mean"]:
        got = wrow.iloc[0][k] if len(wrow) else "row missing"
        got = None if (not isinstance(got, str) and pd.isna(got)) else (got if isinstance(got, str) else
                                                                       (int(got) if float(got).is_integer() else float(got)))
        C.append(compare(f"worked example route 1 2024-08-01: {k}", we[k], got, "9.9.3"))
    C.append(compare("matched rows missing 28-day lag", ref["matched_missing_lag_28d"], classes[28]["total"], "9.6.4.3"))
    for ctx_name, n in ref["matched_missing_lag_28d_by_context"].items():
        C.append(compare(f"missing 28-day lag, lag-date context: {ctx_name}", n,
                         int(classes[28]["by_context"].get(ctx_name, 0)), "9.6.4.3"))
    for route, n in ref["matched_missing_lag_28d_by_route"].items():
        C.append(compare(f"missing 28-day lag, route {route}", n, int(classes[28]["by_route"].get(route, 0)), "9.6.4.3"))
        C.append(compare(f"matched rows, route {route}", ref["matched_rows_by_route"][route],
                         int((matched["route"] == route).sum()), "9.6.4.3"))
    C.append(compare("matched rows missing 1-day lag", ref["matched_missing_lag_1d"], classes[1]["total"], "9.6.4.3"))
    act1 = int(classes[1]["by_context"].get("active_service_no_passenger_record", 0))
    C.append(compare("missing 1-day lag: active scheduled service, no passenger record",
                     ref["matched_missing_lag_1d_by_context"]["active_service_no_passenger_record"], act1, "9.6.4.3"))
    C.append(compare("missing 1-day lag: no active trips on lag date (all other contexts)",
                     ref["matched_missing_lag_1d_by_context"]["no_active_trips_on_lag_date"],
                     classes[1]["total"] - act1, "9.6.4.3"))
    for p, key in [("option_1", "option_1_withheld_by_split"), ("option_2", "option_2_withheld_by_split")]:
        for s in SPLITS:
            C.append(compare(f"{p} withheld, matched {s}", ref[key][s], withheld[f"matched/{p}"][s], "9.10.2"))
    C.append(compare("option_1 withheld, matched total", ref["option_1_withheld_total"],
                     sum(withheld["matched/option_1"].values()), "9.10.2"))
    C.append(compare("option_2 extra eligible test rows vs option_1", ref["option_2_extra_eligible_test_rows"],
                     withheld["matched/option_1"]["test"] - withheld["matched/option_2"]["test"], "9.10.2"))
    for name, df in [("demand-only", daily), ("matched", matched)]:
        C.append(compare(f"{name}: dates shared between splits", 0, sum(date_overlap(df).values()), "9.10.3"))
    C.append(compare("matched: service_date equals date", True, bool((matched["service_date"] == matched["date"]).all()), "9.9.2"))
    on_boundary = matched["date"].dt.date.isin(set(pairs.loc[pairs["boundary"], "date"]))
    not_usable = matched["archive_available_from"] > matched["date"]
    C.append(compare("matched: descriptive archive unusable for forecasting exactly on boundary dates", True,
                     bool((on_boundary == not_usable).all()), "9.14.3"))
    fa = finputs[finputs["forecast_snapshot"].notna()]
    C.append(compare("forecast inputs: every archive captured strictly before target date", True,
                     bool((pd.to_datetime(fa["forecast_snapshot"].map(captured)) < pd.to_datetime(fa["date"])).all()), "9.14.3"))
    n_mis = sum(c["result"] == "MISMATCH" for c in C)

    # ---------------------------------------------------------------- write outputs
    vdir = s2_dir / f"features__delay{delay}d"
    vdir.mkdir(parents=True, exist_ok=True)
    outputs: dict = {}
    write_csv(daily, vdir / D, outputs)
    write_csv(matched, vdir / M, outputs)
    write_csv(fi[KEY + ["boundary"] + fs.FORECAST_COLS + ["differs_from_descriptive"]], vdir / "forecast_schedule_inputs.csv", outputs)
    write_csv(elig_demand, vdir / "policy_eligibility_demand.csv", outputs)
    write_csv(elig_matched, vdir / "policy_eligibility_matched.csv", outputs)
    absence = pd.concat([lag_absence_table("demand_only", daily), lag_absence_table("matched", matched)], ignore_index=True)
    write_csv(absence, vdir / "lag_absence_by_route_split.csv", outputs)

    settings = {k: fcfg[k] for k in ["timezone", "issue_time", "reporting_delay_days", "archive_availability_policy",
                                     "lags_days", "seasonal_lags_days", "seasonal_min_observations", "target_window",
                                     "splits", "selected_policy", "comparison_policy"]}
    settings["latest_permitted_ridership_date"] = f"target date - {delay} day(s)"
    settings["sunday_service_holidays"] = fcfg["sunday_service_holidays"]["dates"]
    settings["holiday_observance_rule"] = observance_rule
    settings["observed_holiday_dates"] = {d.isoformat(): n for d, n in sorted(holidays.items())}
    fingerprints = {"ridership": {rid["snapshot_id"]: s2["input_fingerprints"][rid["snapshot_id"]]},
                    "stage2_manifest_sha256": sha256(s2_manifest_path),
                    "stage2_outputs": {k: v["sha256"] for k, v in s2["outputs"].items()},
                    "gtfs": {k: v for k, v in s2["input_fingerprints"].items() if k != rid["snapshot_id"]}}
    schema = build_schema(fcfg["schema_version"], settings, f"{s2_version}/features__delay{delay}d", fingerprints)
    (vdir / "feature_schema.json").write_text(json.dumps(schema, indent=2, default=str), encoding="utf-8")
    commit = git_commit()
    manifest = {"data_version": f"{s2_version}/features__delay{delay}d", "stage2_data_version": s2_version,
                "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "code": "analytics/features/build_stage3.py", "git_commit": commit, "spec_version": "3.8",
                "schema_version": fcfg["schema_version"], "settings": settings, "input_fingerprints": fingerprints,
                "outputs": outputs, "withheld": withheld, "missing_history": classes}
    (vdir / "features_manifest.json").write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")

    # ---------------------------------------------------------------- report
    def counts_table():
        rows = []
        for (t, p), df in prep.items():
            for s in SPLITS:
                g = df[df["split"] == s]
                rows.append({"table": t, "policy": p, "split": s, "target rows": len(g),
                             "eligible": int(g["eligible"].sum()), "withheld": int((~g["eligible"]).sum())})
        return pd.DataFrame(rows)

    def reasons_table():
        rows = []
        for (t, p), df in prep.items():
            r = df.loc[~df["eligible"], "withheld_reason"].str.split(";").explode().value_counts()
            rows += [{"table": t, "policy": p, "reason": k, "rows": int(v)} for k, v in r.items()]
        return pd.DataFrame(rows)

    lag_missing = pd.DataFrame([{"table": n, "split": s, **{c: int(df.loc[df["split"] == s, c].isna().sum())
                                                            for c in LAG_EXPORT.values()},
                                 "seasonal mean missing": int(df.loc[df["split"] == s, "past_four_same_weekdays_mean"].isna().sum())}
                                for n, df in [("demand-only", daily), ("matched", matched)] for s in SPLITS])
    ctx_table = pd.DataFrame([{"lag": f"{k}-day", "context of the earlier lag date": c, "matched target rows": int(v)}
                              for k in [28, 1] for c, v in classes[k]["by_context"].items()])
    L = ["# Stage 3 quality report: feature contracts", "",
         f"Generated {datetime.now(timezone.utc).isoformat(timespec='seconds')} by `analytics/features/build_stage3.py` "
         "(spec v3.8, sections 9.9, 9.10.2-9.10.4, 9.14.3). No model is trained in this stage.", "",
         f"- Data version: `{s2_version}/features__delay{delay}d` (built on Stage 2 version `{s2_version}`)",
         f"- Code version: git `{commit}`; feature schema version {fcfg['schema_version']}",
         f"- Issue time: {fcfg['issue_time']}; **assumed reporting delay: {delay} day(s)** (configurable in "
         "`analytics/config/features.json`; an assumption for the retrospective replay, not a verified feed capability)",
         f"- Reference comparisons: **{len(C) - n_mis} MATCH, {n_mis} MISMATCH**", "",
         "> Reference counts are compared, never forced (spec 9.22.2). Absent lag dates stay missing; recorded zeros "
         "stay zero; targets are never filled.", "",
         "## 1. Reference comparison", "", "| section | metric | spec | ours | result | difference |",
         "|---|---|---:|---:|---|---:|"]
    for c in C:
        L.append(f"| {c['section']} | {c['metric']} | {_fmt(c['spec'])} | {_fmt(c['ours'])} | **{c['result']}** | {c['difference']} |")
    L += ["", "## 2. Policy coverage before model fitting (Option 2 selected, Option 1 comparison)", "",
          "Matched rows use the descriptive Stage 2 schedule (the spec's reference construction). "
          "`matched_forecast_schedule` repeats the check with the forecast-input schedule (section 4).", "",
          *_table(counts_table()), "", "Withheld reasons (a row can have several):", "", *_table(reasons_table()), "",
          "Routes 10 and 130 (absent from schedule-augmented training; reported separately, spec 9.10.2):", "",
          *_table(pd.DataFrame(special)), "",
          "For option_2 the last column counts rows whose 28-day lag was filled (flag 0).", "",
          "## 3. Missing history", "", "Missing lags by table and split (before any filling):", "",
          *_table(lag_missing), "",
          "Schedule context of the earlier lag date, for matched target rows (spec 9.6.4.3):", "", *_table(ctx_table), "",
          "Per route/split/lag counts: `lag_absence_by_route_split.csv`.", "",
          "## 4. Forecast-input schedule selection (spec 9.14.3)", "",
          "Descriptive (Stage 2, unchanged): latest archive captured on/before D. Forecast input: latest archive captured "
          "**strictly before** D (only capture dates are known). The two differ only on capture dates; on those dates the "
          "forecast schedule is rebuilt from the earlier archive.", "",
          *_table(boundary_table), "",
          f"Matched rows whose forecast-input schedule differs from the descriptive one: "
          f"{int(fi['differs_from_descriptive'].sum())}. Rows with no forecast schedule available: "
          f"{int((fi['forecast_schedule_status'] != 'available').sum())} "
          f"({', '.join(f'{k} {v}' for k, v in fi['forecast_schedule_status'].value_counts().items())}).", "",
          "## 5. Issue-time Sunday/holiday predictor vs reported daytype", "",
          f"`is_sunday_holiday_service_day` = Sunday or an observed date of the fixed holiday list "
          f"({len(holidays)} dates in `features.json`, observance rule `{observance_rule}`: a Saturday holiday is "
          "observed on the Friday before, a Sunday holiday on the Monday after). It never reads the target-date "
          "ridership row. "
          f"Rows where it differs from the reported `is_sunday_holiday_daytype`: **{row_disagree:,}** of {len(dd):,}. "
          f"Dates with any disagreement: **{len(disagree_table)}**:", "",
          *(_table(disagree_table) if len(disagree_table) else ["(none)"]), "",
          "## Outputs", "", "| file | rows | columns | sha256 (first 16) |", "|---|---:|---:|---|"]
    for name, o in outputs.items():
        L.append(f"| `{name}` | {o['rows']:,} | {o['columns']} | `{o['sha256'][:16]}` |")
    L += ["| `feature_schema.json` | | | |", ""]
    if n_mis:
        L += ["## Mismatches", ""] + [f"- **{c['metric']}**: spec {_fmt(c['spec'])}, ours {_fmt(c['ours'])} ({c['difference']})"
                                      for c in C if c["result"] == "MISMATCH"] + [""]
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "stage3_quality_report.md").write_text("\n".join(L), encoding="utf-8")
    (args.out / "stage3_quality_checks.json").write_text(json.dumps(
        {"data_version": manifest["data_version"], "comparisons": C, "withheld": withheld, "missing_history": classes,
         "boundary_dates": boundary_rows, "holiday_disagreements": disagree_table.to_dict("records"),
         "holiday_row_disagreements": row_disagree, "special_routes": special}, indent=2, default=str), encoding="utf-8")
    print(f"done: {len(C) - n_mis} MATCH, {n_mis} MISMATCH -> {args.out / 'stage3_quality_report.md'}")
    for c in C:
        if c["result"] == "MISMATCH":
            print(f"  MISMATCH {c['metric']}: spec {c['spec']} ours {c['ours']}")


if __name__ == "__main__":
    main()
