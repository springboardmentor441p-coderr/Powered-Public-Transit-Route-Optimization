"""Stage 5 quality report (markdown), checks (JSON), committed summary CSVs and the groups manifest.
Reads results only; makes no choices. Every number comes from the build context."""
from __future__ import annotations

import json
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

from analytics.groups.profiles import VIEWS
from analytics.reconstruction.report import _table

VIEW_LABEL = {"observed_daily_demand_rank": "observed daily demand (mean rides/day)",
              "rides_per_trip_rank": "rides per scheduled trip",
              "service_productivity_metric_rank": "rides per scheduled hour"}
SAT, SUN, CV = ("saturday_to_weekday_rides_ratio", "sunday_holiday_to_weekday_rides_ratio", "weekday_rides_cv")


def _r(df: pd.DataFrame, nd: int = 3) -> pd.DataFrame:
    """Round numbers and turn list cells (e.g. group sizes) into text, so the shared table helper can print them."""
    out = df.round(nd)
    for c in out.columns:
        if out[c].map(lambda v: isinstance(v, (list, tuple))).any():
            out[c] = out[c].map(lambda v: ", ".join(map(str, v)) if isinstance(v, (list, tuple)) else v)
    return out


def ranking_counts(ranking: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (period, dt), g in ranking.groupby(["period_name", "daytype"], sort=False):
        row = {"period": period, "day type": dt, "routes": int(len(g))}
        for v in VIEWS:
            row[f"ranked: {VIEW_LABEL[v]}"] = int(g[f"{v}_eligible"].sum())
        row["unranked"] = int((~g["observed_daily_demand_rank_eligible"]).sum())
        reasons = g["observed_daily_demand_rank_reason"].dropna().str.replace(r"\(\d+\)", "(n)", regex=True)
        row["unranked reasons"] = "; ".join(f"{k}: {n}" for k, n in reasons.value_counts().items())
        rows.append(row)
    return pd.DataFrame(rows)


def top_table(ranking: pd.DataFrame, period: str, daytype: str, n: int = 10) -> pd.DataFrame:
    g = ranking[(ranking["period_name"] == period) & (ranking["daytype"] == daytype)
                & ranking["service_productivity_metric_rank"].notna()]
    g = g.sort_values(["service_productivity_metric_rank", "route"]).head(n)
    return g[["route", "observed_days", "rides_per_scheduled_hour", "service_productivity_metric_rank",
              "rides_per_scheduled_trip", "rides_per_trip_rank", "mean_daily_rides", "observed_daily_demand_rank"]]


def unranked_rows(ranking: pd.DataFrame, period: str) -> pd.DataFrame:
    g = ranking[(ranking["period_name"] == period) & ~ranking["observed_daily_demand_rank_eligible"]
                & ~ranking["observed_daily_demand_rank_reason"].eq("no scheduled service of this day type")]
    return g[["route", "daytype", "observed_days", "scheduled_service_days", "observed_daily_demand_rank_reason"]]


def knife_edge(sel: dict, cfg: dict) -> list[str]:
    """Plain statement of the weekend-ratio decision and every pair within 0.02 of the correlation bar."""
    sp, bar = sel["spearman"], cfg["clustering"]["max_abs_spearman"]
    d = sel["decisions"].set_index("feature")
    out = []
    if SAT in d.index and SUN in d.index and d.loc[SAT, "kept"] != d.loc[SUN, "kept"]:
        kept, dropped = (SUN, SAT) if d.loc[SUN, "kept"] else (SAT, SUN)
        out.append(f"- **Knife-edge result (kept as the fixed rule decided, disclosed here):** the Saturday and "
                   f"Sunday/holiday ratios correlate at |ρ| = {abs(sp.loc[SAT, SUN]):.3f}, so they carry nearly the "
                   f"same information. `{dropped}` was dropped at |ρ| = {abs(sp.loc[dropped, CV]):.3f} against "
                   f"`{CV}`; `{kept}` stayed at |ρ| = {abs(sp.loc[kept, CV]):.3f}, against a bar of {bar}. Weekend "
                   "shape is still represented, through the kept ratio; a difference of "
                   f"{abs(abs(sp.loc[dropped, CV]) - abs(sp.loc[kept, CV])):.3f} decided which weekend day stands for "
                   "it. Part of the correlation with CV likely comes from the structural zeros (weekday-only routes "
                   "tend to be peak-heavy and more variable).")
    near = [f"`{f}` vs `{g}`: |ρ| = {abs(sp.loc[f, g]):.3f}"
            for f, g in combinations(cfg["clustering"]["candidates_in_priority_order"], 2)
            if abs(abs(sp.loc[f, g]) - bar) <= 0.02]
    if near:
        out.append(f"- Pairs within 0.02 of the bar ({bar}): " + "; ".join(near) + ".")
    return out


def write_report(out_dir: Path, ctx: dict) -> dict:
    cfg, k, kt = ctx["cfg"], ctx["k"], ctx["k_table"]
    ref = cfg["periods"]["reference_ranking_period"]
    dec = ctx["selection"]["decisions"]
    passing = kt[kt["passes_size_gate"]]
    best = passing["silhouette"].max()
    best_k = int(passing.sort_values("silhouette", ascending=False).iloc[0]["k"])
    chosen = kt.set_index("k").loc[k]
    tie = (f"a **near tie** with k = {best_k} ({chosen['silhouette']:.3f} vs {best:.3f}, a difference of "
           f"{best - chosen['silhouette']:.3f})" if best_k != k else "also the best silhouette")
    meaning = (f"A silhouette of {chosen['silhouette']:.2f} means **moderate separation**: real structure, but with "
               "routes near the boundary between groups (1 = tight, well-separated groups; 0 = groups that blur together).")
    mem, nb, ov = ctx["membership"], ctx["notebook"], ctx["overlap"]
    dv = ov["overlap"][ov["overlap"]["geometry_version"] == ctx["default_version"]]
    dv_top = dv.sort_values(["overlap_review_rank", "route_a", "route_b"]).head(10)

    L = ["# Stage 5 quality report: route groups and ranking", "",
         f"Generated {ctx['built_at']} by `analytics/groups/build_stage5.py` (spec 9.7, 9.11, 9.12; stage table 9.18). "
         "The spec wins where it differs from the mentor's notebook; the notebook's rules are recomputed in section 7.", "",
         f"- Data products: `{ctx['data_manifest']['data_version']}`; settings `groups.json` sha256 "
         f"`{ctx['data_manifest']['settings_sha256'][:16]}`; names `group_names.json` sha256 "
         f"`{ctx['data_manifest']['names_sha256'][:16]}`",
         f"- Code version: git `{ctx['git_commit']}`; artifact version `{cfg['artifact_version']}`",
         f"- Development profile period (groups): {cfg['periods']['development'][0]}..{cfg['periods']['development'][1]}. "
         f"Reference ranking period: `{ref}` "
         f"({cfg['periods']['ranking_periods'][ref][0]}..{cfg['periods']['ranking_periods'][ref][1]}), a "
         "historical-analysis table: it includes the June-July replay period, so replay mode must recompute "
         "rankings from revealed history only (Stage 7).",
         f"- Gates (spec 9.7.2 trial values, applied independently): ranking "
         f"{cfg['gates']['ranking_min_observed_days']} observed days; clustering base "
         f"{cfg['gates']['cluster_min_weekday_days']} weekdays; weekend ratio {cfg['gates']['cluster_min_weekend_days']} days", "",
         "## Summary", "",
         f"- **{int((mem['group'] != 'ungrouped').sum())}** routes grouped into **k = {k}** groups (chosen by the fixed "
         f"rule); **{int((mem['group'] == 'ungrouped').sum())}** of {len(mem)} routes in the ridership window ungrouped, "
         "each with a reason.",
         *[f"- Group {g}: **{n}** ({int((mem['group'] == str(g)).sum())} routes)" for g, n in ctx["group_names"].items()],
         f"- k = {k} is {tie}. {meaning}",
         f"- Rankings: three named indicators, ties preserved, unranked rows kept with their observed-day count and a "
         f"reason. Reference period, routes ranked by rides per scheduled hour (W/A/U): "
         + " / ".join(str(int(ctx["ranking"][(ctx["ranking"]["period_name"] == ref) & (ctx["ranking"]["daytype"] == d)]
                               ["service_productivity_metric_rank_eligible"].sum())) for d in ["W", "A", "U"]) + ".",
         f"- Route overlap review: {len(ov['per_version'])} geometry versions; default review version "
         f"`{ctx['default_version']}`. **Corridor review only**, not merge/split evidence.",
         "- Not built yet: forecast demand/service review (needs served forecasts from the replay, Stage 7).", ""]

    L += ["## 1. Rankings (spec 9.7.1, 9.12)", "",
          "Ratios are ratios of sums over the same matched dates. The hours ratio is unavailable when any included day "
          "has incomplete durations. Ties share the lowest rank. Every route in a period has W, A and U rows; an "
          "ineligible row stays **unranked** with its observed-day count and a reason. \"No scheduled service of this "
          "day type\" means the schedule shows no trips; it is not missing data.", "",
          *_table(ranking_counts(ctx["ranking"])), "",
          "Identities (every matched row counted exactly once; no rank on an ineligible row): "
          + "; ".join(f"`{p}` " + ", ".join(f"{k2} {v}" for k2, v in d.items()) for p, d in ctx["rank_identities"].items()) + ".", "",
          f"Unranked rows in the reference period other than \"no scheduled service\" (all rows are in "
          "`reports/stage5_rankings.csv`):", "", *_table(unranked_rows(ctx["ranking"], ref)), "",
          "**Gate sensitivity** (reported only; the configured gate of "
          f"{cfg['gates']['ranking_min_observed_days']} is unchanged). Routes ranked by rides per scheduled hour at "
          "each gate value:", "",
          *_table(ctx["sensitivity"].pivot_table(index=["period_name", "daytype"], columns="gate",
                                                 values="service_productivity_metric_rank ranked").astype(int)
                  .rename(columns=lambda c: f"gate {c}").reset_index().rename_axis(None, axis=1)), ""]
    for dt in ["W", "A", "U"]:
        L += [f"Reference period, day type {dt}: top 10 by rides per scheduled hour, with the other two named ranks", "",
              *_table(_r(top_table(ctx["ranking"], ref, dt))), ""]

    prof = ctx["profiles"]
    status = pd.DataFrame([{"day type": n, **prof[f"{n}_service_status"].value_counts().to_dict()}
                           for n in ["saturday", "sunday_holiday"]]).fillna(0)
    sp = ctx["selection"]["spearman"]
    L += ["## 2. Clustering profiles and features (spec 9.11.2)", "",
          f"- {len(prof)} routes in the development period; {int(prof['base_eligible'].sum())} pass the base gate.",
          "- Weekend status from the schedule: no scheduled service gives a **structural zero** (no buses ran); service "
          "with too few matched days is **unavailable** (filled in section 3); otherwise the measured ratio.", "",
          *_table(status), "", "Feature decisions (fixed rules, in priority order):", "",
          *_table(dec.assign(availability=(100 * dec["availability"]).round(1))), "", *knife_edge(ctx["selection"], cfg), "",
          "Spearman correlations (base-eligible routes):", "",
          *_table(_r(sp).reset_index().rename(columns={"index": "feature"})), ""]

    logf = set(cfg["clustering"]["log1p_features"])
    imp = pd.DataFrame(ctx["imputation"]).assign(**{"filled routes": lambda d: d["filled routes"].map(", ".join)})
    imp.insert(1, "units", imp["feature"].map(lambda f: "log1p" if f in logf else "original"))
    imp.insert(3, "fitted median (original units)",
               [float(np.expm1(v)) if f in logf else v for f, v in zip(imp["feature"], imp["fitted median"])])
    L += ["## 3. Imputation (service-aware median)", "",
          "Fitted on development profiles only. A weekend ratio's median comes **only from routes that have that "
          "service**; structural zeros are never filled and never enter the median. A naive median over all values "
          "is shown for comparison only. The pipeline works on log1p(weekday rides), so that row's medians are in "
          "log1p units; the original-units column converts them back (e.g. log1p 8.058 is about 3,160 rides a day).",
          "", *_table(_r(imp, 4)), ""]

    L += ["## 4. Number of groups (spec 9.11.3)", "", *_table(_r(kt)), "",
          f"- Rule (fixed in `groups.json` before any result): among k whose smallest group has ≥ "
          f"{cfg['clustering']['min_group_routes']} routes, take the smallest k within "
          f"{cfg['clustering']['silhouette_tolerance']} of the best silhouette.",
          f"- **Chosen by the fixed rule: k = {k}.** It is {tie}.",
          f"- Stability: seed adjusted Rand mean {chosen['stability_ari_mean']:.3f} (min {chosen['stability_ari_min']:.3f}); "
          f"agreement between the two half-periods {chosen['period_halves_ari']:.3f}.",
          f"- {meaning}", ""]

    sm = ctx["summary"]
    cand = cfg["clustering"]["candidates_in_priority_order"]
    view = pd.DataFrame([{"feature": f + (" *" if f in ctx["features"] else ""),
                          **{f"group {r['group']}: {r['name']} (n={r['routes']})":
                             f"{r[f + '_median']:.3f} ({r[f + '_min']:.2f}-{r[f + '_max']:.2f})" for _, r in sm.iterrows()}}
                         for f in cand])
    weekend = pd.DataFrame([{"group": f"{r['group']}: {r['name']}",
                             **{f"{n} {s}": int(r[f"{n}_{s}"]) for n in ["saturday", "sunday_holiday"]
                                for s in ["available", "no_scheduled_service", "insufficient_observations"]}}
                            for _, r in sm.iterrows()])
    L += ["## 5. Groups and explanations", "",
          "Median (min-max) in original units; * marks clustering features. Names were chosen after inspection and are "
          "applied only because the frozen memberships equal those in `analytics/config/group_names.json`.", "",
          *_table(view), "", "Weekend service status by group:", "", *_table(weekend), "",
          "Centroids in original units:", "", *_table(_r(ctx["centroids"])), "",
          "**Caveats** (stored with the names):", "", *[f"- {c}" for c in ctx["names"]["caveats"]], "",
          "Ungrouped routes:", "", *_table(mem[mem["group"] == "ungrouped"][["route", "reason"]]), "",
          *[f"- Group {r['group']} ({r['name']}) routes: {r['route_list']}" for _, r in sm.iterrows()], ""]

    L += ["## 6. Route stop coverage and overlap (spec 9.7, 9.12)", "",
          "Geometry version = GTFS archive; served stops come from bus trips active on the archive's applied dates. "
          f"Identities hold per version and for all versions combined: {all(ov['combined_checks'].values())}.", "",
          *_table(_r(ov["per_version"])), "",
          f"Default review version `{ctx['default_version']}`: top 10 pairs by Jaccard (ties share the rank).", "",
          "**Corridor review only:** shared stop IDs are not merge/split evidence (no direction, walking access, "
          "transfers or journeys). Smaller-route overlap of 1.000 means every stop of the smaller route is also on "
          "the other route.", "",
          *_table(_r(dv_top[["route_a", "route_b", "route_a_stop_count", "route_b_stop_count", "shared_stop_count",
                             "jaccard_stop_overlap", "smaller_route_stop_overlap", "overlap_review_rank"]])), ""]

    g = nb["groups"]
    L += ["## 7. Mentor notebook comparison (its rules recomputed; reads our outputs only)", "",
          *_table(pd.DataFrame([{"item": k2, "value": json.dumps(v) if isinstance(v, (dict, list)) else v}
                                for k2, v in {**nb["population_rows"], **nb["profiles"]}.items()])), "",
          "Routes the notebook drops, by their weekend status in our profiles:", "",
          *_table(nb["weekend_dropped_by_notebook_status_in_ours"]), "",
          f"- Features: notebook (fixed) {', '.join(nb['features']['notebook (fixed)'])}; ours (selected by rule) "
          f"{', '.join(nb['features']['ours (selected by rule)'])}.",
          f"- Groups: notebook k = {g['notebook k']}, ours k = {g['our k']}; agreement "
          f"{json.dumps(g['membership agreement'])}.", "", "Notebook k table:", "", *_table(_r(g["notebook k table"])), "",
          "Rides per scheduled hour, notebook training-period ranking vs our development-period ranking:", "",
          *_table(_r(nb["ranking"])), ""]

    fi = ctx["file_info"]
    L += ["## 8. Saved artifact and reproducibility", "",
          f"- `artifacts/stage5/route_groups.joblib` (imputer + scaler + KMeans): {fi['uncompressed_bytes']:,} bytes "
          f"uncompressed, **{fi['compressed_bytes']:,}** saved (compress 3), under 20 MB {fi['under_limit']}, sha256 "
          f"`{fi['sha256'][:16]}`; reload reproduces the memberships exactly: {ctx['reload_exact']}.",
          "- One thread for every KMeans fit/predict; fixed seeds; no timestamps inside the artifact or data CSVs, so a "
          "rerun must give identical hashes.",
          "- Data products: " + ", ".join(f"`{n}` {o['rows']:,} rows (`{o['sha256'][:12]}`)"
                                          for n, o in ctx["data_manifest"]["outputs"].items()),
          "- Runtime: " + ", ".join(f"{k2} {v}" for k2, v in ctx["runtime"].items()), "",
          "## 9. Limitations", "",
          "- Groups and rankings describe patterns, not route quality or performance; nothing here justifies a service cut.",
          "- The reference ranking period includes June-July (the replay period); it is a historical-analysis table only.",
          "- Overlap uses shared stop IDs only (no direction, time of day, walking access, transfers or journeys).",
          "- Archives are verified as in Stage 2: each registered ZIP's sha256 is checked and its extracted files are "
          "read. The extracted .txt files themselves are not re-hashed here or in Stage 2.",
          "- The 9.7.2 gates are CTA trial values, not validated sample sizes; see the gate sensitivity table.", ""]

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "stage5_quality_report.md").write_text("\n".join(L), encoding="utf-8")
    sm.to_csv(out_dir / "stage5_group_summary.csv", index=False, float_format="%.6f", lineterminator="\n")
    ctx["ranking"].to_csv(out_dir / "stage5_rankings.csv", index=False, float_format="%.6f", lineterminator="\n")
    checks = {"generated_at": ctx["built_at"], "artifact_version": cfg["artifact_version"], "k": k,
              "k_table": json.loads(kt.to_json(orient="records")), "features": ctx["features"],
              "rank_identities": ctx["rank_identities"], "reload_exact": ctx["reload_exact"],
              "names_match_frozen_memberships": True, "overlap_combined_checks": ov["combined_checks"],
              "overlap_per_version": json.loads(ov["per_version"].to_json(orient="records")),
              "notebook_profiles": nb["profiles"],
              "notebook_groups": {k2: v for k2, v in g.items() if k2 != "notebook k table"},
              "membership_counts": mem["reason"].value_counts().to_dict()}
    (out_dir / "stage5_quality_checks.json").write_text(json.dumps(checks, indent=2, default=str), encoding="utf-8")
    return {"artifact_version": cfg["artifact_version"], "created_at": ctx["built_at"], "git_commit": ctx["git_commit"],
            "code": "analytics/groups/build_stage5.py", "settings": cfg, "group_names": ctx["group_names"],
            "features": ctx["features"], "k": k, "file": fi, "reload_exact": ctx["reload_exact"],
            "data_products": ctx["data_manifest"], "default_overlap_version": ctx["default_version"],
            "profile_period": cfg["periods"]["development"], "runtime": ctx["runtime"]}
