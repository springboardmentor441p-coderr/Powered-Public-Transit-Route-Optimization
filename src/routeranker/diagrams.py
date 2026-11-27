"""Architecture, pipeline and model-result figures (PNG) for the app, README and report."""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import seaborn as sns  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

from . import config as C  # noqa: E402


def _box(ax, x, y, w, h, title, lines, color, title_color="white"):
    """Draw a rounded, titled box with bullet lines (architecture diagram helper)."""
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08",
                                fc=color, ec="none", alpha=.95))
    ax.text(x + w / 2, y + h - 0.18, title, ha="center", va="top", fontsize=9.5, weight="bold", color=title_color)
    for i, ln in enumerate(lines):
        ax.text(x + w / 2, y + h - 0.5 - i * 0.26, ln, ha="center", va="top", fontsize=7.4, color=title_color)


def _arrow(ax, x1, y1, x2, y2, label=None, color="#334155", style="-|>", ls="-"):
    """Draw an arrow between two points with an optional label."""
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=style, mutation_scale=13, color=color,
                                 lw=1.5, linestyle=ls))
    if label:
        ax.text((x1 + x2) / 2, (y1 + y2) / 2 + 0.12, label, ha="center", fontsize=6.8, color="#475569")


def architecture_diagram() -> str:
    """Layered system architecture (data -> processing -> ML -> service -> UI/API)."""
    fig, ax = plt.subplots(figsize=(15, 6.2))
    ax.set_xlim(0, 15.4); ax.set_ylim(-0.1, 6.2); ax.axis("off")
    ax.text(7.7, 6.0, "RouteRanker - System Architecture (layered, modular monolith + REST API)",
            ha="center", fontsize=13, weight="bold", color="#0f172a")
    _box(ax, 0.2, 2.1, 2.2, 2.9, "DATA SOURCES", ["data.ny.gov SODA API", "Hourly ridership", "Schedules (GTFS)",
                                                   "Segment speeds", "Wait assessment", "Routes / Stops / Shapes",
                                                   "User GTFS upload (.zip)"], "#1e3a8a")
    _box(ax, 2.9, 2.1, 2.2, 2.9, "INGESTION", ["data_collection.py", "SoQL server-side", "aggregation", "monthly parquet cache",
                                               "incremental refresh", "manifest.json"], "#1d4ed8")
    _box(ax, 5.6, 2.1, 2.3, 2.9, "PROCESSING", ["cleaning.py", "feature_engineering.py", "eda.py", "preprocessing.py",
                                                "(split, encode, scale)"], "#b45309")
    _box(ax, 8.4, 2.1, 2.4, 2.9, "ML MODELS", ["KMeans + DBSCAN", "(route segments)", "RF / XGBoost classifier",
                                               "(perf. class)", "XGBoost / RF regressor", "(hourly forecast)"], "#7e22ce")
    _box(ax, 11.3, 2.1, 1.9, 2.9, "SERVICE", ["inference.py", "RouteRankerService", "ranking + explain", "validation",
                                              "optimization.py", "simulator"], "#be185d")
    _box(ax, 13.6, 3.65, 1.65, 1.35, "STREAMLIT UI", ["11 pages", "Plotly maps"], "#047857")
    _box(ax, 13.6, 2.1, 1.65, 1.35, "FASTAPI", ["REST /api/*", "JSON"], "#0f766e")
    for x1, x2, lab in [(2.4, 2.9, "raw"), (5.1, 5.6, "parquet"), (7.9, 8.4, "features"), (10.8, 11.3, "models")]:
        _arrow(ax, x1, 3.55, x2, 3.55, lab)
    _arrow(ax, 13.2, 3.9, 13.6, 4.3); _arrow(ax, 13.2, 3.2, 13.6, 2.8)
    # storage layer
    ax.add_patch(FancyBboxPatch((2.9, 0.4), 10.3, 1.1, boxstyle="round,pad=0.02,rounding_size=0.08",
                                fc="#f1f5f9", ec="#94a3b8"))
    ax.text(8.05, 1.22, "STORAGE LAYER", ha="center", fontsize=9, weight="bold", color="#0f172a")
    ax.text(8.05, 0.75, "data/raw/*.parquet   ·   data/processed/*.parquet   ·   models/*.joblib   ·   "
            "reports/metrics/*.json   ·   reports/figures/*.png", ha="center", fontsize=7.8, color="#334155")
    for x in (4.0, 6.75, 9.6, 12.25):
        _arrow(ax, x, 2.1, x, 1.5, style="<|-|>", color="#94a3b8")
    _arrow(ax, 14.4, 2.1, 14.4, 0.12, ls="--", color="#16a34a", style="-")
    _arrow(ax, 14.4, 0.12, 1.3, 0.12, ls="--", color="#16a34a", style="-")
    _arrow(ax, 1.3, 0.12, 1.3, 2.1, ls="--", color="#16a34a")
    ax.text(7.7, -0.05, "user input: date/time (IST), GTFS upload, data refresh", ha="center", fontsize=7.5,
            color="#15803d")
    path = C.FIGURES_DIR / "architecture_diagram.png"
    fig.savefig(path, dpi=150, bbox_inches="tight"); plt.close(fig)
    return str(path.relative_to(C.ROOT_DIR))


def pipeline_diagram() -> str:
    """The 10-stage ML pipeline as a flow chart."""
    steps = [("1. Data\nCollection", "#1e40af"), ("2. Cleaning", "#1d4ed8"), ("3. Feature\nEngineering", "#2563eb"),
             ("4. EDA", "#b45309"), ("5. Pre-\nprocessing", "#d97706"), ("6. Clustering\nKMeans +\nDBSCAN", "#7e22ce"),
             ("7. Classifi-\ncation\nRF / XGBoost", "#9333ea"), ("8. Forecasting\nXGBoost / RF", "#a855f7"),
             ("9. Inference &\nOptimisation", "#be185d"), ("10. Dashboard\n& API", "#047857")]
    fig, ax = plt.subplots(figsize=(15, 3.6))
    ax.set_xlim(0, 15); ax.set_ylim(0, 3.6); ax.axis("off")
    ax.text(7.5, 3.35, "RouteRanker end-to-end ML pipeline (python -m routeranker.pipeline)", ha="center",
            fontsize=12, weight="bold")
    w, gap = 1.3, 0.17
    for i, (t, c) in enumerate(steps):
        x = 0.1 + i * (w + gap)
        ax.add_patch(FancyBboxPatch((x, 1.25), w, 1.3, boxstyle="round,pad=0.02,rounding_size=0.1", fc=c, ec="none"))
        ax.text(x + w / 2, 1.9, t, ha="center", va="center", color="white", fontsize=7.6, weight="bold")
        if i < len(steps) - 1:
            _arrow(ax, x + w, 1.9, x + w + gap, 1.9)
    outs = ["parquet\nper month", "clean\nreport", "route-hour\ntable", "11 figures\n+ JSON", "train/valid\nsplit",
            "segments +\noutliers", "class\nprobabilities", "hourly\nforecast", "ranking +\nactions", "11 pages\n+ REST"]
    for i, o in enumerate(outs):
        ax.text(0.1 + i * (w + gap) + w / 2, 0.75, o, ha="center", va="center", fontsize=7, color="#475569")
    path = C.FIGURES_DIR / "pipeline_diagram.png"
    fig.savefig(path, dpi=150, bbox_inches="tight"); plt.close(fig)
    return str(path.relative_to(C.ROOT_DIR))


def model_figures(cluster_prof: pd.DataFrame, cluster_metrics: dict, clf: dict, reg: dict,
                  val: pd.DataFrame) -> dict[str, str]:
    """K selection, PCA cluster map, confusion matrices, feature importances, forecast fit."""
    out = {}
    ks = pd.DataFrame(cluster_metrics["k_selection"])
    fig, ax = plt.subplots(1, 2, figsize=(11, 3.8))
    ax[0].plot(ks["k"], ks["inertia"], "o-", color="#2563eb"); ax[0].set(title="Elbow (inertia)", xlabel="k")
    ax[1].plot(ks["k"], ks["silhouette"], "o-", color="#16a34a", label="Silhouette")
    ax[1].plot(ks["k"], ks["davies_bouldin"] / ks["davies_bouldin"].max(), "s--", color="#dc2626",
               label="Davies-Bouldin (scaled)")
    ax[1].axvline(cluster_metrics["kmeans"]["k"], color="k", ls=":"); ax[1].legend(fontsize=8)
    ax[1].set(title="Cluster quality vs k", xlabel="k")
    out["k_selection"] = _save(fig, "model_kmeans_k_selection.png")

    fig, ax = plt.subplots(1, 2, figsize=(13, 5))
    sns.scatterplot(data=cluster_prof, x="pc1", y="pc2", hue="cluster_name", ax=ax[0], s=40, palette="tab10")
    ax[0].set(title="KMeans route segments (PCA projection)"); ax[0].legend(fontsize=7)
    sns.scatterplot(data=cluster_prof, x="pc1", y="pc2", hue=cluster_prof["dbscan_outlier"].map({0: "core", 1: "outlier"}),
                    palette={"core": "#94a3b8", "outlier": "#ef4444"}, ax=ax[1], s=40)
    for _, r in cluster_prof[cluster_prof["dbscan_outlier"] == 1].iterrows():
        ax[1].annotate(r["route_id"], (r["pc1"], r["pc2"]), fontsize=6)
    ax[1].set(title="DBSCAN density clusters - outlier routes")
    out["clusters_pca"] = _save(fig, "model_clusters_pca.png")

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.3))
    for a, k in zip(axes, ("RandomForest", "XGBoost")):
        cm = np.array(clf[k]["confusion_matrix"])
        cmn = cm / cm.sum(1, keepdims=True)
        sns.heatmap(cmn, annot=True, fmt=".2f", cmap="Blues", xticklabels=C.CLASS_LABELS,
                    yticklabels=C.CLASS_LABELS, ax=a, cbar=False)
        a.set(title=f"{k} (macro-F1 {clf[k]['f1_macro']:.3f})", xlabel="Predicted", ylabel="Actual")
    out["confusion"] = _save(fig, "model_confusion_matrices.png")

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    for a, (title, imp) in zip(axes, [("Classifier (" + clf["best"] + ")", clf["feature_importance"][clf["best"]]),
                                      ("Forecaster (" + reg["best"] + ")", reg["feature_importance"][reg["best"]])]):
        s = pd.Series(imp).head(15)[::-1]
        a.barh(s.index, s.values, color="#7c3aed"); a.set(title=f"Top features - {title}")
        a.tick_params(axis="y", labelsize=7)
    out["importance"] = _save(fig, "model_feature_importance.png")

    fig, axes = plt.subplots(1, 2, figsize=(13, 4.3))
    net = val.groupby("ts")[["ridership", "pred"]].sum() / 1000
    axes[0].plot(net.index, net["ridership"], lw=1.2, label="Actual", color="#0f172a")
    axes[0].plot(net.index, net["pred"], lw=1.2, label="Forecast", color="#f97316", alpha=.85)
    axes[0].set(title="Validation period - network hourly boardings (thousands)"); axes[0].legend()
    axes[0].tick_params(axis="x", rotation=30, labelsize=7)
    smp = val.sample(min(20000, len(val)), random_state=1)
    axes[1].scatter(smp["ridership"], smp["pred"], s=3, alpha=.25, color="#2563eb")
    m = smp[["ridership", "pred"]].max().max()
    axes[1].plot([0, m], [0, m], "k--", lw=1)
    axes[1].set(title="Route-hour: forecast vs actual", xlabel="Actual", ylabel="Forecast")
    out["forecast_fit"] = _save(fig, "model_forecast_validation.png")

    comp = pd.DataFrame({k: {m: reg[k][m] for m in ("mae", "rmse", "wape")}
                         for k in ("SeasonalProfileBaseline", "RandomForest", "XGBoost")}).T
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.4))
    for a, m in zip(axes, ("mae", "rmse", "wape")):
        a.bar(comp.index, comp[m], color=["#94a3b8", "#22c55e", "#f97316"]); a.set(title=m.upper())
        a.tick_params(axis="x", labelsize=7, rotation=10)
    out["forecast_comparison"] = _save(fig, "model_forecast_comparison.png")
    return out


def _save(fig, name):
    """Save a matplotlib figure to reports/figures and return its relative path."""
    p = C.FIGURES_DIR / name
    fig.tight_layout(); fig.savefig(p, dpi=130); plt.close(fig)
    return str(p.relative_to(C.ROOT_DIR))
