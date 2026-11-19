"""Stage 5, Step 50: the mentor notebook's grouping and ranking rules (steps 36-44), recomputed for comparison.

The spec wins where it differs (your decision for Stage 5); nothing here feeds our groups or rankings. The rules
are re-implemented as the notebook states them, on the notebook's population: forecast-time feature rows
(feature_rows.csv) in the training split with recorded rides (2025-11-24..2026-03-31).
`compare` only READS our profiles, labels and ranking table; it never modifies them.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

NB_FEATURES = ["log_weekday_boardings", "weekday_variability", "saturday_to_weekday_ratio",
               "sunday_holiday_to_weekday_ratio", "log_weekday_scheduled_trips"]


def notebook_population(feature_rows: pd.DataFrame) -> pd.DataFrame:
    """Notebook step 36: training-period rows with a recorded count."""
    t = feature_rows[feature_rows["split"].eq("train") & feature_rows["rides"].notna()]
    return t[["route", "date", "daytype", "rides", "scheduled_trips", "scheduled_hours"]].copy()


def notebook_profiles(train_all: pd.DataFrame, nc: dict) -> tuple[pd.DataFrame, dict]:
    """Notebook step 37: one profile per route, or an exclusion reason."""
    rows, reasons = [], {}
    for route, g in train_all.groupby("route"):
        weekday = g.loc[g["daytype"].eq("W"), "rides"]
        saturday = g.loc[g["daytype"].eq("A"), "rides"]
        sunday = g.loc[g["daytype"].eq("U"), "rides"]
        if len(weekday) < nc["min_weekdays"]:
            reasons[route] = f"fewer than {nc['min_weekdays']} weekdays in training ({len(weekday)})"
            continue
        if len(saturday) < nc["min_saturdays"] or len(sunday) < nc["min_sundays"]:
            reasons[route] = (f"fewer than {nc['min_saturdays']} Saturdays or {nc['min_sundays']} "
                              "Sundays/holidays in training")
            continue
        mean_w = weekday.mean()
        if mean_w <= 0:
            reasons[route] = "mean weekday boardings not positive"
            continue
        rows.append({"route": route, "log_weekday_boardings": np.log1p(mean_w),
                     "weekday_variability": weekday.std() / mean_w,
                     "saturday_to_weekday_ratio": saturday.mean() / mean_w,
                     "sunday_holiday_to_weekday_ratio": sunday.mean() / mean_w,
                     "log_weekday_scheduled_trips": np.log1p(g.loc[g["daytype"].eq("W"), "scheduled_trips"].mean())})
    return pd.DataFrame(rows, columns=["route", *NB_FEATURES]), reasons


def notebook_groups(profiles: pd.DataFrame, nc: dict, seed: int) -> dict:
    """Notebook steps 38-41: scale, try 2..min(6, n-1) groups, size gate, silhouette rule, final fit."""
    if len(profiles) < 4:
        return {"table": pd.DataFrame(), "k": None, "labels": None}
    X = StandardScaler().fit_transform(profiles[NB_FEATURES])
    rows, labels_by_k = [], {}
    with threadpool_limits(limits=1):
        for k in range(2, min(6, len(profiles) - 1) + 1):
            labels = KMeans(n_clusters=k, n_init=10, random_state=seed).fit(X).labels_
            sizes = np.bincount(labels, minlength=k)
            repeats = [KMeans(n_clusters=k, n_init=10, random_state=s).fit(X).labels_ for s in range(1, 6)]
            rows.append({"k": k, "group_sizes": sizes.tolist(), "smallest_group": int(sizes.min()),
                         "passes_size_gate": bool(sizes.min() >= nc["min_cluster_routes"]),
                         "silhouette": float(silhouette_score(X, labels)),
                         "stability_ari_mean": float(np.mean([adjusted_rand_score(labels, r) for r in repeats]))})
            labels_by_k[k] = labels
    table = pd.DataFrame(rows)
    passing = table[table["passes_size_gate"]]
    k = None
    if not passing.empty:
        k = int(passing.loc[passing["silhouette"] >= passing["silhouette"].max() - 0.02, "k"].min())
    labels = pd.Series(labels_by_k[k], index=profiles["route"].to_numpy()) if k else None
    return {"table": table, "k": k, "labels": labels}


def notebook_ranking(train_all: pd.DataFrame, nc: dict) -> pd.DataFrame:
    """Notebook steps 43-44: rides per scheduled hour per day type, sequential ranks (ties broken by order)."""
    out = []
    for code in ["W", "A", "U"]:
        g = train_all.loc[train_all["daytype"].eq(code) & train_all["scheduled_hours"].gt(0)]
        t = g.groupby("route").agg(service_days=("date", "size"), rides=("rides", "sum"),
                                   hours=("scheduled_hours", "sum"))
        t = t.loc[t["service_days"].ge(nc["min_rank_dates"])].copy()
        t["rides_per_service_hour"] = t["rides"] / t["hours"]
        t = t.sort_values("rides_per_service_hour", ascending=False).reset_index()
        t.insert(0, "daytype", code)
        t.insert(1, "notebook_rank", range(1, len(t) + 1))
        out.append(t)
    return pd.concat(out, ignore_index=True)


def compare(feature_rows: pd.DataFrame, our_profiles: pd.DataFrame, our_labels: pd.Series | None,
            our_selected: list[str], our_k: int | None, our_ranking_dev: pd.DataFrame, cfg: dict) -> dict:
    nc = cfg["notebook_comparison"]
    train_all = notebook_population(feature_rows)
    nb_prof, nb_reasons = notebook_profiles(train_all, nc)
    nb = notebook_groups(nb_prof, nc, int(cfg["seed"]))
    nb_rank = notebook_ranking(train_all, nc)

    ours_base = set(our_profiles.loc[our_profiles["base_eligible"].astype(bool), "route"])
    nb_valid = set(nb_prof["route"])
    reason_counts = pd.Series(nb_reasons, dtype=object).value_counts().to_dict()
    weekend_dropped = sorted(r for r, why in nb_reasons.items() if "Saturdays" in why)
    st = our_profiles.set_index("route")
    weekend_dropped_status = (st.loc[[r for r in weekend_dropped if r in st.index],
                                     ["saturday_service_status", "sunday_holiday_service_status"]]
                              .value_counts().rename("routes").reset_index())

    ari = None
    if nb["labels"] is not None and our_labels is not None:
        common = sorted(set(nb["labels"].index) & set(our_labels.index))
        if common:
            ari = {"routes_grouped_by_both": len(common),
                   "adjusted_rand": float(adjusted_rand_score(nb["labels"][common], our_labels[common]))}

    rank_rows = []
    ours = our_ranking_dev[our_ranking_dev["service_productivity_metric_rank_eligible"]]
    for code in ["W", "A", "U"]:
        n = nb_rank[nb_rank["daytype"] == code].set_index("route")
        o = ours[ours["daytype"] == code].set_index("route")
        common = sorted(set(n.index) & set(o.index))
        rho = (float(pd.Series(n.loc[common, "notebook_rank"]).corr(
               pd.Series(o.loc[common, "service_productivity_metric_rank"].astype(float)), method="spearman"))
               if len(common) >= 3 else None)
        rank_rows.append({"daytype": code, "routes ranked (notebook)": len(n), "routes ranked (ours)": len(o),
                          "common routes": len(common), "rank Spearman on common routes": rho,
                          "tied values kept by ours": int(o["service_productivity_metric_rank"].duplicated(keep=False).sum())})
    return {
        "population_rows": {"notebook (forecast-time rows with rides, train)": int(len(train_all)),
                            "notebook routes": int(train_all["route"].nunique()),
                            "notebook first date": str(train_all["date"].min().date())},
        "profiles": {"notebook valid profiles (recomputed)": len(nb_valid),
                     "notebook valid profiles (stated)": nc["reported_valid_profiles"],
                     "ours base-eligible": len(ours_base),
                     "in ours, not in notebook": len(ours_base - nb_valid),
                     "in notebook, not in ours": len(nb_valid - ours_base),
                     "notebook exclusion reasons": reason_counts},
        "weekend_dropped_by_notebook_status_in_ours": weekend_dropped_status,
        "features": {"notebook (fixed)": NB_FEATURES, "ours (selected by rule)": our_selected},
        "groups": {"notebook k table": nb["table"], "notebook k": nb["k"], "our k": our_k, "membership agreement": ari},
        "ranking": pd.DataFrame(rank_rows),
        "notebook_ranking_table": nb_rank,
    }
