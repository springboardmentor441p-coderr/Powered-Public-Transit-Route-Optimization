"""Module 3 - EDA: hourly ridership curves, heatmaps, route-density map, overlap/under-use detection."""
import numpy as np, pandas as pd, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt, seaborn as sns, folium
from folium.plugins import HeatMap
from .config import FIG_DIR, CLASSES

PAL = {"underutilized": "#4c78a8", "balanced": "#54a24b", "overcrowded": "#e45756"}

def hourly_curves(hourly, ax=None, city=None):
    h = hourly if city is None else hourly[hourly.city == city]
    g = h.groupby(["day_type", "hour"]).boardings.sum().reset_index()
    ax = ax or plt.gca()
    for dt, d in g.groupby("day_type"): ax.plot(d.hour, d.boardings / 1000, marker="o", label=dt)
    ax.set(xlabel="Hour of day", ylabel="Boardings (thousands)", title=f"Hourly ridership - {city or 'all cities'}"); ax.legend(); return ax

def city_hour_heatmap_df(hourly):
    p = hourly[hourly.day_type == "weekday"].pivot_table(index="city", columns="hour", values="boardings", aggfunc="sum").fillna(0)
    return p.div(p.sum(axis=1), axis=0)

def underused_overlapping(routes, pairs, min_ratio=0.5):
    """Routes that are underutilized AND share most stops with another route."""
    u = routes[routes.label == "underutilized"].route_uid
    ov = pairs[(pairs.overlap_ratio >= min_ratio) & (pairs.route_a.isin(u) | pairs.route_b.isin(u))]
    return ov.sort_values("overlap_ratio", ascending=False)

def make_figures(bundle, out=FIG_DIR):
    out.mkdir(parents=True, exist_ok=True); r, h = bundle["routes"], bundle["hourly"]; sns.set_theme(style="whitegrid")
    fig, ax = plt.subplots(figsize=(7, 4)); hourly_curves(h, ax); fig.tight_layout(); fig.savefig(out / "hourly_ridership.png", dpi=130); plt.close(fig)
    fig, ax = plt.subplots(figsize=(11, 6)); sns.heatmap(city_hour_heatmap_df(h), cmap="YlOrRd", ax=ax, cbar_kws=dict(label="share of daily boardings"))
    ax.set_title("Weekday demand by city and hour"); fig.tight_layout(); fig.savefig(out / "city_hour_heatmap.png", dpi=130); plt.close(fig)
    fig, ax = plt.subplots(figsize=(11, 4)); sns.countplot(data=r, x="city", hue="label", hue_order=CLASSES, palette=PAL, ax=ax)
    ax.tick_params(axis="x", rotation=60); ax.set_title("Route classes per city"); fig.tight_layout(); fig.savefig(out / "class_distribution.png", dpi=130); plt.close(fig)
    fig, ax = plt.subplots(figsize=(6, 5)); sns.scatterplot(data=r, x="proxy_lf", y="peak_lf", hue="label", hue_order=CLASSES, palette=PAL, ax=ax, s=18)
    ax.set_title("Structural supply/demand proxy vs observed peak load"); fig.tight_layout(); fig.savefig(out / "proxy_vs_peak_lf.png", dpi=130); plt.close(fig)
    fig, ax = plt.subplots(figsize=(7, 5)); sns.heatmap(r[["route_length_km", "trips_per_day", "headway_peak_min", "frac_stops_shared", "daily_boardings", "peak_lf", "avg_lf"]].corr(), annot=True, fmt=".2f", cmap="coolwarm", ax=ax)
    fig.tight_layout(); fig.savefig(out / "correlations.png", dpi=130); plt.close(fig)

def density_map(bundle, city, path):
    s = bundle["stops"][bundle["stops"].city == city]
    m = folium.Map([s.stop_lat.mean(), s.stop_lon.mean()], zoom_start=11, tiles="OpenStreetMap")
    HeatMap(s[["stop_lat", "stop_lon", "est_boardings_day"]].values.tolist(), radius=14, blur=18).add_to(m); m.save(path); return m
