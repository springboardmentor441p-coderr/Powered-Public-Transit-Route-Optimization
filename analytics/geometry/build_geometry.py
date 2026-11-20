"""Stage 6a, Step 56: build route_shapes.csv for all 8 geometry versions.

From the repo root (CMD):
  python -I analytics\\geometry\\build_geometry.py --sources analytics\\config\\sources.json ^
      --register reports\\source_register.csv ^
      --version-dir data\\processed\\cta_ref__r20261113__gtfs8__to20260731
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]  # `python -I` skips the script folder; add our own repo root
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import duckdb  # noqa: E402
import pandas as pd  # noqa: E402

from analytics.geometry.route_shapes import (BOUNDS, COORD_ORDER, PATH_DEFINITION, PATH_LABEL, TIE_LABEL,  # noqa: E402
                                             TIE_RULE, verify, version_shapes)
from analytics.models.train_stage4a import now  # noqa: E402
from analytics.reconstruction.build_stage2 import git_commit, sha256  # noqa: E402
from analytics.reconstruction.gtfs_tables import open_snapshot  # noqa: E402
from analytics.reconstruction.snapshot_select import applied_ranges, selection_table  # noqa: E402

GROUPS = "groups__dev20251123_20260331"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for a in ["--sources", "--register", "--version-dir"]:
        ap.add_argument(a, required=True, type=Path)
    args = ap.parse_args()
    vdir = args.version_dir
    out_dir = vdir / "geometry"
    if out_dir.exists():  # processed products are never overwritten; a rebuild goes to a new version
        raise SystemExit(f"{out_dir} already exists; refusing to overwrite")

    sources = json.loads(args.sources.read_text(encoding="utf-8"))
    manifest = json.loads((vdir / "manifest.json").read_text(encoding="utf-8"))
    gman = json.loads((vdir / GROUPS / "groups_data_manifest.json").read_text(encoding="utf-8"))
    with open(args.register, newline="", encoding="utf-8") as f:
        reg = {r["snapshot_id"]: r for r in csv.DictReader(f)}

    cov_path = vdir / GROUPS / "route_stop_coverage.csv"
    if sha256(cov_path) != gman["outputs"]["route_stop_coverage.csv"]["sha256"]:
        raise SystemExit("route_stop_coverage.csv differs from its Stage 5 manifest")
    cov = pd.read_csv(cov_path, dtype=str, usecols=["geometry_version", "route"])

    archives_cfg = sources["gtfs"]["archives"]
    archives = [{"snapshot_id": a["snapshot_id"], "captured": date.fromisoformat(a["captured"])} for a in archives_cfg]
    start, end = (date.fromisoformat(x) for x in sources["stage2_reference"]["analysis_period"])
    sel = selection_table(start, end, archives)
    ranges = applied_ranges(sel)

    tables, per_version = [], []
    for a in archives_cfg:
        sid = a["snapshot_id"]
        zip_path = REPO_ROOT / reg[sid]["local_path"]
        if not (sha256(zip_path) == reg[sid]["sha256"] == manifest["input_fingerprints"][sid]):
            raise SystemExit(f"{sid}: ZIP differs from the register / Stage 2 manifest (raw files are immutable)")
        if [str(ranges[sid][0]), str(ranges[sid][1])] != a["applied_dates"]:
            raise SystemExit(f"{sid}: applied dates {ranges[sid]} differ from sources.json {a['applied_dates']}")
        extracted = zip_path.parent / "extracted"
        con, _ = open_snapshot(extracted)
        try:
            t = version_shapes(con, sid, extracted / "shapes.txt", sorted(sel.loc[sel["snapshot_id"] == sid, "date"]))
        finally:
            con.close()
        checks = verify(t, set(cov.loc[cov["geometry_version"] == sid, "route"]))
        tables.append(t)
        per_version.append({"geometry_version": sid, "applied_dates": a["applied_dates"], "routes": t["route"].nunique(),
                            "route_directions": len(t), "tied_route_directions": int((t["tied_top_shapes"] > 1).sum()),
                            "points": int(t["point_count"].sum()), "identities_hold": all(checks.values())})

    out = pd.concat(tables, ignore_index=True)
    out_dir.mkdir(parents=True)
    path = out_dir / "route_shapes.csv"
    out.to_csv(path, index=False, lineterminator="\n")
    gm = {
        "data_version": f"{manifest['data_version']}/geometry", "created_at": now(), "git_commit": git_commit(),
        "code": "analytics/geometry/build_geometry.py", "label": PATH_LABEL, "definition": PATH_DEFINITION,
        "tie_rule": TIE_RULE, "tie_label": TIE_LABEL, "coordinate_order": COORD_ORDER, "bounds_check": BOUNDS,
        "inputs": {"gtfs_zip_sha256": {a["snapshot_id"]: reg[a["snapshot_id"]]["sha256"] for a in archives_cfg},
                   "route_stop_coverage.csv": gman["outputs"]["route_stop_coverage.csv"]["sha256"]},
        "limitations": ["extracted shapes.txt/trips.txt are not re-hashed (the ZIP is), as in Stages 2 and 5"],
        "outputs": {"route_shapes.csv": {"rows": len(out), "columns": len(out.columns), "sha256": sha256(path)}},
        "per_version": per_version,
        "runtime": {"python": sys.version.split()[0], "pandas": pd.__version__, "duckdb": duckdb.__version__},
    }
    (out_dir / "geometry_manifest.json").write_text(json.dumps(gm, indent=2), encoding="utf-8")
    print(pd.DataFrame(per_version).to_string(index=False))


if __name__ == "__main__":
    main()
