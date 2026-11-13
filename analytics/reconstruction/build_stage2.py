"""Stage 2 orchestrator: daily reconstruction + exact matching (spec 9.5, 9.6.2-9.6.5, 9.8).

Writes to data/processed/<data_version>/:
    expanded_scheduled_route_day_service.csv
    expanded_matched_utilization.csv
    expanded_ridership_without_schedule.csv
    expanded_schedule_without_ridership.csv
    manifest.json   (source IDs + sha256, date boundaries, parameters, row counts, output hashes)
and to --out (reports/): stage2_quality_report.md, stage2_quality_checks.json

Usage (CMD, from the repo root):
    python -I analytics\\reconstruction\\build_stage2.py --config analytics\\config\\sources.json --register data\\raw\\source_register.csv --out reports
"""
from __future__ import annotations

import sys
from pathlib import Path

# `python -I` does not put the script's folder on sys.path; add the repo root (our own code, not a data folder).
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import argparse  # noqa: E402
import csv  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import subprocess  # noqa: E402
from datetime import date, datetime, timedelta, timezone  # noqa: E402

import pandas as pd  # noqa: E402

from analytics.reconstruction import regime_checks as rc  # noqa: E402
from analytics.reconstruction.daily_service import (build_trip_durations, bus_trips_per_date,  # noqa: E402
                                                    daily_service, invalid_duration_summary)
from analytics.reconstruction.gtfs_tables import bus_crosswalk, open_snapshot  # noqa: E402
from analytics.reconstruction.matching import load_ridership, match, per_route, reconciliation  # noqa: E402
from analytics.reconstruction.report import compare, write_report  # noqa: E402
from analytics.reconstruction.service_calendar import (active_service_dates, load_calendar,  # noqa: E402
                                                       load_calendar_dates)
from analytics.reconstruction.snapshot_select import applied_ranges, date_range, selection_table  # noqa: E402

OVERLAP_PROBE_DAYS = 7  # one week covers W, A and U day types
OUTPUT_FILES = {
    "schedule": "expanded_scheduled_route_day_service.csv",
    "matched": "expanded_matched_utilization.csv",
    "ridership_without_schedule": "expanded_ridership_without_schedule.csv",
    "schedule_without_ridership": "expanded_schedule_without_ridership.csv",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while block := f.read(1 << 20):
            h.update(block)
    return h.hexdigest()


def git_commit() -> str:
    try:
        out = subprocess.run(["git", "-C", str(REPO_ROOT), "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "-C", str(REPO_ROOT), "status", "--porcelain"],
                               capture_output=True, text=True, check=True).stdout.strip()
        return out + ("+uncommitted" if dirty else "")
    except Exception:  # noqa: BLE001
        return "unknown"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True, type=Path)
    ap.add_argument("--register", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    cfg = json.loads(args.config.read_text(encoding="utf-8"))
    ref = cfg["stage2_reference"]
    root = args.register.resolve().parent.parent.parent
    start, end = (date.fromisoformat(x) for x in ref["analysis_period"])

    # ---------------------------------------------------------------- sources (verify bytes before use)
    with open(args.register, newline="", encoding="utf-8") as f:
        register = list(csv.DictReader(f))
    rid = [r for r in register if r["dataset_id"] == cfg["ridership"]["dataset_id"] and r["is_primary"] == "True"]
    if len(rid) != 1:
        raise SystemExit(f"expected exactly one primary ridership export in the register, found {len(rid)}")
    rid = rid[0]
    gtfs_reg = {r["snapshot_id"]: r for r in register if r["dataset_id"] == cfg["gtfs"]["dataset_id"]}
    archives_cfg = sorted(cfg["gtfs"]["archives"], key=lambda a: a["captured"])
    ids = [a["snapshot_id"] for a in archives_cfg]
    if len(set(ids)) != 8 or not set(ids) <= gtfs_reg.keys():
        raise SystemExit(f"need 8 unique registered archives from the manifest; have {sorted(set(ids) & gtfs_reg.keys())}")

    sources = []
    for r, used in [(rid, "rides")] + [(gtfs_reg[i], "schedule") for i in ids]:
        print(f"verifying sha256 of {r['snapshot_id']} ...", flush=True)
        actual = sha256(root / r["local_path"])
        if actual != r["sha256"]:
            raise SystemExit(f"{r['local_path']} changed since registration (raw files must be immutable)")
        sources.append({"dataset_id": r["dataset_id"], "snapshot_id": r["snapshot_id"], "sha256": actual,
                        "local_path": r["local_path"], "fingerprint_match": r["fingerprint_match"] == "True",
                        "used_for": used})

    data_version = f"cta_ref__r{rid['snapshot_id'][-8:]}__gtfs{len(ids)}__to{end:%Y%m%d}"
    vdir = root / "data" / "processed" / data_version
    input_fp = {s["snapshot_id"]: s["sha256"] for s in sources}
    if (vdir / "manifest.json").exists():
        old = json.loads((vdir / "manifest.json").read_text(encoding="utf-8"))
        if old.get("input_fingerprints") != input_fp:
            raise SystemExit(f"{vdir} exists with different inputs; a changed source needs a new data version")

    # ---------------------------------------------------------------- snapshot selection
    archives = [{"snapshot_id": a["snapshot_id"], "captured": date.fromisoformat(a["captured"])} for a in archives_cfg]
    selection = selection_table(start, end, archives)
    ranges = applied_ranges(selection)

    # ---------------------------------------------------------------- per-snapshot reconstruction
    applied_parts, probes, probe_dates, crosswalks, fingerprints, regimes, invalid = [], {}, {}, {}, {}, {}, {}
    gaps = []
    for i, a in enumerate(archives_cfg):
        sid = a["snapshot_id"]
        print(f"reconstructing {sid} ...", flush=True)
        con, _ = open_snapshot(root / Path(gtfs_reg[sid]["local_path"]).parent / "extracted")
        cw = bus_crosswalk(con, sid)
        crosswalks[sid] = set(cw["route"])
        build_trip_durations(con)
        fingerprints[sid] = rc.bus_payload_fingerprint(con)
        regimes[sid] = rc.bus_calendar_regimes(con)

        applied = sorted(selection.loc[selection["snapshot_id"] == sid, "date"])
        probe = []
        if i + 1 < len(archives_cfg):  # the next archive's first week, for the same-date overlap check
            nxt = date.fromisoformat(archives_cfg[i + 1]["captured"])
            probe = [d for d in date_range(nxt, nxt + timedelta(days=OVERLAP_PROBE_DAYS - 1)) if d <= end]
        cal, cd = load_calendar(con), load_calendar_dates(con)
        ds = daily_service(con, sid, active_service_dates(cal, cd, applied + probe))
        per_date = bus_trips_per_date(con)
        invalid[sid] = invalid_duration_summary(con)
        con.close()

        applied_ds = ds[ds["date"].isin(applied)]
        probes[sid] = ds[ds["date"].isin(probe)]
        probe_dates[sid] = probe
        active_dates = set(per_date.loc[per_date["date"].isin(applied), "date"])
        gaps += [{"date": str(d), "snapshot_id": sid, "reason": "selected snapshot defines no bus service"}
                 for d in applied if d not in active_dates]
        applied_parts.append(applied_ds)
    gaps += [{"date": str(d), "snapshot_id": None, "reason": "no archive captured on/before date"}
             for d in selection.loc[selection["snapshot_id"].isna(), "date"]]

    schedule = pd.concat(applied_parts, ignore_index=True).sort_values(["route", "date"]).reset_index(drop=True)
    routes_any = set().union(*crosswalks.values())

    # ---------------------------------------------------------------- ridership + matching
    print("matching with ridership ...", flush=True)
    rides_all, rinfo = load_ridership(root / rid["local_path"])
    after = rides_all[rides_all["date"] > end]
    rides_all = rides_all[rides_all["date"] <= end]  # rows dated on/before the cutoff only
    rides = rides_all[rides_all["date"] >= start].reset_index(drop=True)
    res = match(schedule, rides, selection, crosswalks, routes_any)
    rec = reconciliation(res, schedule, rides)
    rws_by_route = per_route(res["ridership_without_schedule"], with_rides=True)
    swr_by_route = per_route(res["schedule_without_ridership"], with_rides=False)

    # ---------------------------------------------------------------- 9.6.5 regime / integrity checks
    by_id = {a["snapshot_id"]: a for a in archives_cfg}
    jan, feb, apr, may = (next(s for s in ids if s.startswith(f"mdb-389-2026{m}")) for m in ["01", "02", "04", "05"])
    jf_same = (fingerprints[jan]["bus_trips_hash"] == fingerprints[feb]["bus_trips_hash"]
               and fingerprints[jan]["bus_stop_events_hash"] == fingerprints[feb]["bus_stop_events_hash"])
    ratio = fingerprints[apr]["bus_stop_events"] / fingerprints[may]["bus_stop_events"]
    zip_bytes_differ = gtfs_reg[jan]["sha256"] != gtfs_reg[feb]["sha256"]
    overlaps = []
    for older, newer in zip(ids, ids[1:]):
        nds = schedule[schedule["snapshot_id"] == newer]
        o = rc.compare_overlap(probes[older], nds, older, newer, probe_dates[older])
        o["newer_only_regime_starts"] = rc.newer_only_regime_starts(regimes[older], regimes[newer])
        o["explanation"] = rc.explain_overlap(o, o["newer_only_regime_starts"])
        overlaps.append(o)
    unexplained = [o for o in overlaps if o["explanation"].startswith("UNEXPLAINED")]
    overlap_table = pd.DataFrame([{
        "older": o["older"], "newer": o["newer"], "dates both define": len(o["dates_both_define_service"]),
        "route/dates compared": o["route_dates_compared"], "only older": o["route_dates_only_older"],
        "only newer": o["route_dates_only_newer"], "trip-count diffs": o["trip_count_differences"],
        "hours diffs": o["hours_differences"], "explanation": o["explanation"]} for o in overlaps])
    regime_table = pd.DataFrame([{"snapshot": sid, "start_date": r["start_date"], "end_date": r["end_date"],
                                  "services": r["services"], "bus trips": r["bus_trips"]}
                                 for sid in ids for r in regimes[sid]])
    regime_lines = [
        f"Jan 8 vs Feb 10: ZIP bytes differ = {zip_bytes_differ}; bus trip records and bus stop events identical = "
        f"**{jf_same}** (bus stop events {fingerprints[jan]['bus_stop_events']:,} vs {fingerprints[feb]['bus_stop_events']:,}; "
        "spec 2,859,229 each).",
        f"April 24 / May 30 bus stop events = {fingerprints[apr]['bus_stop_events']:,} / "
        f"{fingerprints[may]['bus_stop_events']:,} = {ratio:.3f} (spec: approximately half). "
        "Calendar-selected daily counts are kept; smaller feeds are not doubled.",
        "Archives with more than one disjoint bus calendar regime (outgoing + incoming timetables): "
        + (", ".join(f"{sid} ({len(regimes[sid])})" for sid in ids
                     if len(regimes[sid]) > 1 and rc.regimes_disjoint(regimes[sid])) or "none"),
        f"Same-date overlap comparisons with common dates: {sum(1 for o in overlaps if o['route_dates_compared'] > 0)}; "
        f"with no differences: {sum(1 for o in overlaps if o['explanation'] == 'no differences')}; "
        f"with differences confined to a timetable present only in the newer archive: "
        f"{sum(1 for o in overlaps if o['explanation'].startswith('differences only'))}; "
        f"**unexplained: {len(unexplained)}**. The spec reports five comparisons with no differences; it does not "
        "list which pairs/dates, so this is reported side by side rather than as a pass/fail.",
    ]

    # ---------------------------------------------------------------- descriptive summaries
    rw_start, rw_end = (date.fromisoformat(x) for x in ref["recent_window"])
    recent = rc.window_summary(rides_all, rw_start, rw_end)
    r1001 = rc.route_window(rides_all, "1001", rw_start, rw_end)
    presence = rc.route_name_presence(rides_all, rw_start, rw_end, routes_any)
    record_days = rc.monthly_record_days(rides_all, ["10", "130"], 2026, list(range(1, 8)))
    monthly = rc.monthly_coverage(rides)
    first_active = schedule.groupby("route")["date"].min()

    # ---------------------------------------------------------------- reference comparisons
    C = []
    for k, sec in [("schedule_records", "9.3.3"), ("matched", "9.6.4"), ("ridership_without_schedule", "9.6.4.1"),
                   ("schedule_without_ridership", "9.6.4.1"), ("ridership_observations", "9.6.4.1"),
                   ("matched_dates", "9.3.3"), ("matched_routes", "9.3.3"),
                   ("schedule_conditioned_coverage_pct", "9.6.4.3"),
                   ("routes_with_records_on_every_scheduled_date", "9.6.4.3")]:
        C.append(compare(k, ref[k], rec[k], sec))
    C.append(compare("identity: observations = matched + without schedule", True, rec["identity_ridership_holds"], "9.6.4.1"))
    C.append(compare("identity: schedule = matched + without rides", True, rec["identity_schedule_holds"], "9.6.4.1"))
    rws_idx = rws_by_route.set_index("route")
    for route, e in ref["ridership_without_schedule_by_route"].items():
        got = rws_idx.loc[route] if route in rws_idx.index else None
        C.append(compare(f"rides w/o service, route {route}: records", e["records"],
                         int(got["records"]) if got is not None else 0, "9.6.4.1"))
        C.append(compare(f"rides w/o service, route {route}: rides", e["rides"],
                         int(got["rides"]) if got is not None else 0, "9.6.4.1"))
        C.append(compare(f"rides w/o service, route {route}: dates",
                         f"{e['first_date']} to {e['last_date']}",
                         f"{got['first_date']} to {got['last_date']}" if got is not None else None, "9.6.4.1"))
    extra_routes = sorted(set(rws_idx.index) - set(ref["ridership_without_schedule_by_route"]))
    C.append(compare("rides w/o service: routes not in spec list", [], extra_routes, "9.6.4.1"))
    swr_idx = swr_by_route.set_index("route")
    for route, e in ref["schedule_without_ridership_by_route"].items():
        got = swr_idx.loc[route] if route in swr_idx.index else None
        C.append(compare(f"schedule w/o rides, route {route}: records", e["records"],
                         int(got["records"]) if got is not None else 0, "9.6.4.1"))
        C.append(compare(f"schedule w/o rides, route {route}: dates", f"{e['first_date']} to {e['last_date']}",
                         f"{got['first_date']} to {got['last_date']}" if got is not None else None, "9.6.4.1"))
    C.append(compare("schedule w/o rides: routes not in spec list", [],
                     sorted(set(swr_idx.index) - set(ref["schedule_without_ridership_by_route"])), "9.6.4.1"))
    for k in ["records", "route_identifiers", "calendar_dates"]:
        C.append(compare(f"recent window {k}", ref["recent_window_summary"][k], recent[k], "9.6.4.3"))
    C.append(compare("route 1001 recent-window records", ref["route_1001_recent_window"]["records"], r1001["records"], "9.6.4.2"))
    C.append(compare("route 1001 recent-window rides", ref["route_1001_recent_window"]["rides"], r1001["rides"], "9.6.4.2"))
    C.append(compare("identifiers absent from all 8 archives", ref["identifiers_absent_from_all_archives_recent_window"],
                     presence["absent_identifiers"], "9.6.4.2"))
    for route, d in ref["first_active_schedule_date"].items():
        C.append(compare(f"route {route} first active schedule date", d,
                         str(first_active.get(route)) if route in first_active.index else None, "9.6.4.3"))
    rd = record_days.set_index("month")
    for route, months in ref["record_days_2026"].items():
        ours = {m: int(rd.loc[m, f"route_{route}_record_days"]) for m in months}
        C.append(compare(f"route {route} record days Jan-Jul 2026", list(months.values()), list(ours.values()), "9.6.4.3"))
    sel_ok = all([str(ranges[a["snapshot_id"]][0]), str(ranges[a["snapshot_id"]][1])] == a["applied_dates"]
                 for a in archives_cfg)
    C.append(compare("applied date ranges equal spec 9.4.2 for all 8 archives", True, sel_ok, "9.4.2"))
    C.append(compare("Jan 8 / Feb 10 bus stop events", [2859229, 2859229],
                     [fingerprints[jan]["bus_stop_events"], fingerprints[feb]["bus_stop_events"]], "9.6.5"))
    C.append(compare("Jan 8 / Feb 10 bus trips and stop events identical", True, jf_same, "9.6.5"))
    C.append(compare("selection gaps", 0, len(gaps), "9.6.3"))
    C.append(compare("overlap comparisons with unexplained differences", 0, len(unexplained), "9.6.5"))
    n_mis = sum(c["result"] == "MISMATCH" for c in C)

    # ---------------------------------------------------------------- write outputs
    vdir.mkdir(parents=True, exist_ok=True)
    frames = {"schedule": schedule, **res}
    outputs = {}
    for key, fname in OUTPUT_FILES.items():
        p = vdir / fname
        frames[key].to_csv(p, index=False, lineterminator="\n")
        outputs[fname] = {"rows": len(frames[key]), "sha256": sha256(p)}
    selection_summary = pd.DataFrame([{
        "snapshot": a["snapshot_id"], "captured": a["captured"],
        "applied from": str(ranges[a["snapshot_id"]][0]), "applied to": str(ranges[a["snapshot_id"]][1]),
        "spec applied": f"{a['applied_dates'][0]} to {a['applied_dates'][1]}",
        "dates": int((selection["snapshot_id"] == a["snapshot_id"]).sum()),
        "route/date rows": int((schedule["snapshot_id"] == a["snapshot_id"]).sum()),
        "bus routes": len(crosswalks[a["snapshot_id"]])} for a in archives_cfg])

    commit = git_commit()
    manifest = {
        "data_version": data_version, "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "code": "analytics/reconstruction/build_stage2.py", "git_commit": commit, "spec_version": "3.8",
        "analysis_period": [str(start), str(end)], "ridership_cutoff": str(end),
        "parameters": {"bus_route_type": "3", "route_normalization": "strip surrounding whitespace; exact, case-sensitive",
                       "snapshot_rule": "latest captured on/before date; one whole snapshot per date; no per-route fallback",
                       "hours_rule": "sum(valid durations)/3600, missing unless every active trip duration is valid",
                       "overlap_probe_days": OVERLAP_PROBE_DAYS},
        "input_fingerprints": input_fp,
        "sources": [{**s, **({"captured": by_id[s["snapshot_id"]]["captured"],
                              "applied": [str(x) for x in ranges[s["snapshot_id"]]]} if s["snapshot_id"] in by_id else
                             {"source_last_updated": rid["source_last_updated"]})} for s in sources],
        "outputs": outputs, "reconciliation": rec, "gaps": gaps,
    }
    (vdir / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")

    ctx = {
        "data_version": data_version, "period": [str(start), str(end)], "git_commit": commit,
        "sources": sources, "ridership_fingerprint_match": sources[0]["fingerprint_match"],
        "ridership_scope": {**rinfo, "after_cutoff_rows": len(after),
                            "after_cutoff_first": str(after["date"].min()) if len(after) else None,
                            "after_cutoff_last": str(after["date"].max()) if len(after) else None,
                            "source_last_updated": rid["source_last_updated"]},
        "comparisons": C, "reconciliation": rec, "selection_summary": selection_summary, "gaps": gaps,
        "duration_complete_rows": int(schedule["duration_complete"].sum()),
        "invalid_durations": {k: v for k, v in invalid.items() if v},
        "rws_by_route": rws_by_route, "swr_by_route": swr_by_route,
        "rws_reasons": res["ridership_without_schedule"]["unmatched_reason"].value_counts().to_dict(),
        "regime_lines": regime_lines, "overlap_table": overlap_table, "regime_table": regime_table,
        "presence": presence, "record_days": record_days, "monthly": monthly, "outputs": outputs,
        "mismatch_explanation": ("The ridership export used here is newer than the spec's reference file "
                                 "(sha256 differs; publisher update 2026-10-28). Differences are reported as found "
                                 "and were not adjusted."),
    }
    args.out.mkdir(parents=True, exist_ok=True)
    write_report(args.out / "stage2_quality_report.md", ctx)
    checks = {"data_version": data_version, "comparisons": C, "reconciliation": rec, "gaps": gaps,
              "overlaps": overlaps, "fingerprints": fingerprints, "regimes": regimes,
              "invalid_durations": invalid, "presence": presence,
              "ridership_without_schedule_by_route": rws_by_route.to_dict("records"),
              "schedule_without_ridership_by_route": swr_by_route.to_dict("records"),
              "ridership_without_schedule_reasons": ctx["rws_reasons"]}
    (args.out / "stage2_quality_checks.json").write_text(json.dumps(checks, indent=2, default=str), encoding="utf-8")
    print(f"done: {len(C) - n_mis} MATCH, {n_mis} MISMATCH -> {args.out / 'stage2_quality_report.md'}")
    for c in C:
        if c["result"] == "MISMATCH":
            print(f"  MISMATCH {c['metric']}: spec {c['spec']} ours {c['ours']}")


if __name__ == "__main__":
    main()
