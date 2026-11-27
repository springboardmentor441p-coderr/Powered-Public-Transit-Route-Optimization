"""Shared helpers for the Streamlit frontend: service loading, IST clock, styling, charts."""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from routeranker import config as C  # noqa: E402
from routeranker.inference import PRESETS, RouteRankerService, ist_to_transit, now_ist  # noqa: E402

CLASS_COLORS = {"Underutilized": "#94a3b8", "Balanced": "#22c55e", "Overcrowded": "#ef4444", "No service": "#e2e8f0"}
SEQ = ["#2563eb", "#f97316", "#16a34a", "#a855f7", "#e11d48", "#0891b2", "#ca8a04", "#4f46e5"]

CSS = """
<style>
.block-container {padding-top: 1.4rem; max-width: 1400px;}
div[data-testid="stMetric"] {background: var(--secondary-background-color); border-radius: 12px;
     padding: 12px 16px; border: 1px solid rgba(128,128,128,.18);}
div[data-testid="stMetricValue"] {font-size: 1.6rem;}
.rr-hero {background: linear-gradient(120deg,#1e3a8a 0%,#7e22ce 60%,#be185d 100%); color: white;
     padding: 18px 24px; border-radius: 16px; margin-bottom: 14px;}
.rr-hero h1 {color: white; margin: 0; font-size: 1.9rem;}
.rr-hero p {margin: 4px 0 0 0; opacity: .9;}
.rr-card {border: 1px solid rgba(128,128,128,.25); border-radius: 14px; padding: 14px 18px; margin-bottom: 10px;
     background: var(--secondary-background-color);}
.rr-win {border-left: 6px solid #16a34a;}
.rr-pill {display:inline-block; padding: 2px 10px; border-radius: 999px; font-size: .78rem; font-weight: 600;
     margin-right: 6px; background: rgba(37,99,235,.12); color: #2563eb;}
.rr-clock {font-variant-numeric: tabular-nums; font-size: .95rem;}
</style>
"""


def setup_page(title: str, subtitle: str, icon: str = "🚌"):
    """Inject the CSS theme and render the gradient page header."""
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown(f'<div class="rr-hero"><h1>{icon} {title}</h1><p>{subtitle}</p></div>', unsafe_allow_html=True)


@st.cache_resource(show_spinner="Loading models and data ...")
def get_service() -> RouteRankerService | None:
    """Cached RouteRankerService (None if artefacts are missing)."""
    try:
        return RouteRankerService()
    except FileNotFoundError:
        return None


def require_service() -> RouteRankerService:
    """Return the service or stop the page with instructions to run the pipeline."""
    svc = get_service()
    if svc is None:
        st.error("Trained artefacts not found. Run the pipeline first:\n\n"
                 "`python -m routeranker.pipeline` (from the project root with `PYTHONPATH=src`).")
        st.stop()
    return svc


def fmt_ist(dt: datetime) -> str:
    """Format a datetime in IST, e.g. 'Fri 27 Nov 2026, 05:02 PM IST'."""
    return dt.astimezone(C.IST).strftime("%a %d %b %Y, %I:%M %p IST")


def ist_clock_sidebar():
    """Live IST clock (and network-local time) in the sidebar, refreshed every 30 s."""
    @st.fragment(run_every=30)
    def _clock():
        """Fragment body that renders the clock."""
        n = now_ist()
        st.sidebar.markdown(
            f"<div class='rr-clock'>🕒 <b>{n:%d %b %Y · %I:%M %p}</b> IST<br>"
            f"<span style='opacity:.7'>Network local: {ist_to_transit(n):%d %b %I:%M %p} (New York)</span></div>",
            unsafe_allow_html=True)
    _clock()


def date_hour_picker(svc: RouteRankerService, key: str, default_now: bool = True, show_hours: bool = True):
    """IST date/time picker -> returns (ist datetime, transit-local datetime, hour window)."""
    n = now_ist()
    c1, c2, c3 = st.columns([1.2, 1, 1.6])
    d = c1.date_input("Date (IST)", value=n.date(), key=f"{key}_d",
                      help="Pick today for a real-time forecast, a past date to compare against actuals, "
                           "or a future date for planning.")
    t = c2.time_input("Time (IST)", value=n.time().replace(second=0, microsecond=0), key=f"{key}_t", step=3600)
    dt_ist = datetime.combine(d, t).replace(tzinfo=C.IST)
    local = ist_to_transit(dt_ist)
    hours = (0, 23)
    if show_hours:
        mode = c3.selectbox("Time window", ["Selected hour ±1h", "AM peak (6-10)", "Midday (10-16)",
                                            "PM peak (16-20)", "Evening (20-24)", "Whole service day (5-24)"],
                            key=f"{key}_w")
        h = local.hour
        hours = {"Selected hour ±1h": (max(h - 1, 0), min(h + 1, 23)), "AM peak (6-10)": (6, 9),
                 "Midday (10-16)": (10, 15), "PM peak (16-20)": (16, 19), "Evening (20-24)": (20, 23),
                 "Whole service day (5-24)": (5, 23)}[mode]
    status = ("📡 **Real-time** (today)" if d == n.date() else
              "🔮 **Forecast** (future date)" if pd.Timestamp(local.date()) > svc.data_end else
              "📚 **Historical** (actuals available)" if pd.Timestamp(local.date()) >= svc.data_start else
              "🔮 **Model estimate** (before data window)")
    st.caption(f"{status} · You selected **{fmt_ist(dt_ist)}** → bus-network local time "
               f"**{local:%a %d %b %Y, %I:%M %p}** (America/New_York). Model hours {hours[0]:02d}:00–{hours[1] + 1:02d}:00 local.")
    return dt_ist, local, hours


def weight_picker(key: str) -> C.ScoreWeights:
    """Expander with presets and sliders for the RouteRank score weights."""
    with st.expander("⚖️ Scoring weights (how 'best' is defined)", expanded=False):
        preset = st.radio("Preset", list(PRESETS), horizontal=True, key=f"{key}_preset")
        w = PRESETS[preset]
        cols = st.columns(5)
        vals = {}
        for c, (k, v) in zip(cols, w.as_dict().items()):
            vals[k] = c.slider(k.title(), 0.0, 1.0, float(round(v, 2)), 0.05, key=f"{key}_{preset}_{k}")
        return C.ScoreWeights(**vals)


def route_map(svc: RouteRankerService, color_by: dict[str, str] | None = None, highlight: list[str] | None = None,
              height: int = 560, legend_title: str = "") -> go.Figure:
    """Route lines on an OpenStreetMap basemap (MapLibre). ``color_by`` maps route -> category."""
    info = svc.route_info.set_index("route_id")
    paths = svc.paths
    if highlight:
        paths = paths[paths["route_id"].isin(highlight)]
    fig = go.Figure()
    groups: dict[str, list] = {}
    for _, r in paths.iterrows():
        if not r["path"]:
            continue
        cat = color_by.get(r["route_id"], "Other") if color_by else r["route_id"]
        groups.setdefault(cat, []).append(r)
    palette = {**CLASS_COLORS}
    for i, (cat, rows) in enumerate(sorted(groups.items())):
        lats, lons, texts = [], [], []
        for r in rows:
            pts = json.loads(r["path"])
            lons += [p[0] for p in pts] + [None]
            lats += [p[1] for p in pts] + [None]
            name = info.at[r["route_id"], "route_long_name"] if r["route_id"] in info.index else ""
            texts += [f"{r['route_id']} - {name}"] * len(pts) + [None]
        col = palette.get(cat) or (info.at[cat, "route_color"] if (not color_by and cat in info.index) else SEQ[i % len(SEQ)])
        fig.add_trace(go.Scattermap(lat=lats, lon=lons, mode="lines", line=dict(width=3 if highlight else 1.6, color=col),
                                    name=str(cat), text=texts, hoverinfo="text"))
    fig.update_layout(map=dict(style="carto-positron", center=dict(lat=40.70, lon=-73.93), zoom=9.6),
                      height=height, margin=dict(l=0, r=0, t=0, b=0), legend_title_text=legend_title,
                      legend=dict(bgcolor="rgba(255,255,255,.75)", font=dict(size=10)))
    return fig


def no_data_note():
    """Info box explaining the data window."""
    st.info("Data window: the model is trained on MTA hourly ridership; dates beyond the last published day "
            "are forecasts.")
