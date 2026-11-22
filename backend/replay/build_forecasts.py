"""Stage 7, step 2: issue and store every replay forecast, day by day, before any session can reveal a day.

Walks the run's target days in order (1 Jun -> 31 Jul 2026). Each day's forecasts use only rides through the day
before (backend/replay/forecasting.py). Running it again inserts nothing and checks every stored row against a fresh
recomputation (a difference stops the job: stored forecasts are never rewritten).

Then the consistency check: over all target days, the stored model and baseline forecasts are scored against the
recorded rides on the SAME route-days, and must reproduce Stage 4a's test MAE for both methods (model_manifest.json).

From the repo root (CMD):
  python -I backend\\replay\\build_forecasts.py
  python -I backend\\replay\\build_forecasts.py --url-var TEST_DATABASE_URL
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import psycopg  # noqa: E402
from psycopg.rows import dict_row  # noqa: E402

from backend.importer.import_data import DEFAULTS, read_env  # noqa: E402
from backend.replay.forecasting import (BASELINE, commit_or_unknown, ensure_run, run_hash,  # noqa: E402
                                        store_range)

MANIFEST = REPO_ROOT / "artifacts" / "stage4a" / "model_manifest.json"


def consistency(conn: psycopg.Connection, run_id: str, model_method: str) -> dict:
    """Score the stored forecasts on route-days where BOTH methods forecast and a ride is recorded."""
    r = conn.cursor(row_factory=dict_row).execute("""
        WITH f AS (
            SELECT m.route, m.target_date, m.prediction AS model, b.prediction AS base
            FROM forecasts m JOIN forecasts b
              ON b.run_id = m.run_id AND b.route = m.route AND b.target_date = m.target_date
             AND b.issue_date = m.issue_date AND b.method = %(base)s
            WHERE m.run_id = %(run)s AND m.method = %(model)s AND m.status = 'forecast' AND b.status = 'forecast')
        SELECT count(*) AS rows,
               avg(abs(d.rides - f.model)) AS model_mae, avg(abs(d.rides - f.base)) AS base_mae,
               100 * sum(abs(d.rides - f.model)) / sum(d.rides) AS model_wape,
               100 * sum(abs(d.rides - f.base)) / sum(d.rides) AS base_wape
        FROM f JOIN forecast_runs run ON run.run_id = %(run)s
        JOIN daily_ridership d ON d.data_version = run.data_version AND d.route = f.route
                              AND d.service_date = f.target_date""",
        {"run": run_id, "model": model_method, "base": BASELINE}).fetchone()
    return {k: (float(v) if k != "rows" else int(v)) for k, v in r.items()}


def stage4_reference(model_method: str) -> dict:
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    test = {x["method"]: x for x in m["test_metrics_reused_holdout"]}
    return {"rows": test[model_method]["scored_rows"], "model_mae": test[model_method]["MAE"],
            "base_mae": test[BASELINE]["MAE"], "base_rows": test[BASELINE]["scored_rows"]}


def build(conn: psycopg.Connection) -> dict:
    run = ensure_run(conn, DEFAULTS["version_dir"].name, code_commit=commit_or_unknown())
    days = store_range(conn, run, run.first_target, run.last_target)
    c = consistency(conn, run.run_id, run.model_method)
    ref = stage4_reference(run.model_method)
    ok = (c["rows"] == ref["rows"] == ref["base_rows"] and abs(c["model_mae"] - ref["model_mae"]) < 1e-6
          and abs(c["base_mae"] - ref["base_mae"]) < 1e-6)
    return {"run": run, "days": days, "hash": run_hash(conn, run.run_id), "consistency": c, "stage4": ref, "ok": ok}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--env", type=Path, default=REPO_ROOT / "backend" / ".env")
    ap.add_argument("--url-var", default="DATABASE_URL")
    args = ap.parse_args()
    url = read_env(args.env).get(args.url_var)
    if not url:
        raise SystemExit(f"{args.url_var} is not set in {args.env}")
    with psycopg.connect(url, autocommit=True) as conn:
        out = build(conn)
    run, c, ref = out["run"], out["consistency"], out["stage4"]
    ins = sum(d["inserted"] for d in out["days"])
    total = sum(d["rows"] for d in out["days"])
    print(f"run {run.run_id}: {len(out['days'])} days, {total:,} forecast rows ({ins:,} newly stored, "
          f"{total - ins:,} already stored and re-verified)")
    print(f"content sha256 {out['hash']}")
    print(f"consistency on {c['rows']:,} shared route-days: model MAE {c['model_mae']:.4f} (Stage 4a {ref['model_mae']:.4f}), "
          f"baseline MAE {c['base_mae']:.4f} (Stage 4a {ref['base_mae']:.4f}); WAPE {c['model_wape']:.2f} % vs "
          f"{c['base_wape']:.2f} %")
    if not out["ok"]:
        raise SystemExit("CONSISTENCY CHECK FAILED: the stored forecasts do not reproduce Stage 4a's test scores")
    print("consistency check passed")


if __name__ == "__main__":
    main()
