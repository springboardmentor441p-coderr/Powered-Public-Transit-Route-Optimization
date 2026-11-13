"""Step 16: Stage 2 quality report (spec 9.6.6, 9.22.2): source versions, periods, counts, comparisons, checks.

Every reference number is COMPARED and labelled MATCH / MISMATCH; nothing is adjusted to reach it.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd


def compare(metric: str, spec, ours, section: str) -> dict:
    if isinstance(spec, (int, float)) and isinstance(ours, (int, float)) and not isinstance(spec, bool):
        diff = ours - spec
        diff_txt = f"{diff:+,}" if isinstance(diff, int) else f"{diff:+.3f}"
        ok = abs(diff) < 1e-9
    else:
        ok, diff_txt = spec == ours, ""
    return {"section": section, "metric": metric, "spec": spec, "ours": ours,
            "result": "MATCH" if ok else "MISMATCH", "difference": diff_txt}


def _fmt(v) -> str:
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, int):
        return f"{v:,}"
    if isinstance(v, float):
        return f"{v:,.3f}"
    if isinstance(v, list):
        return ", ".join(map(str, v))
    return "" if v is None else str(v)


def _table(df: pd.DataFrame) -> list[str]:
    cols = list(df.columns)
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows():
        out.append("| " + " | ".join(_fmt(r[c]) if not pd.isna(r[c]) else "" for c in cols) + " |")
    return out


def write_report(path, ctx: dict) -> None:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    comps = ctx["comparisons"]
    n_mis = sum(c["result"] == "MISMATCH" for c in comps)
    rec = ctx["reconciliation"]
    L = ["# Stage 2 quality report: daily reconstruction and exact matching", "",
         f"Generated {now} by `analytics/reconstruction/build_stage2.py` (spec v3.8, sections 9.5, 9.6.2-9.6.5, 9.19.1).",
         "",
         f"- Data version: `{ctx['data_version']}` (outputs in `data/processed/{ctx['data_version']}/`)",
         f"- Analysis period: {ctx['period'][0]} to {ctx['period'][1]}; ridership rows dated on/before {ctx['period'][1]} only",
         f"- Code version: git `{ctx['git_commit']}`",
         f"- Reference comparisons: **{len(comps) - n_mis} MATCH, {n_mis} MISMATCH**", "",
         "> Reference counts are compared, never forced (spec 9.22.2). Missing passenger observations stay missing; "
         "they are never turned into zero rides. Payload integrity and schedule agreement do not verify actually "
         "operated service.", ""]

    L += ["## 1. Source versions", "", "| dataset | snapshot | sha256 (first 16) | matches spec 9.22.1 | used for |",
          "|---|---|---|---|---|"]
    for s in ctx["sources"]:
        L.append(f"| {s['dataset_id']} | `{s['snapshot_id']}` | `{s['sha256'][:16]}` | {s['fingerprint_match']} | {s['used_for']} |")
    rs = ctx["ridership_scope"]
    L += ["", f"Ridership export: {rs['raw_rows']:,} raw rows; {rs['exact_duplicates_removed']:,} exact duplicates removed; "
          f"{rs['missing_rides']:,} missing rides values. Rows after {ctx['period'][1]}: **{rs['after_cutoff_rows']:,}** "
          f"({rs['after_cutoff_first']} to {rs['after_cutoff_last']}), excluded from this stage and kept in the raw file. "
          f"Publisher last update: {rs['source_last_updated']}.", ""]
    if not ctx["ridership_fingerprint_match"]:
        L += ["**Provenance note:** the ridership export is not byte-identical to the spec's 2026-10-22 reference file. "
              "Any count difference below should first be explained by that newer export (the publisher updated the "
              "dataset on 2026-10-28), not by the reconstruction.", ""]

    L += ["## 2. Reference comparison", "", "| section | metric | spec | ours | result | difference |",
          "|---|---|---:|---:|---|---:|"]
    for c in comps:
        L.append(f"| {c['section']} | {c['metric']} | {_fmt(c['spec'])} | {_fmt(c['ours'])} | **{c['result']}** | {c['difference']} |")
    L.append("")

    L += ["## 3. Snapshot selection (spec 9.6.3)", "",
          "One whole snapshot per date: the latest captured on/before the date. No per-route fallback.", "",
          *_table(ctx["selection_summary"]), "",
          f"Selection gaps (no archive captured yet, or the selected archive defines no bus service): "
          f"**{len(ctx['gaps'])}**" + (f": {ctx['gaps']}" if ctx["gaps"] else ""), ""]

    L += ["## 4. Daily scheduled service", "",
          f"- Rows: {rec['schedule_records']:,}; dates: {rec['schedule_dates']}; routes: {rec['schedule_routes']}",
          f"- Route/dates with complete durations: {ctx['duration_complete_rows']:,} of {rec['schedule_records']:,}; "
          f"invalid trip durations by reason: {ctx['invalid_durations'] or 'none'}",
          f"- Unique (date, trip_id) among active trips: enforced (build stops otherwise)", ""]

    L += ["## 5. Exact matching and two-direction reconciliation (spec 9.6.4)", "",
          "```",
          f"{rec['ridership_observations']:,} ridership observations = {rec['matched']:,} matched + "
          f"{rec['ridership_without_schedule']:,} without selected service   -> holds: {rec['identity_ridership_holds']}",
          f"{rec['schedule_records']:,} schedule records       = {rec['matched']:,} matched + "
          f"{rec['schedule_without_ridership']:,} without recorded rides    -> holds: {rec['identity_schedule_holds']}",
          "```", "",
          f"- Matched coverage: {rec['matched_dates']} dates, {rec['matched_routes']} routes. "
          f"Ridership side: {rec['ridership_dates']} dates, {rec['ridership_routes']} identifiers.",
          f"- Schedule-conditioned coverage: {rec['schedule_conditioned_coverage_pct']}%; routes with records on every "
          f"scheduled date: {rec['routes_with_records_on_every_scheduled_date']} of {rec['schedule_routes']}.",
          f"- Genuine zero-ride matched rows (kept as 0): {rec['matched_zero_ride_rows']}", "",
          "### Ridership observations without selected scheduled service (by route)", "",
          *_table(ctx["rws_by_route"]), "",
          "Reasons: " + ", ".join(f"{k} = {v}" for k, v in ctx["rws_reasons"].items()), "",
          "### Scheduled route/dates without a ridership observation (by route)", "",
          *_table(ctx["swr_by_route"]), "",
          "These rows keep `rides` empty (missing). They are not zero-ridership targets.", ""]

    L += ["## 6. Archive integrity and timetable regimes (spec 9.6.5)", ""]
    for line in ctx["regime_lines"]:
        L.append(f"- {line}")
    L += ["", "Same-date overlap comparisons (older vs newer archive on the newer one's first days, where both define service):", "",
          *_table(ctx["overlap_table"]), "",
          "Bus calendar regimes inside each archive (distinct calendar.txt ranges used by bus trips):", "",
          *_table(ctx["regime_table"]), ""]

    L += ["## 7. Descriptive summaries (spec 9.6.2, 9.6.4.2, 9.6.4.3)", "",
          f"- Route-name presence: {ctx['presence']['pct']}% of recent-window rows "
          f"({ctx['presence']['records_with_route_in_archives']:,} of {ctx['presence']['records']:,}) use an identifier "
          "found in at least one of the 8 archived bus route tables. The spec's 97.95% is measured against the original "
          "*September* schedule, which is not one of this stage's inputs, so it is **not directly reproducible** here; "
          "context only.",
          f"- Identifiers absent from all 8 archives (recent window): {ctx['presence']['absent_identifiers']}", "",
          "Route 10 / 130 record days in 2026:", "", *_table(ctx["record_days"]), "",
          "Monthly ridership record coverage in the analysis period (record availability, not reporting completeness):", "",
          *_table(ctx["monthly"]), ""]

    if n_mis:
        L += ["## 8. Mismatches", ""]
        for c in comps:
            if c["result"] == "MISMATCH":
                L.append(f"- **{c['metric']}**: spec {_fmt(c['spec'])}, ours {_fmt(c['ours'])} ({c['difference']}).")
        L += ["", ctx.get("mismatch_explanation", ""), ""]

    L += ["## Outputs", "", "| file | rows | sha256 (first 16) |", "|---|---:|---|"]
    for name, o in ctx["outputs"].items():
        L.append(f"| `{name}` | {o['rows']:,} | `{o['sha256'][:16]}` |")
    L.append("")
    path.write_text("\n".join(L), encoding="utf-8")
