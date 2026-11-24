r"""Stage 8: save the deliberate scenario examples (spec 9.18 deliverable "saved scenario examples") and export them.

These are the ONLY scenarios meant for the app database. Saved scenarios can never be deleted, so this script:
  - saves only when the database holds no example yet; otherwise it saves nothing and just re-checks the stored ones;
  - recomputes every example and requires an identical result hash;
  - writes reports/stage8_scenario_examples.json (inputs, assumptions, the key numbers and the hashes).

From the repo root (CMD), once:
  python -I backend\scenarios\save_examples.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.db import open_write_conn, resolve_version  # noqa: E402
from backend.importer.import_data import read_env  # noqa: E402
from backend.scenarios.store import _json, recompute, save  # noqa: E402

OUT = REPO_ROOT / "reports" / "stage8_scenario_examples.json"
EXAMPLES = [
    ("Route 49: 20 % more weekday trips, demand held fixed",
     {"baseline": {"routes": ["49"], "period": "full_matched_window", "daytype": "W"},
      "service": [{"routes": None, "trips": {"how": "percent", "value": 20}, "trip_hours": None}],
      "demand_stress": None}),
    ("Lower-demand group: rides assumed 15 % lower on weekdays",
     {"baseline": {"group_id": 1, "period": "full_matched_window", "daytype": "W"},
      "service": [], "demand_stress": {"percent": -15, "scope": "baseline_routes", "routes": None}}),
    ("Route 1: add 40 Sunday trips where there is no Sunday service",
     {"baseline": {"routes": ["1"], "period": "full_matched_window", "daytype": "U"},
      "service": [{"routes": None, "trips": {"how": "per_day", "value": 40}, "trip_hours": None}],
      "demand_stress": None}),
]
KEY = ("rides_per_day", "trips_per_day", "hours_per_day", "mean_trip_minutes", "rides_per_scheduled_trip",
       "rides_per_scheduled_hour", "rank_rides_per_scheduled_hour", "reasons")


def summary(row: dict) -> dict:
    res = row["result"]
    return {"scenario_id": row["scenario_id"], "name": row["name"], "version": row["version"], "origin": row["origin"],
            "mode": row["mode"], "cutoff": row["cutoff"], "data_version": row["data_version"],
            "group_version": row["group_version"], "baseline": row["baseline"]["request"],
            "inputs": row["inputs"], "assumptions": [a["text"] for a in row["assumptions"]],
            "result_sha256": row["result_sha256"].strip(), "created_at": row["created_at"],
            "routes": [{"route": r["route"], "status": r["status"], "note": r["note"],
                        "baseline": {k: r["baseline"][k] for k in KEY}, "scenario": {k: r["scenario"][k] for k in KEY}}
                       for r in res["rows"]],
            "totals_selected": res["totals"]["selected"], "totals_network": res["totals"]["network"],
            "other_rank_changes": len(res["other_rank_changes"]), "ranked_routes": res["ranked_routes"]}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--env", type=Path, default=REPO_ROOT / "backend" / ".env")
    ap.add_argument("--url-var", default="DATABASE_URL")
    args = ap.parse_args()
    url = read_env(args.env)[args.url_var]
    with open_write_conn(url) as conn:
        v = resolve_version(conn, None)
        stored = conn.execute("SELECT * FROM scenarios WHERE origin = 'example' ORDER BY created_at").fetchall()
        if stored:
            print(f"{len(stored)} examples already saved: nothing new is saved, the stored ones are re-checked")
        else:
            for name, req in EXAMPLES:
                row, created = save(conn, v, None, req, name, origin="example")
                print(f"{'saved' if created else 'already stored'}: {row['scenario_id']}  {name}")
            stored = conn.execute("SELECT * FROM scenarios WHERE origin = 'example' ORDER BY created_at").fetchall()
        out = []
        for row in stored:
            chk = recompute(conn, v, row)
            if not chk["identical"]:
                raise SystemExit(f"RECOMPUTE DIFFERS for {row['scenario_id']}: {chk}")
            print(f"recomputed identically: {row['scenario_id']}  sha256 {chk['recomputed_sha256'][:16]}...")
            out.append({**summary(row), "recompute_identical": True})
        total = conn.execute("SELECT count(*) AS n FROM scenarios").fetchone()["n"]
    OUT.write_text(json.dumps(_json(out), indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{total} scenarios in this database; examples exported to {OUT.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
