"""Stage 5 orchestrator: route groups and ranking (spec 9.7, 9.11, 9.12; stage table 9.18).

Order (each step stops the build if its check fails):
  1. verify inputs: Stage 2 tables (sha in the Stage 3 manifest), Stage 3 feature rows, raw GTFS archives
  2. rankings for every ranking period + gate sensitivity; identities against the matched table
  3. clustering profiles on the development period; features chosen by the fixed rules
  4. k table; k by the fixed rule; fit on development profiles only
  5. FREEZE route_groups.joblib (compress 3, < 20 MB), reload, require identical labels
  6. names applied only if the frozen memberships equal analytics/config/group_names.json exactly
  7. membership for every route in the ridership window; summaries and centroids in original units
  8. stop coverage/overlap for all 8 archives (applied dates checked against sources.json)
  9. the mentor notebook's rules recomputed for comparison (reads only)
 10. data products, report, checks and manifest

Archives are verified as in Stage 2: the registered ZIP's sha256 is checked, then its extracted/ folder is read.

Usage (CMD, from the repo root):
    python -I analytics\\groups\\build_stage5.py --features data\\processed\\cta_ref__r20261113__gtfs8__to20260731\\features__delay1d --groups analytics\\config\\groups.json --names analytics\\config\\group_names.json --sources analytics\\config\\sources.json --register data\\raw\\source_register.csv --artifacts artifacts\\stage5 --out reports
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
from datetime import date  # noqa: E402
from importlib.metadata import version as package_version  # noqa: E402

import joblib  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from analytics.groups import clustering as C  # noqa: E402
from analytics.groups.notebook_compare import compare  # noqa: E402
from analytics.groups.overlap import coverage, overlap, verify, version_tables  # noqa: E402
from analytics.groups.profiles import (all_ranking_periods, gate_sensitivity, load_matched,  # noqa: E402
                                       load_schedule, route_profiles, select_features)
from analytics.groups.report5 import write_report  # noqa: E402
from analytics.models.train_stage4a import dump_info, load_feature_rows, now  # noqa: E402
from analytics.reconstruction.build_stage2 import git_commit, sha256  # noqa: E402
from analytics.reconstruction.gtfs_tables import open_snapshot  # noqa: E402
from analytics.reconstruction.snapshot_select import applied_ranges, selection_table  # noqa: E402

MAX_BYTES = 20_000_000  # the same 20 MB limit as the Stage 4 model files
STAGE2_TABLES = ["expanded_matched_utilization.csv", "expanded_scheduled_route_day_service.csv",
                 "expanded_ridership_without_schedule.csv"]


def write_csv(df: pd.DataFrame, path: Path) -> dict:
    df.to_csv(path, index=False, float_format="%.10g", lineterminator="\n", date_format="%Y-%m-%d")
    return {"rows": int(len(df)), "columns": int(len(df.columns)), "sha256": sha256(path)}


def verify_stage2(features_dir: Path, fmanifest: dict) -> Path:
    s2 = features_dir.parent
    recorded = fmanifest["input_fingerprints"]["stage2_outputs"]
    for name in STAGE2_TABLES:
        if sha256(s2 / name) != recorded[name]:
            raise SystemExit(f"{name} changed since Stage 3 recorded it; rebuild Stages 2-3")
    return s2


def ranking_identities(matched: pd.DataFrame, ranking: pd.DataFrame, cfg: dict) -> dict:
    out = {}
    for name, (a, b) in cfg["periods"]["ranking_periods"].items():
        mm = matched[matched["date"].between(a, b) & matched["daytype"].isin(["W", "A", "U"])]
        r = ranking[ranking["period_name"] == name]
        out[name] = {"rides": int(r["rides_sum"].sum()) == int(mm["rides"].sum()),
                     "trips": int(r["scheduled_trips_sum"].sum()) == int(mm["scheduled_trips"].sum()),
                     "days": int(r["observed_days"].sum()) == len(mm),
                     "three day types per route": bool(r.groupby("route")["daytype"].nunique().eq(3).all()),
                     "no rank on an ineligible row": bool(all(r.loc[~r[f"{v}_eligible"], v].isna().all() for v in
                                                              ["observed_daily_demand_rank", "rides_per_trip_rank",
                                                               "service_productivity_metric_rank"]))}
    if not all(all(v.values()) for v in out.values()):
        raise SystemExit(f"ranking identities failed: {out}")
    return out


def apply_names(labels: pd.Series, names: dict, k: int) -> dict:
    """Names attach only to exactly the memberships the user inspected."""
    if names["k"] != k:
        raise SystemExit(f"group_names.json was written for k = {names['k']}, the fixed rule chose k = {k}")
    for gid, g in names["groups"].items():
        frozen = set(labels[labels == int(gid)].index)
        if frozen != set(g["routes"]):
            raise SystemExit(f"group {gid}: frozen membership differs from group_names.json "
                             f"(only frozen {sorted(frozen - set(g['routes']))}, only named "
                             f"{sorted(set(g['routes']) - frozen)}); re-inspect before naming")
    return {int(gid): g["name"] for gid, g in names["groups"].items()}


def overlap_all(sources: dict, register: Path) -> dict:
    root = register.resolve().parent.parent.parent
    with open(register, newline="", encoding="utf-8") as f:
        reg = {r["snapshot_id"]: r for r in csv.DictReader(f)}
    archives_cfg = sources["gtfs"]["archives"]
    archives = [{"snapshot_id": a["snapshot_id"], "captured": date.fromisoformat(a["captured"])} for a in archives_cfg]
    start, end = (date.fromisoformat(x) for x in sources["stage2_reference"]["analysis_period"])
    sel = selection_table(start, end, archives)
    ranges = applied_ranges(sel)
    served, per_version = [], []
    for a in archives_cfg:
        sid = a["snapshot_id"]
        zip_path = root / reg[sid]["local_path"]
        if sha256(zip_path) != reg[sid]["sha256"]:
            raise SystemExit(f"{sid} changed since registration (raw files must be immutable)")
        applied_ok = [str(ranges[sid][0]), str(ranges[sid][1])] == a["applied_dates"]
        if not applied_ok:
            raise SystemExit(f"{sid}: applied dates {ranges[sid]} differ from sources.json {a['applied_dates']}")
        con, _ = open_snapshot(zip_path.parent / "extracted")
        t = version_tables(con, sid, sorted(sel.loc[sel["snapshot_id"] == sid, "date"]))
        con.close()
        served.append(t["served"])
        per_version.append({"geometry_version": sid, "applied_dates": "..".join(a["applied_dates"]),
                            "routes": int(len(t["coverage"])), "served stops": int(t["served"]["stop_id"].nunique()),
                            "sharing pairs": int(len(t["overlap"])),
                            "median exclusive share": float(t["coverage"]["exclusive_stop_fraction"].median()),
                            "identities hold": all(t["checks"].values())})
    allv = pd.concat(served, ignore_index=True)
    cov, ov = coverage(allv), overlap(allv)
    combined = verify(allv, cov, ov)
    return {"coverage": cov, "overlap": ov, "per_version": pd.DataFrame(per_version), "combined_checks": combined,
            "selection": sel}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for a in ["--features", "--groups", "--names", "--sources", "--register", "--artifacts", "--out"]:
        ap.add_argument(a, required=True, type=Path)
    args = ap.parse_args()
    cfg = json.loads(args.groups.read_text(encoding="utf-8"))
    names = json.loads(args.names.read_text(encoding="utf-8"))
    sources = json.loads(args.sources.read_text(encoding="utf-8"))
    seed = int(cfg["seed"])

    print("verifying inputs ...", flush=True)
    fr, fmanifest = load_feature_rows(args.features)
    s2 = verify_stage2(args.features, fmanifest)
    matched = load_matched(s2 / STAGE2_TABLES[0])
    schedule = load_schedule(s2 / STAGE2_TABLES[1], matched)
    rws = pd.read_csv(s2 / STAGE2_TABLES[2], dtype={"route": str}, parse_dates=["date"])

    print("rankings ...", flush=True)
    ranking = all_ranking_periods(matched, cfg, schedule)
    sensitivity = gate_sensitivity(matched, cfg, schedule)
    rank_ids = ranking_identities(matched, ranking, cfg)

    print("clustering profiles and features ...", flush=True)
    dev = cfg["periods"]["development"]
    prof = route_profiles(matched, schedule, dev[0], dev[1], cfg)
    sel = select_features(prof, cfg)
    feats = sel["selected"]
    base = prof[prof["base_eligible"].astype(bool)]
    frame = C.model_frame(base, feats, cfg)
    halves = []
    for a, b in cfg["periods"]["sensitivity_halves"]:
        hp = route_profiles(matched, schedule, a, b, cfg)
        halves.append(C.model_frame(hp[hp["base_eligible"].astype(bool)], feats, cfg))

    print("choosing the number of groups ...", flush=True)
    ktab = C.evaluate_k(frame, feats, cfg, halves)
    k = C.choose_k(ktab, cfg)
    if k is None:
        raise SystemExit("no group count passed the size gate; routes stay ungrouped (no artifact to freeze)")
    pipe = C.fit(frame, feats, k, seed, cfg)
    labels = pd.Series(pipe.named_steps["kmeans"].labels_, index=frame.index, name="group")

    print("freezing the pipeline ...", flush=True)
    art = args.artifacts
    art.mkdir(parents=True, exist_ok=True)
    file_info = dump_info(pipe, art / "route_groups.joblib", 3)
    file_info["under_limit"] = file_info["compressed_bytes"] < MAX_BYTES
    if not file_info["under_limit"]:
        raise SystemExit("route_groups.joblib is at or above 20 MB")
    reloaded = C.predict(joblib.load(art / "route_groups.joblib"), frame)
    reload_exact = bool(np.array_equal(reloaded, labels.to_numpy()))
    if not reload_exact:
        raise SystemExit("the reloaded pipeline does not reproduce the frozen memberships")
    group_names = apply_names(labels, names, k)

    print("memberships and summaries ...", flush=True)
    a, b = cfg["periods"]["ranking_periods"]["full_matched_window"]
    window_routes = set(matched.loc[matched["date"].between(a, b), "route"])
    rws_routes = set(rws.loc[rws["date"].between(a, b), "route"])
    mem = C.membership(prof, labels, sorted(window_routes | rws_routes), rws_routes - window_routes)
    mem["group_name"] = mem["group"].map(lambda g: group_names.get(int(g)) if g != "ungrouped" else np.nan)
    summary = C.group_summary(prof, labels, cfg)
    summary.insert(1, "name", summary["group"].map(group_names))
    centroids = C.centroids_original_units(pipe, feats, cfg)
    centroids.insert(1, "name", centroids["group"].map(group_names))
    imp = pipe.named_steps["impute"]
    imputation = [{"feature": f, "fitted median": imp.medians_[f], "naive median (all values)": float(frame[f].median()),
                   "filled routes": sorted(frame.index[frame[f].isna()])} for f in feats]

    print("stop coverage and overlap (8 archives) ...", flush=True)
    ovl = overlap_all(sources, args.register)
    default_version = ovl["selection"].loc[ovl["selection"]["date"] == date.fromisoformat(dev[1]), "snapshot_id"].item()

    print("notebook comparison (reads only) ...", flush=True)
    nb = compare(fr, prof, labels, feats, k, ranking[ranking["period_name"] == "development"], cfg)

    print("writing data products ...", flush=True)
    out_data = s2 / f"groups__dev{dev[0].replace('-', '')}_{dev[1].replace('-', '')}"
    out_data.mkdir(parents=True, exist_ok=True)
    outputs = {"expanded_utilization_profiles.csv": write_csv(ranking, out_data / "expanded_utilization_profiles.csv"),
               "route_profiles.csv": write_csv(prof, out_data / "route_profiles.csv"),
               "route_group_membership.csv": write_csv(mem, out_data / "route_group_membership.csv"),
               "route_stop_coverage.csv": write_csv(ovl["coverage"], out_data / "route_stop_coverage.csv"),
               "route_stop_overlap.csv": write_csv(ovl["overlap"], out_data / "route_stop_overlap.csv")}
    data_manifest = {"data_version": f"{s2.name}/{out_data.name}", "settings_sha256": sha256(args.groups),
                     "names_sha256": sha256(args.names), "outputs": outputs,
                     "inputs": {n: fmanifest["input_fingerprints"]["stage2_outputs"][n] for n in STAGE2_TABLES}}
    (out_data / "groups_data_manifest.json").write_text(json.dumps(data_manifest, indent=2), encoding="utf-8")

    runtime = {"python": platform.python_version(),
               **{p: package_version(p) for p in ["pandas", "numpy", "scikit-learn", "joblib", "duckdb", "threadpoolctl"]}}
    ctx = {"cfg": cfg, "names": names, "group_names": group_names, "ranking": ranking, "sensitivity": sensitivity,
           "rank_identities": rank_ids, "profiles": prof, "selection": sel, "features": feats, "k_table": ktab,
           "k": k, "labels": labels, "membership": mem, "summary": summary, "centroids": centroids,
           "imputation": imputation, "file_info": file_info, "reload_exact": reload_exact, "overlap": ovl,
           "default_version": default_version, "notebook": nb, "data_manifest": data_manifest,
           "out_data": out_data, "runtime": runtime, "git_commit": git_commit(), "built_at": now()}
    manifest = write_report(args.out, ctx)
    (art / "groups_manifest.json").write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    print(f"done -> {args.out / 'stage5_quality_report.md'}; data in {out_data}; artifact in {art}")


if __name__ == "__main__":
    main()
