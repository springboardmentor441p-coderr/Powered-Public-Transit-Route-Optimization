"""RouteRanker - EXPLORATORY DATA ANALYSIS (single main file).

Reads the processed hourly route x hour table produced by the backend
(``python backend/main.py train``) and runs the complete EDA:

* descriptive statistics (mean, median, std, quantiles, skewness, kurtosis)
* temporal profiling (hour-of-day curves per day type, day-of-week boxplots,
  daily time series with 7-day rolling mean and holiday markers)
* route density heatmap (route x hour mean boardings)
* distribution analysis of occupancy with class thresholds
* performance-class share by hour
* Spearman rank correlation between route KPIs
* IQR outlier detection on daily route ridership
* group comparisons by borough and route type, productivity ranking
* speed vs crowding, stop-set overlap (Jaccard) and under-utilisation screening

Granularity: HOURLY (one row per route per clock hour, America/New_York).

Usage (from the project root):
    python eda/main.py

Outputs: eda/figures/*.png and eda/eda_summary.json
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
import seaborn as sns  # noqa: E402

# ----------------------------------------------------------------------------------------------
# Paths and inputs (produced by backend/main.py)
# ----------------------------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = ROOT / "data" / "processed"
METRICS_DIR = ROOT / "reports" / "metrics"
EDA_DIR = ROOT / "eda"
FIGURES_DIR = EDA_DIR / "figures"
FIGURES_DIR.mkdir(parents=True, exist_ok=True)
CLASS_LABELS = ["Underutilized", "Balanced", "Overcrowded"]
THRESHOLDS = {"underutilized_max": 0.25, "overcrowded_min": 0.85}
if (PROCESSED_DIR / "thresholds.json").exists():
    THRESHOLDS.update(json.loads((PROCESSED_DIR / "thresholds.json").read_text()))


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    """Load the hourly route-hour table, route profiles, stop-overlap pairs and cleaning report."""
    missing = [f for f in ("route_hour.parquet", "route_info.parquet", "overlap.parquet")
               if not (PROCESSED_DIR / f).exists()]
    if missing:
        raise SystemExit(f"Missing {missing} in data/processed - run `python backend/main.py train` first.")
    rh = pd.read_parquet(PROCESSED_DIR / "route_hour.parquet")
    rh["is_am_peak"] = rh["hour"].isin(range(6, 10)).astype("int8")
    rh["is_pm_peak"] = rh["hour"].isin(range(16, 20)).astype("int8")
    profiles = pd.read_parquet(PROCESSED_DIR / "route_info.parquet")
    overlap = pd.read_parquet(PROCESSED_DIR / "overlap.parquet")
    rep_file = METRICS_DIR / "cleaning_report.json"
    cleaning_report = json.loads(rep_file.read_text()) if rep_file.exists() else {}
    return rh, profiles, overlap, cleaning_report


# ----------------------------------------------------------------------------------------------
# EDA methods and figures
# ----------------------------------------------------------------------------------------------
sns.set_theme(style="whitegrid", context="notebook")
PALETTE = {"Weekday": "#2563eb", "Saturday": "#f59e0b", "Sunday": "#10b981",
           "Underutilized": "#94a3b8", "Balanced": "#22c55e", "Overcrowded": "#ef4444"}


def _save(fig, name: str) -> str:
    """Save a matplotlib figure to reports/figures and return its relative path."""
    path = FIGURES_DIR / name
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return str(path.relative_to(ROOT))


def descriptive_stats(rh: pd.DataFrame) -> dict:
    """Summary statistics of the main hourly variables incl. skewness & kurtosis."""
    cols = ["ridership", "transfers", "trips", "load_per_trip", "occupancy", "productivity", "speed_mph"]
    d = rh[cols].describe(percentiles=[0.25, 0.5, 0.75, 0.9, 0.99]).T
    d["skew"] = rh[cols].skew()
    d["kurtosis"] = rh[cols].kurt()
    return d.round(3).to_dict(orient="index")


def peak_windows(rh: pd.DataFrame) -> dict:
    """Busiest hours per day type (high-traffic time windows)."""
    out = {}
    for dt, g in rh.groupby("day_type"):
        curve = g.groupby("hour")["ridership"].sum() / g["date"].nunique()
        out[dt] = {"top_hours": curve.nlargest(4).index.tolist(),
                   "peak_hour": int(curve.idxmax()), "peak_boardings": float(curve.max()),
                   "daily_total": float(curve.sum())}
    return out


def iqr_outliers(rh: pd.DataFrame) -> dict:
    """IQR rule on daily ridership per route: share of route-days outside [Q1-1.5IQR, Q3+1.5IQR]."""
    daily = rh.groupby(["route_id", "date"])["ridership"].sum().reset_index()
    q = daily.groupby("route_id")["ridership"].quantile([0.25, 0.75]).unstack()
    daily = daily.join(q, on="route_id")
    iqr = daily[0.75] - daily[0.25]
    out = (daily["ridership"] < daily[0.25] - 1.5 * iqr) | (daily["ridership"] > daily[0.75] + 1.5 * iqr)
    top_dates = daily[out].groupby("date").size().nlargest(10)
    return {"route_days": int(len(daily)), "outlier_route_days": int(out.sum()),
            "outlier_share": float(out.mean()),
            "dates_with_most_outliers": {str(k.date()): int(v) for k, v in top_dates.items()}}


def fig_hourly_curves(rh: pd.DataFrame) -> str:
    """Line chart of average network boardings by hour for Weekday / Saturday / Sunday."""
    fig, ax = plt.subplots(figsize=(9, 4.5))
    for dt, g in rh.groupby("day_type"):
        curve = g.groupby("hour")["ridership"].sum() / g["date"].nunique()
        ax.plot(curve.index, curve.values / 1000, marker="o", ms=3, lw=2, label=dt, color=PALETTE.get(dt))
    ax.set(title="Network hourly ridership curve by day type", xlabel="Hour of day (NYC local)",
           ylabel="Avg boardings (thousands)", xticks=range(0, 24, 2))
    ax.legend()
    return _save(fig, "eda_hourly_ridership_curve.png")


def fig_daily_trend(rh: pd.DataFrame) -> str:
    """Daily network ridership with 7-day rolling mean and holiday markers."""
    daily = rh.groupby("date")["ridership"].sum() / 1e6
    fig, ax = plt.subplots(figsize=(11, 4))
    ax.plot(daily.index, daily.values, color="#93c5fd", lw=1, label="Daily")
    ax.plot(daily.index, daily.rolling(7, center=True).mean(), color="#1d4ed8", lw=2.2, label="7-day rolling mean")
    hol = rh.loc[rh["is_holiday"] == 1, "date"].unique()
    for h in hol:
        ax.axvline(h, color="#ef4444", alpha=.25, lw=1)
    ax.set(title="Daily network ridership (red lines = public holidays)", ylabel="Boardings (millions)")
    ax.legend()
    return _save(fig, "eda_daily_trend.png")


def fig_dow_box(rh: pd.DataFrame) -> str:
    """Box plot of daily network ridership per day of week."""
    daily = rh.groupby(["date", "dow"])["ridership"].sum().reset_index()
    daily["day"] = daily["dow"].map(dict(enumerate(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])))
    fig, ax = plt.subplots(figsize=(8, 4))
    sns.boxplot(data=daily, x="day", y=daily["ridership"] / 1e6, ax=ax, color="#60a5fa",
                order=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])
    ax.set(title="Daily ridership distribution by day of week", ylabel="Boardings (millions)", xlabel="")
    return _save(fig, "eda_day_of_week_box.png")


def fig_route_heatmap(rh: pd.DataFrame, top: int = 40) -> str:
    """Route x hour heatmap of mean weekday boardings for the busiest routes."""
    wk = rh[rh["day_type"] == "Weekday"]
    mat = wk.pivot_table(index="route_id", columns="hour", values="ridership", aggfunc="mean")
    mat = mat.loc[mat.sum(axis=1).nlargest(top).index]
    fig, ax = plt.subplots(figsize=(12, 10))
    sns.heatmap(mat, cmap="YlOrRd", ax=ax, cbar_kws={"label": "Avg boardings / hour"})
    ax.set(title=f"Route density heatmap - top {top} routes, weekdays", xlabel="Hour of day", ylabel="Route")
    return _save(fig, "eda_route_density_heatmap.png")


def fig_occupancy_distribution(rh: pd.DataFrame) -> str:
    """Histogram of estimated occupancy with the class thresholds."""
    occ = rh["occupancy"].dropna().clip(upper=2)
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.hist(occ, bins=80, color="#6366f1", alpha=.85)
    ax.axvline(THRESHOLDS['underutilized_max'], color="#64748b", ls="--", label=f"Underutilized < {THRESHOLDS['underutilized_max']:.3f}")
    ax.axvline(THRESHOLDS['overcrowded_min'], color="#ef4444", ls="--", label=f"Overcrowded > {THRESHOLDS['overcrowded_min']:.3f}")
    ax.set(title="Distribution of estimated occupancy (route-hours with service)",
           xlabel="Estimated max-load / capacity", ylabel="Route-hours")
    ax.legend()
    return _save(fig, "eda_occupancy_distribution.png")


def fig_class_by_hour(rh: pd.DataFrame) -> str:
    """Stacked bar chart of performance-class shares by hour (weekdays)."""
    wk = rh[(rh["day_type"] == "Weekday") & rh["perf_class"].notna()]
    share = pd.crosstab(wk["hour"], wk["perf_class"], normalize="index")[CLASS_LABELS]
    fig, ax = plt.subplots(figsize=(10, 4))
    share.plot(kind="bar", stacked=True, ax=ax, color=[PALETTE[c] for c in CLASS_LABELS], width=.85)
    ax.set(title="Performance class share by hour (weekdays)", xlabel="Hour", ylabel="Share of route-hours")
    ax.legend(loc="upper right", fontsize=8)
    return _save(fig, "eda_class_share_by_hour.png")


def fig_correlation(profiles: pd.DataFrame) -> tuple[str, dict]:
    """Spearman correlation heatmap of route KPIs; returns (figure path, matrix)."""
    cols = ["avg_daily_ridership", "daily_trips", "mean_occupancy", "productivity", "mean_speed_mph",
            "length_mi", "stop_density", "reliability", "weekend_ratio", "am_peak_share", "transfer_rate"]
    corr = profiles[cols].corr(method="spearman")
    fig, ax = plt.subplots(figsize=(9, 7.5))
    sns.heatmap(corr, annot=True, fmt=".2f", cmap="RdBu_r", center=0, ax=ax, annot_kws={"size": 7})
    ax.set(title="Spearman correlation of route KPIs")
    return _save(fig, "eda_kpi_correlation.png"), corr.round(3).to_dict()


def fig_borough_type(profiles: pd.DataFrame) -> str:
    """Daily ridership by borough and median productivity by route type."""
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    b = profiles.groupby("borough")["avg_daily_ridership"].sum().sort_values() / 1000
    b.plot(kind="barh", ax=axes[0], color="#0ea5e9")
    axes[0].set(title="Avg daily ridership by borough", xlabel="Boardings (thousands)", ylabel="")
    t = profiles.groupby("route_type")["productivity"].median().sort_values()
    t.plot(kind="barh", ax=axes[1], color="#8b5cf6")
    axes[1].set(title="Median productivity by route type", xlabel="Boardings / revenue hour", ylabel="")
    return _save(fig, "eda_borough_and_type.png")


def fig_productivity_rank(profiles: pd.DataFrame, n: int = 15) -> str:
    """Top-N and bottom-N routes by productivity (boardings per vehicle-hour)."""
    p = profiles.set_index("route_id")["productivity"]
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    p.nlargest(n).sort_values().plot(kind="barh", ax=axes[0], color="#16a34a")
    axes[0].set(title=f"Top {n} most productive routes", xlabel="Boardings / revenue hour")
    p.nsmallest(n).sort_values(ascending=False).plot(kind="barh", ax=axes[1], color="#dc2626")
    axes[1].set(title=f"Bottom {n} (underutilised) routes", xlabel="Boardings / revenue hour")
    return _save(fig, "eda_productivity_top_bottom.png")


def fig_speed_vs_load(profiles: pd.DataFrame) -> str:
    """Bubble chart of route speed vs mean occupancy (bubble = daily ridership)."""
    fig, ax = plt.subplots(figsize=(8, 5))
    sns.scatterplot(data=profiles, x="mean_speed_mph", y="mean_occupancy", hue="route_type",
                    size="avg_daily_ridership", sizes=(15, 300), alpha=.7, ax=ax)
    ax.set(title="Speed vs crowding (bubble = daily ridership)", xlabel="Mean speed (mph)",
           ylabel="Mean occupancy")
    ax.legend(fontsize=7, loc="upper right")
    return _save(fig, "eda_speed_vs_occupancy.png")


def fig_overlap(overlap: pd.DataFrame, n: int = 15) -> str | None:
    """Bar chart of the most overlapping route pairs (stop-set Jaccard)."""
    if overlap.empty:
        return None
    top = overlap.head(n).copy()
    top["pair"] = top["route_a"] + " ↔ " + top["route_b"]
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.barh(top["pair"][::-1], top["jaccard"][::-1], color="#f97316")
    ax.set(title="Most overlapping route pairs (stop-set Jaccard)", xlabel="Jaccard similarity")
    return _save(fig, "eda_route_overlap.png")


def run_eda(rh: pd.DataFrame, profiles: pd.DataFrame, overlap: pd.DataFrame, cleaning_report: dict) -> dict:
    """Execute the full EDA and persist figures + JSON summary."""
    figs = {
        "hourly_curve": fig_hourly_curves(rh),
        "daily_trend": fig_daily_trend(rh),
        "dow_box": fig_dow_box(rh),
        "route_heatmap": fig_route_heatmap(rh),
        "occupancy_distribution": fig_occupancy_distribution(rh),
        "class_by_hour": fig_class_by_hour(rh),
        "borough_type": fig_borough_type(profiles),
        "productivity_rank": fig_productivity_rank(profiles),
        "speed_vs_load": fig_speed_vs_load(profiles),
        "overlap": fig_overlap(overlap),
    }
    figs["correlation"], corr = fig_correlation(profiles)
    underused = profiles[(profiles["pct_hours_underutilized"] > 0.6)].sort_values("productivity")
    summary = {
        "granularity": "hourly (route x clock-hour, America/New_York); daily values = sum of hours",
        "rows": int(len(rh)), "routes": int(rh["route_id"].nunique()),
        "date_range": [str(rh["date"].min().date()), str(rh["date"].max().date())],
        "days": int(rh["date"].nunique()),
        "total_boardings": float(rh["ridership"].sum()),
        "descriptive_stats": descriptive_stats(rh),
        "peak_windows": peak_windows(rh),
        "iqr_outliers": iqr_outliers(rh),
        "class_distribution": rh["perf_class"].value_counts(normalize=True).round(4).to_dict(),
        "underutilized_routes": underused["route_id"].head(25).tolist(),
        "top_overlaps": overlap.head(15).to_dict(orient="records"),
        "spearman_correlation": corr,
        "cleaning_report": cleaning_report,
        "figures": figs,
    }
    (EDA_DIR / "eda_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    return summary


def main() -> None:
    """Run the complete EDA and print where the outputs were written."""
    rh, profiles, overlap, rep = load_inputs()
    summary = run_eda(rh, profiles, overlap, rep)
    print(f"EDA complete: {len([f for f in summary['figures'].values() if f])} figures in {FIGURES_DIR}")
    print(f"Summary: {EDA_DIR / 'eda_summary.json'}")
    for dt, v in summary["peak_windows"].items():
        print(f"  {dt:8s} peak hour {v['peak_hour']:02d}:00  ~{v['peak_boardings']:,.0f} boardings/hour")


if __name__ == "__main__":
    main()
