"""RouteRanker - FRONTEND (single main file, Streamlit).

All user-interface code lives here: shared UI helpers (theme, IST clock, IST date/time
picker, scoring-weight picker, route map) and the 11 dashboard pages:

  Overview       Network Overview · Best Route Today (Live)
  Analysis       Productivity Ranking · Route Comparison · Historical Replay · EDA Insights
  Optimisation   Scenario Simulator · Optimisation Actions
  Models & Data  Model Performance · Data & Coverage · Pipeline & Architecture

The pages call the backend service layer (``backend/main.py``: RouteRankerService,
optimiser, simulator, GTFS analyser) and read EDA outputs from ``eda/``.

Usage (from the project root, after ``python backend/main.py train`` and ``python eda/main.py``):
    streamlit run frontend/main.py          # http://localhost:8501
"""
from __future__ import annotations

import json
import sys
import textwrap
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend import main as C  # noqa: E402  (backend module doubles as the config namespace C.*)
from backend.main import (COMPONENTS, PRESETS, RouteRankerService, analyse_gtfs, ist_to_transit,  # noqa: E402
                          latest_timestamp, now_ist, simulate_scenario)


# ====================================================================================================
# SHARED UI HELPERS
# ====================================================================================================
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
                 "`python backend/main.py train` and then `python eda/main.py` (from the project root).")
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

# ====================================================================================================
# PAGE: Network Overview
# ====================================================================================================
def page_network_overview():
    """Network Overview page."""
    setup_page("Network Overview", "Live health of the bus network - segments, crowding and today's forecast (all times IST).")
    svc = require_service()
    ri = svc.route_info
    n = now_ist()
    local = ist_to_transit(n)
    today = svc.predict_day(local.date())

    c = st.columns(5)
    c[0].metric("Routes modelled", f"{len(ri):,}")
    c[1].metric("Avg daily boardings", f"{ri['avg_daily_ridership'].sum() / 1e6:.2f} M")
    c[2].metric("Forecast boardings today", f"{today['ridership'].sum() / 1e6:.2f} M",
                help=f"Forecast for {local:%a %d %b} (network local date) generated {fmt_ist(n)}")
    svc_hours = today[today["trips"] > 0]
    c[3].metric("Overcrowded route-hours today", f"{(svc_hours['pred_class'] == 'Overcrowded').mean():.1%}")
    c[4].metric("Underutilised route-hours today", f"{(svc_hours['pred_class'] == 'Underutilized').mean():.1%}")
    st.caption(f"Data window {svc.data_start:%d %b %Y} → {svc.data_end:%d %b %Y} · models built {svc.manifest['built_at_ist']} · "
               f"forecast generated {fmt_ist(n)}")

    left, right = st.columns([1.7, 1])
    with left:
        color_opt = st.radio("Colour routes by", ["Route segment (KMeans)", "Today's predicted status", "Borough",
                                                   "Route type"], horizontal=True)
        if color_opt.startswith("Route segment"):
            cmap = dict(zip(ri["route_id"], ri["cluster_name"]))
        elif color_opt.startswith("Today"):
            dom = (today[today["trips"] > 0].groupby("route_id")["pred_class"]
                   .agg(lambda s: "Overcrowded" if (s == "Overcrowded").mean() > .15 else
                        ("Underutilized" if (s == "Underutilized").mean() > .5 else "Balanced")))
            cmap = dom.to_dict()
        elif color_opt == "Borough":
            cmap = dict(zip(ri["route_id"], ri["borough"]))
        else:
            cmap = dict(zip(ri["route_id"], ri["route_type"]))
        st.plotly_chart(route_map(svc, cmap, height=540), width="stretch")
    with right:
        seg = ri.groupby("cluster_name").agg(routes=("route_id", "count"),
                                             daily_riders=("avg_daily_ridership", "sum"),
                                             productivity=("productivity", "median"),
                                             occupancy=("mean_occupancy", "median")).reset_index()
        st.markdown("**Route segments (KMeans)**")
        st.dataframe(seg.sort_values("daily_riders", ascending=False), hide_index=True, width="stretch",
                     column_config={"daily_riders": st.column_config.NumberColumn(format="%d"),
                                    "productivity": st.column_config.NumberColumn("riders/veh-h", format="%.0f"),
                                    "occupancy": st.column_config.ProgressColumn(min_value=0, max_value=1, format="%.2f")})
        b = ri.groupby("borough")["avg_daily_ridership"].sum().reset_index()
        st.plotly_chart(px.pie(b, names="borough", values="avg_daily_ridership", hole=.55,
                               title="Daily ridership by borough").update_layout(height=300, margin=dict(t=40, b=0)),
                        width="stretch")

    st.subheader(f"Today's network forecast - {local:%A %d %b %Y} (local)")
    curve = today.groupby("hour").agg(ridership=("ridership", "sum")).reset_index()
    curve["IST time"] = [(pd.Timestamp(local.date()) + pd.Timedelta(hours=h)).tz_localize("America/New_York")
                         .tz_convert("Asia/Kolkata").strftime("%d %b %I %p") for h in curve["hour"]]
    fig = px.area(curve, x="hour", y="ridership", hover_data=["IST time"], labels={"hour": "Hour (network local)"})
    fig.add_vline(x=local.hour, line_dash="dash", line_color="red", annotation_text="now")
    if "ridership_actual" in today:
        act = today.groupby("hour")["ridership_actual"].sum().reset_index()
        fig.add_scatter(x=act["hour"], y=act["ridership_actual"], name="Actual", mode="lines+markers")
    st.plotly_chart(fig.update_layout(height=320), width="stretch")

    cls = today[today["trips"] > 0].groupby(["hour", "pred_class"]).size().reset_index(name="route_hours")
    st.plotly_chart(px.bar(cls, x="hour", y="route_hours", color="pred_class", color_discrete_map=CLASS_COLORS,
                           title="Predicted performance class by hour (classifier)").update_layout(height=320),
                    width="stretch")


# ====================================================================================================
# PAGE: Best Route Today (Live)
# ====================================================================================================
def page_best_route():
    """Best Route Today (Live) page."""
    setup_page("Best Route Today", "Real-time / date-specific prediction of the best bus route, why it wins, "
                                   "and validation against the alternatives.", "🏆")
    svc = require_service()
    ri = svc.route_info

    dt_ist, local, hours = date_hour_picker(svc, "best")

    st.markdown("##### Which routes should compete?")
    mode = st.radio("Candidate set", ["Journey: from stop A to stop B", "Borough / route type", "Hand-pick routes"],
                    horizontal=True, label_visibility="collapsed")
    candidates = None
    if mode.startswith("Journey"):
        c1, c2 = st.columns(2)
        o = c1.text_input("Origin stop / street contains", "FLATBUSH AV")
        d = c2.text_input("Destination stop / street contains", "ATLANTIC AV")
        pairs = svc.find_routes_between(o, d) if o and d else pd.DataFrame()
        if pairs.empty:
            st.warning("No direct route serves both places - try a broader street name (e.g. 'BROADWAY', "
                       "'MAIN ST', '125 ST').")
            st.stop()
        candidates = pairs["route_id"].tolist()
        with st.expander(f"{len(candidates)} direct routes found"):
            st.dataframe(pairs, hide_index=True, width="stretch")
    elif mode.startswith("Borough"):
        c1, c2 = st.columns(2)
        boro = c1.multiselect("Borough", sorted(ri["borough"].unique()), default=["Manhattan"])
        rtype = c2.multiselect("Route type", sorted(ri["route_type"].unique()), default=sorted(ri["route_type"].unique()))
        candidates = ri[ri["borough"].isin(boro or ri["borough"].unique()) & ri["route_type"].isin(rtype)]["route_id"].tolist()
    else:
        candidates = st.multiselect("Routes", svc.routes, default=svc.routes[:6], format_func=svc.route_label)
    if not candidates or len(candidates) < 2:
        st.info("Select at least two candidate routes.")
        st.stop()

    weights = weight_picker("best")


    @st.fragment(run_every=300 if dt_ist.date() == now_ist().date() else None)
    def results():
        gen = now_ist()
        pred = svc.predict_day(local.date())
        rank = svc.rank_routes(pred, hours, weights, candidates)
        if rank.empty:
            st.warning("None of the candidate routes runs in this time window.")
            return
        top = rank.iloc[0]
        st.markdown(f"<div class='rr-card rr-win'><span class='rr-pill'>BEST ROUTE</span>"
                    f"<span class='rr-pill'>{top['route_type']}</span><span class='rr-pill'>{top['borough']}</span>"
                    f"<h2 style='margin:.3rem 0'>🚌 {top['route_id']} - {top['route_long_name']}</h2>"
                    f"RouteRank score <b>{top['score']:.1f}/100</b> · window {hours[0]:02d}:00–{hours[1] + 1:02d}:00 local "
                    f"· forecast generated <b>{fmt_ist(gen)}</b></div>", unsafe_allow_html=True)
        m = st.columns(6)
        m[0].metric("Predicted riders (window)", f"{top['riders']:,.0f}")
        m[1].metric("Productivity", f"{top['productivity']:.0f}/veh-h")
        m[2].metric("Avg speed", f"{top['speed']:.1f} mph")
        m[3].metric("Reliability", f"{top['reliability']:.0%}")
        m[4].metric("Avg wait", f"{top['avg_wait_min']:.1f} min")
        m[5].metric("P(not crowded)", f"{top['comfort']:.0%}")

        t1, t2, t3, t4 = st.tabs(["💡 Why it's the best", "📊 Compare with alternatives", "⏱️ Hourly forecast",
                                  "✅ Validation (back-test)"])
        with t1:
            for line in svc.explain(rank, weights):
                st.markdown(line)
            st.plotly_chart(route_map(svc, {r: ("Best" if r == top["route_id"] else "Alternative") for r in candidates},
                                      highlight=candidates[:40], height=380), width="stretch")
        with t2:
            show = rank.head(12)
            fig = go.Figure()
            for i, (_, r) in enumerate(show.head(5).iterrows()):
                fig.add_trace(go.Scatterpolar(r=[r[f"{c}_pct"] for c in COMPONENTS] + [r[f"{COMPONENTS[0]}_pct"]],
                                              theta=[c.title() for c in COMPONENTS] + [COMPONENTS[0].title()],
                                              fill="toself" if i == 0 else None, name=r["route_id"],
                                              line=dict(color=SEQ[i], width=3 if i == 0 else 1.5)))
            fig.update_layout(polar=dict(radialaxis=dict(range=[0, 100])), height=420,
                              title="Percentile profile - top 5 (higher is better)")
            c1, c2 = st.columns([1, 1.2])
            c1.plotly_chart(fig, width="stretch")
            bar = px.bar(show, x="score", y="route_id", orientation="h", color="score", color_continuous_scale="Viridis",
                         hover_data=["route_long_name", "riders", "productivity", "speed", "reliability"],
                         title="RouteRank score")
            c2.plotly_chart(bar.update_layout(yaxis=dict(autorange="reversed"), height=420), width="stretch")
            st.dataframe(rank[["rank", "route_id", "route_long_name", "score", "riders", "productivity", "speed",
                               "reliability", "frequency", "avg_wait_min", "mean_occupancy", "comfort"]],
                         hide_index=True, width="stretch",
                         column_config={"score": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.1f"),
                                        "riders": st.column_config.NumberColumn(format="%d"),
                                        "productivity": st.column_config.NumberColumn(format="%.0f"),
                                        "speed": st.column_config.NumberColumn("mph", format="%.1f"),
                                        "reliability": st.column_config.NumberColumn(format="%.2f"),
                                        "frequency": st.column_config.NumberColumn("buses/h", format="%.1f"),
                                        "avg_wait_min": st.column_config.NumberColumn("wait min", format="%.1f"),
                                        "mean_occupancy": st.column_config.NumberColumn("load", format="%.2f"),
                                        "comfort": st.column_config.NumberColumn("P(not crowded)", format="%.2f")})
        with t3:
            top5 = rank["route_id"].head(5).tolist()
            p = pred[pred["route_id"].isin(top5)].copy()
            p["IST"] = [(pd.Timestamp(local.date()) + pd.Timedelta(hours=h)).tz_localize("America/New_York")
                        .tz_convert("Asia/Kolkata").strftime("%d %b %I:%M %p") for h in p["hour"]]
            fig = px.line(p, x="hour", y="ridership", color="route_id", markers=True, hover_data=["IST", "trips", "occupancy"],
                          title="Forecast boardings per hour (network local hour; hover shows IST)")
            fig.add_vrect(x0=hours[0] - .5, x1=hours[1] + .5, fillcolor="green", opacity=.08, line_width=0)
            if "ridership_actual" in p:
                for i, rid in enumerate(top5):
                    a = p[p["route_id"] == rid]
                    fig.add_scatter(x=a["hour"], y=a["ridership_actual"], mode="markers", name=f"{rid} actual",
                                    marker=dict(symbol="x", color=SEQ[i]))
            st.plotly_chart(fig, width="stretch")
            fig2 = px.line(p, x="hour", y="occupancy", color="route_id", title="Predicted occupancy (load / capacity)")
            fig2.add_hline(y=0.85, line_dash="dash", line_color="red", annotation_text="overcrowded")
            fig2.add_hline(y=0.25, line_dash="dash", line_color="gray", annotation_text="underutilised")
            st.plotly_chart(fig2, width="stretch")
        with t4:
            st.caption("For the previous same-weekday dates in the historical data, all candidates are re-scored using "
                       "ACTUAL ridership. A good recommendation keeps a top rank on real data, and the forecast error "
                       "for the recommended route should be small.")
            v = svc.validate(top["route_id"], local.date(), hours, candidates, weights)
            if v.empty:
                st.info("No comparable historical dates available.")
            else:
                k = st.columns(4)
                k[0].metric("Weeks checked", len(v))
                k[1].metric("Median rank on actuals", f"{v['rank_on_actuals'].median():.0f} / {v['candidates'].iloc[0]}")
                k[2].metric("Top-3 hit rate", f"{(v['rank_on_actuals'] <= 3).mean():.0%}")
                k[3].metric("Mean abs % error", f"{v['abs_pct_error'].mean():.1f}%")
                st.dataframe(v, hide_index=True, width="stretch")
                st.plotly_chart(px.bar(v, x="date", y=["predicted_riders", "actual_riders"], barmode="group",
                                       title=f"{top['route_id']}: predicted vs actual riders in the window"),
                                width="stretch")


    results()


# ====================================================================================================
# PAGE: Productivity Ranking
# ====================================================================================================
def page_productivity_ranking():
    """Productivity Ranking page."""
    setup_page("Productivity Ranking", "League table of routes - boardings per vehicle-hour, crowding, speed and "
                                       "reliability, for any date (IST).", "📈")
    svc = require_service()
    ri = svc.route_info

    basis = st.radio("Ranking basis", ["Forecast for a selected date", "Historical average (whole data window)"],
                     horizontal=True)
    c1, c2 = st.columns(2)
    boro = c1.multiselect("Borough filter", sorted(ri["borough"].unique()))
    rtype = c2.multiselect("Route-type filter", sorted(ri["route_type"].unique()))
    mask = ri["borough"].isin(boro or ri["borough"].unique()) & ri["route_type"].isin(rtype or ri["route_type"].unique())
    cand = ri.loc[mask, "route_id"].tolist()

    if basis.startswith("Forecast"):
        dt_ist, local, hours = date_hour_picker(svc, "prod")
        weights = weight_picker("prod")
        pred = svc.predict_day(local.date())
        rank = svc.rank_routes(pred, hours, weights, cand)
        val_col, val_name = "productivity", "Boardings per vehicle-hour"
    else:
        rank = ri[ri["route_id"].isin(cand)].copy()
        rank["score"] = (rank["productivity"].rank(pct=True) * 40 + rank["mean_speed_mph"].rank(pct=True) * 20 +
                         rank["reliability"].rank(pct=True) * 20 + (1 - rank["pct_hours_overcrowded"]).rank(pct=True) * 20)
        rank = rank.sort_values("score", ascending=False)
        rank["rank"] = range(1, len(rank) + 1)
        val_col, val_name = "productivity", "Boardings per vehicle-hour"

    n = st.slider("Show top / bottom N", 5, 40, 15)
    a, b = st.columns(2)
    a.plotly_chart(px.bar(rank.nlargest(n, val_col), x=val_col, y="route_id", orientation="h", color="route_type",
                          title=f"🟢 Most productive - {val_name}").update_layout(yaxis=dict(autorange="reversed"), height=480),
                   width="stretch")
    b.plotly_chart(px.bar(rank.nsmallest(n, val_col), x=val_col, y="route_id", orientation="h", color="route_type",
                          title=f"🔴 Least productive - {val_name}").update_layout(yaxis=dict(autorange="reversed"), height=480),
                   width="stretch")

    if basis.startswith("Forecast"):
        fig = px.scatter(rank, x="productivity", y="comfort", size="riders", color="borough", hover_name="route_id",
                         hover_data=["route_long_name", "score"], title="Efficiency vs comfort (bubble = predicted riders)")
        st.plotly_chart(fig, width="stretch")
        cols = ["rank", "route_id", "route_long_name", "borough", "route_type", "cluster_name", "score", "riders",
                "productivity", "speed", "reliability", "frequency", "mean_occupancy", "comfort"]
    else:
        fig = px.scatter(rank, x="productivity", y="mean_occupancy", size="avg_daily_ridership", color="cluster_name",
                         hover_name="route_id", title="Productivity vs average occupancy (bubble = daily riders)")
        st.plotly_chart(fig, width="stretch")
        cols = ["rank", "route_id", "route_long_name", "borough", "route_type", "cluster_name", "score",
                "avg_daily_ridership", "productivity", "mean_speed_mph", "reliability", "mean_occupancy",
                "pct_hours_overcrowded", "pct_hours_underutilized", "trend_4w_pct"]
    st.dataframe(rank[cols], hide_index=True, width="stretch", height=520,
                 column_config={"score": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.1f")})
    st.download_button("⬇️ Download ranking (CSV)", rank[cols].to_csv(index=False), "routeranker_ranking.csv", "text/csv")


# ====================================================================================================
# PAGE: Route Comparison
# ====================================================================================================
def page_route_comparison():
    """Route Comparison page."""
    setup_page("Route Comparison", "Side-by-side comparison of 2-6 routes: forecasts, crowding, speed, "
                                   "reliability and history.", "⚖️")
    svc = require_service()
    ri = svc.route_info.set_index("route_id")

    default = [r for r in ["M15+", "M15", "B46", "BX12+", "Q58"] if r in svc.routes][:3] or svc.routes[:3]
    sel = st.multiselect("Routes to compare", svc.routes, default=default, max_selections=6, format_func=svc.route_label)
    if len(sel) < 2:
        st.info("Pick at least two routes.")
        st.stop()
    dt_ist, local, hours = date_hour_picker(svc, "cmp")
    pred = svc.predict_day(local.date(), None)
    p = pred[pred["route_id"].isin(sel)]
    rank = svc.rank_routes(pred, hours, None, sel)

    st.subheader("Key indicators")
    kp = ri.loc[sel, ["route_long_name", "route_type", "borough", "cluster_name", "length_mi", "n_stops",
                      "avg_daily_ridership", "productivity", "mean_speed_mph", "reliability", "mean_occupancy",
                      "pct_hours_overcrowded", "pct_hours_underutilized", "weekend_ratio", "trend_4w_pct"]]
    num = kp.select_dtypes("number").columns
    kp[num] = kp[num].round(2)
    st.dataframe(kp.T.astype(str), width="stretch")

    c1, c2 = st.columns(2)
    fig = go.Figure()
    for i, (_, r) in enumerate(rank.iterrows()):
        fig.add_trace(go.Scatterpolar(r=[r[f"{c}_pct"] for c in COMPONENTS] + [r[f"{COMPONENTS[0]}_pct"]],
                                      theta=[c.title() for c in COMPONENTS] + [COMPONENTS[0].title()],
                                      name=f"{r['route_id']} ({r['score']:.0f})", line=dict(color=SEQ[i % 8])))
    fig.update_layout(title="Score components for the window (rank among selected)", height=420,
                      polar=dict(radialaxis=dict(range=[0, 100])))
    c1.plotly_chart(fig, width="stretch")
    c2.plotly_chart(route_map(svc, {r: r for r in sel}, highlight=sel, height=420), width="stretch")

    c1, c2 = st.columns(2)
    c1.plotly_chart(px.line(p, x="hour", y="ridership", color="route_id", markers=True,
                            title=f"Forecast boardings - {local:%a %d %b}"), width="stretch")
    c2.plotly_chart(px.line(p, x="hour", y="occupancy", color="route_id", markers=True,
                            title="Predicted occupancy").add_hline(y=.85, line_dash="dash", line_color="red"),
                    width="stretch")
    c1, c2 = st.columns(2)
    c1.plotly_chart(px.line(p, x="hour", y="speed_mph", color="route_id", title="Expected speed by hour (mph)"),
                    width="stretch")
    c2.plotly_chart(px.bar(p, x="hour", y="trips", color="route_id", barmode="group",
                           title="Scheduled buses per hour"), width="stretch")

    st.subheader("Historical behaviour")
    h = svc.history[svc.history["route_id"].isin(sel)]
    daily = h.groupby(["route_id", "date"])["ridership"].sum().reset_index()
    daily["7-day avg"] = daily.groupby("route_id")["ridership"].transform(lambda s: s.rolling(7, min_periods=1).mean())
    st.plotly_chart(px.line(daily, x="date", y="7-day avg", color="route_id", title="Daily ridership (7-day average)"),
                    width="stretch")
    dow = h.groupby(["route_id", "dow"])["ridership"].sum() / h.groupby(["route_id", "dow"])["date"].nunique()
    dow = dow.reset_index(name="avg_riders")
    dow["day"] = dow["dow"].map(dict(enumerate(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])))
    c1, c2 = st.columns(2)
    c1.plotly_chart(px.bar(dow, x="day", y="avg_riders", color="route_id", barmode="group",
                           title="Average daily riders by weekday"), width="stretch")
    cls = h.dropna(subset=["perf_class"]).groupby(["route_id", "perf_class"]).size().reset_index(name="n")
    cls["share"] = cls["n"] / cls.groupby("route_id")["n"].transform("sum")
    c2.plotly_chart(px.bar(cls, x="route_id", y="share", color="perf_class",
                           color_discrete_map={"Underutilized": "#94a3b8", "Balanced": "#22c55e", "Overcrowded": "#ef4444"},
                           title="Share of service hours by performance class"), width="stretch")


# ====================================================================================================
# PAGE: Historical Replay
# ====================================================================================================
def page_historical_replay():
    """Historical Replay page."""
    setup_page("Historical Replay", "Replay any past day hour by hour - actual boardings and crowding across the "
                                    "network, versus what the model predicted.", "⏪")
    svc = require_service()
    ri = svc.route_info

    d = st.date_input("Day to replay (network local date)", value=svc.data_end.date(),
                      min_value=svc.data_start.date(), max_value=svc.data_end.date())
    day = pd.Timestamp(d)
    pred = svc.predict_day(day)
    if "ridership_actual" not in pred:
        st.warning("No actuals for this date.")
        st.stop()
    pred = pred.dropna(subset=["ridership_actual"])
    c = st.columns(4)
    c[0].metric("Actual boardings", f"{pred['ridership_actual'].sum():,.0f}")
    c[1].metric("Model forecast", f"{pred['ridership'].sum():,.0f}",
                f"{(pred['ridership'].sum() / max(pred['ridership_actual'].sum(), 1) - 1):+.1%}")
    c[2].metric("Route-hour MAE", f"{(pred['ridership'] - pred['ridership_actual']).abs().mean():.1f}")
    svc_h = pred[pred["trips"] > 0]
    c[3].metric("Class accuracy", f"{(svc_h['pred_class'] == svc_h['perf_class_actual']).mean():.1%}")

    m = pred.merge(ri[["route_id", "latitude", "longitude", "route_long_name"]], on="route_id")
    m["IST"] = [(day + pd.Timedelta(hours=h)).tz_localize("America/New_York").tz_convert("Asia/Kolkata")
                .strftime("%d %b %I %p IST") for h in m["hour"]]
    m["status"] = m["perf_class_actual"].fillna("No service")
    m["size"] = m["ridership_actual"].clip(lower=1)
    m = m.sort_values("hour")
    fig = px.scatter_map(m, lat="latitude", lon="longitude", size="size", color="status", animation_frame="hour",
                         hover_name="route_id", hover_data={"route_long_name": True, "ridership_actual": ":.0f",
                                                            "ridership": ":.0f", "IST": True, "size": False},
                         color_discrete_map=CLASS_COLORS, size_max=28, zoom=9.6, height=600,
                         center=dict(lat=40.70, lon=-73.93), map_style="carto-positron",
                         title="Press ▶ to replay: bubble = actual boardings, colour = actual status")
    st.plotly_chart(fig, width="stretch")

    net = pred.groupby("hour")[["ridership_actual", "ridership"]].sum().reset_index()
    st.plotly_chart(px.line(net, x="hour", y=["ridership_actual", "ridership"], markers=True,
                            title="Network boardings: actual vs forecast",
                            labels={"value": "boardings", "variable": ""}), width="stretch")

    hr = st.slider("Inspect hour", 0, 23, 8)
    snap = pred[pred["hour"] == hr].sort_values("ridership_actual", ascending=False)
    st.dataframe(snap[["route_id", "ridership_actual", "ridership", "trips", "occupancy_actual", "perf_class_actual",
                       "pred_class"]].head(40), hide_index=True, width="stretch")


# ====================================================================================================
# PAGE: EDA Insights
# ====================================================================================================
def page_eda_insights():
    """EDA Insights page."""
    setup_page("EDA Insights", "Exploratory data analysis - high-traffic windows, density heatmaps, distributions, "
                               "correlations, outliers and overlaps.", "🔍")
    svc = require_service()
    eda_file = C.EDA_DIR / "eda_summary.json"
    if not eda_file.exists():
        st.warning("EDA outputs not found - run `python eda/main.py`.")
        st.stop()
    eda = json.loads((C.EDA_DIR / "eda_summary.json").read_text())
    h = svc.history

    k = st.columns(4)
    k[0].metric("Route-hour records", f"{eda['rows']:,}")
    k[1].metric("Days", eda["days"])
    k[2].metric("Total boardings", f"{eda['total_boardings'] / 1e6:,.1f} M")
    k[3].metric("IQR outlier route-days", f"{eda['iqr_outliers']['outlier_share']:.1%}")
    st.caption(f"Granularity: {eda['granularity']} · {eda['date_range'][0]} → {eda['date_range'][1]}")

    tabs = st.tabs(["Temporal patterns", "Route density", "Distributions", "Correlation", "Overlap & under-use",
                    "Statistics", "Static figures"])
    with tabs[0]:
        curve = h.groupby(["day_type", "hour"])["ridership"].sum() / h.groupby(["day_type", "hour"])["date"].nunique()
        st.plotly_chart(px.line(curve.reset_index(name="avg"), x="hour", y="avg", color="day_type", markers=True,
                                title="Hourly ridership curve by day type"), width="stretch")
        pw = pd.DataFrame(eda["peak_windows"]).T
        st.dataframe(pw, width="stretch")
        daily = h.groupby("date")["ridership"].sum().reset_index()
        daily["7-day mean"] = daily["ridership"].rolling(7, center=True).mean()
        st.plotly_chart(px.line(daily, x="date", y=["ridership", "7-day mean"], title="Daily network ridership"),
                        width="stretch")
    with tabs[1]:
        dt = st.radio("Day type", ["Weekday", "Saturday", "Sunday"], horizontal=True)
        top = st.slider("Routes", 10, 80, 35)
        sub = h[h["day_type"] == dt]
        mat = sub.pivot_table(index="route_id", columns="hour", values="ridership", aggfunc="mean")
        mat = mat.loc[mat.sum(axis=1).nlargest(top).index]
        st.plotly_chart(px.imshow(mat, aspect="auto", color_continuous_scale="YlOrRd", height=24 * top + 120,
                                  title=f"Route density heatmap ({dt})"), width="stretch")
    with tabs[2]:
        smp = h.dropna(subset=["occupancy"]).sample(min(200000, len(h)), random_state=1)
        f = px.histogram(smp, x=smp["occupancy"].clip(upper=2), nbins=80, color="perf_class",
                         title="Occupancy distribution (sample)")
        st.plotly_chart(f, width="stretch")
        st.plotly_chart(px.box(svc.route_info, x="route_type", y="productivity", color="route_type", points="all",
                               hover_name="route_id", title="Productivity by route type"), width="stretch")
    with tabs[3]:
        corr = pd.DataFrame(eda["spearman_correlation"])
        st.plotly_chart(px.imshow(corr, text_auto=".2f", color_continuous_scale="RdBu_r", zmin=-1, zmax=1,
                                  title="Spearman correlation of route KPIs", height=620), width="stretch")
    with tabs[4]:
        st.markdown("**Most overlapping route pairs (stop-set Jaccard)**")
        st.dataframe(pd.DataFrame(eda["top_overlaps"]), hide_index=True, width="stretch")
        st.markdown("**Routes underutilised in > 60 % of service hours**")
        u = svc.route_info[svc.route_info["route_id"].isin(eda["underutilized_routes"])]
        st.dataframe(u[["route_id", "route_long_name", "avg_daily_ridership", "productivity", "mean_occupancy",
                        "pct_hours_underutilized"]], hide_index=True, width="stretch")
    with tabs[5]:
        st.dataframe(pd.DataFrame(eda["descriptive_stats"]).T, width="stretch")
        st.json(eda["iqr_outliers"])
        st.json(eda["cleaning_report"], expanded=False)
    with tabs[6]:
        figs = [v for v in eda["figures"].values() if v]
        for i in range(0, len(figs), 2):
            cols = st.columns(2)
            for c, f in zip(cols, figs[i:i + 2]):
                c.image(str(ROOT / f), width="stretch")


# ====================================================================================================
# PAGE: Scenario Simulator
# ====================================================================================================
def page_scenario_simulator():
    """Scenario Simulator page."""
    setup_page("Scenario Simulator", "What-if analysis: change demand, frequency, speed (bus lanes) or vehicle size "
                                     "and compare current vs simulated route loads.", "🧪")
    svc = require_service()
    ri = svc.route_info

    dt_ist, local, _ = date_hour_picker(svc, "sim", show_hours=False)
    pred = svc.predict_day(local.date())

    with st.form("scenario"):
        c1, c2 = st.columns([1.4, 1])
        scope = c1.radio("Apply to", ["Selected routes", "A borough", "Whole network"], horizontal=True)
        routes = c1.multiselect("Routes", svc.routes, default=[r for r in ["B46", "M15", "BX12"] if r in svc.routes],
                                format_func=svc.route_label)
        boro = c1.selectbox("Borough", sorted(ri["borough"].unique()))
        hours = c2.slider("Hours (network local)", 0, 23, (6, 20))
        demand = c2.slider("Demand change %", -50, 100, 15, 5)
        freq = c2.slider("Frequency multiplier", 0.25, 3.0, 1.25, 0.05)
        speed = c2.slider("Speed change % (e.g. bus lane)", -30, 50, 0, 5)
        cap = c2.selectbox("Vehicle", ["Unchanged", "Standard 40-ft (65)", "Articulated 60-ft (95)", "Coach (57)"])
        st.form_submit_button("▶ Run simulation", type="primary")

    sel = routes if scope == "Selected routes" else (
        ri.loc[ri["borough"] == boro, "route_id"].tolist() if scope == "A borough" else None)
    cap_val = {"Unchanged": None, "Standard 40-ft (65)": 65, "Articulated 60-ft (95)": 95, "Coach (57)": 57}[cap]
    sim = simulate_scenario(pred, demand, freq, speed, cap_val, sel, hours)
    s = sim[sim["in_scenario"] & (sim["trips"] > 0)]
    if s.empty:
        st.warning("No scheduled service for this selection.")
        st.stop()


    def share(col, cls):
        return (s[col] == cls).mean()


    k = st.columns(5)
    k[0].metric("Riders", f"{s['ridership_sim'].sum():,.0f}", f"{s['ridership_sim'].sum() - s['ridership'].sum():+,.0f}")
    k[1].metric("Bus trips", f"{s['trips_sim'].sum():,.0f}", f"{s['trips_sim'].sum() - s['trips'].sum():+,.0f}")
    k[2].metric("Overcrowded hours", f"{share('perf_class_sim', 'Overcrowded'):.1%}",
                f"{(share('perf_class_sim', 'Overcrowded') - share('perf_class', 'Overcrowded')) * 100:+.1f} pp",
                delta_color="inverse")
    k[3].metric("Avg wait", f"{s['avg_wait_min_sim'].mean():.1f} min",
                f"{s['avg_wait_min_sim'].mean() - s['avg_wait_min'].mean():+.1f}", delta_color="inverse")
    k[4].metric("Vehicle-hours", f"{s['revenue_hours_sim'].sum():,.0f}",
                f"{s['revenue_hours_sim'].sum() - s['revenue_hours'].sum():+,.0f}", delta_color="inverse")

    hr = s.groupby("hour")[["occupancy", "occupancy_sim"]].mean().reset_index()
    fig = go.Figure([go.Scatter(x=hr["hour"], y=hr["occupancy"], name="Current", line=dict(color="#64748b", width=3)),
                     go.Scatter(x=hr["hour"], y=hr["occupancy_sim"], name="Simulated", line=dict(color="#f97316", width=3))])
    fig.add_hline(y=.85, line_dash="dash", line_color="red", annotation_text="overcrowded")
    fig.add_hline(y=.25, line_dash="dash", line_color="gray", annotation_text="underutilised")
    fig.update_layout(title="Current vs simulated mean occupancy by hour", height=380)
    st.plotly_chart(fig, width="stretch")

    c1, c2 = st.columns(2)
    dist = (s.melt(value_vars=["perf_class", "perf_class_sim"], var_name="scenario", value_name="class")
            .replace({"perf_class": "Current", "perf_class_sim": "Simulated"}))
    c1.plotly_chart(px.histogram(dist, x="scenario", color="class", barnorm="percent", color_discrete_map=CLASS_COLORS,
                                 title="Route-hour class mix"), width="stretch")
    r = s.groupby("route_id").agg(now=("occupancy", "max"), sim=("occupancy_sim", "max")).reset_index().nlargest(25, "now")
    c2.plotly_chart(px.bar(r, x="route_id", y=["now", "sim"], barmode="group",
                           title="Peak occupancy per route: current vs simulated"), width="stretch")
    st.dataframe(s[["route_id", "hour", "ridership", "ridership_sim", "trips", "trips_sim", "occupancy", "occupancy_sim",
                    "perf_class", "perf_class_sim", "avg_wait_min", "avg_wait_min_sim"]],
                 hide_index=True, width="stretch", height=360)


# ====================================================================================================
# PAGE: Optimisation Actions
# ====================================================================================================
def page_recommendations():
    """Optimisation Actions page."""
    setup_page("Optimisation Actions", "Model-driven recommendations: frequency changes, merges and splits, with "
                                       "current vs optimised loads.", "🛠️")
    svc = require_service()

    dt_ist, local, _ = date_hour_picker(svc, "rec", show_hours=False)
    opt, rec, imp = svc.recommendations(local.date())

    k = st.columns(5)
    k[0].metric("Overcrowded route-hours", f"{imp['overcrowded_share_opt']:.1%}",
                f"{(imp['overcrowded_share_opt'] - imp['overcrowded_share_now']) * 100:+.1f} pp", delta_color="inverse")
    k[1].metric("Underutilised route-hours", f"{imp['underutilized_share_opt']:.1%}",
                f"{(imp['underutilized_share_opt'] - imp['underutilized_share_now']) * 100:+.1f} pp", delta_color="inverse")
    k[2].metric("Balanced route-hours", f"{imp['balanced_share_opt']:.1%}",
                f"{(imp['balanced_share_opt'] - imp['balanced_share_now']) * 100:+.1f} pp")
    k[3].metric("Vehicle-hours", f"{imp['veh_hours_opt']:,.0f}", f"{imp['veh_hours_opt'] - imp['veh_hours_now']:+,.0f}",
                delta_color="inverse")
    k[4].metric("Productivity", f"{imp['productivity_opt']:.0f}/veh-h", f"{imp['productivity_opt'] - imp['productivity_now']:+.1f}")

    acts = rec["action"].str.split(" \\+ ").explode().str.replace(r"Merge with .*", "Merge", regex=True)
    c1, c2 = st.columns([1, 1.6])
    c1.plotly_chart(px.pie(acts.value_counts().reset_index(), names="action", values="count", hole=.5,
                           title="Recommended actions"), width="stretch")
    hr = opt[opt["trips"] > 0].groupby("hour")[["trips", "trips_opt"]].sum().reset_index()
    fig = go.Figure([go.Bar(x=hr["hour"], y=hr["trips"], name="Current schedule", marker_color="#94a3b8"),
                     go.Bar(x=hr["hour"], y=hr["trips_opt"], name="Optimised", marker_color="#2563eb")])
    c2.plotly_chart(fig.update_layout(title="Network trips per hour: current vs optimised", barmode="group"),
                    width="stretch")

    flt = st.multiselect("Filter actions", sorted(acts.unique()))
    show = rec if not flt else rec[rec["action"].str.contains("|".join(flt))]
    st.dataframe(show[["route_id", "action", "rationale", "priority", "ridership", "trips_now", "trips_opt", "trips_added",
                       "trips_removed", "peak_occupancy_now", "peak_occupancy_opt", "productivity_now",
                       "productivity_opt", "cluster_name"]],
                 hide_index=True, width="stretch", height=460,
                 column_config={"rationale": st.column_config.TextColumn(width="large"),
                                "ridership": st.column_config.NumberColumn("pred riders", format="%d"),
                                "peak_occupancy_now": st.column_config.NumberColumn(format="%.2f"),
                                "peak_occupancy_opt": st.column_config.NumberColumn(format="%.2f"),
                                "productivity_now": st.column_config.NumberColumn(format="%.0f"),
                                "productivity_opt": st.column_config.NumberColumn(format="%.0f")})
    st.download_button("⬇️ Download action plan (CSV)", show.to_csv(index=False), "routeranker_actions.csv")

    st.subheader("Drill into a route")
    rid = st.selectbox("Route", rec["route_id"], format_func=svc.route_label)
    o = opt[opt["route_id"] == rid]
    c1, c2 = st.columns(2)
    c1.plotly_chart(px.bar(o, x="hour", y=["trips", "trips_opt"], barmode="group", title=f"{rid}: trips per hour"),
                    width="stretch")
    f2 = px.line(o, x="hour", y=["occupancy", "occupancy_opt"], markers=True, title=f"{rid}: occupancy current vs optimised")
    c2.plotly_chart(f2.add_hline(y=.85, line_dash="dash", line_color="red"), width="stretch")

    st.subheader("Overlapping route pairs (merge screening)")
    st.dataframe(svc.overlap.head(40), hide_index=True, width="stretch")


# ====================================================================================================
# PAGE: Model Performance
# ====================================================================================================
def page_model_performance():
    """Model Performance page."""
    setup_page("Model Performance", "Clustering (KMeans, DBSCAN), classification (Random Forest vs XGBoost) and "
                                    "forecasting (XGBoost vs Random Forest vs baseline).", "🤖")
    svc = require_service()
    M = svc.metrics
    ri = svc.route_info

    t1, t2, t3 = st.tabs(["🧩 Clustering", "🏷️ Classification", "📉 Forecasting"])
    with t1:
        km, db = M["clustering"]["kmeans"], M["clustering"]["dbscan"]
        k = st.columns(5)
        k[0].metric("KMeans k", km["k"]); k[1].metric("Silhouette", f"{km['silhouette']:.3f}")
        k[2].metric("Davies-Bouldin", f"{km['davies_bouldin']:.3f}")
        k[3].metric("DBSCAN clusters", db["n_clusters"]); k[4].metric("DBSCAN outlier routes", db["n_outliers"])
        ks = pd.DataFrame(M["clustering"]["k_selection"])
        c1, c2 = st.columns(2)
        c1.plotly_chart(px.line(ks, x="k", y=["silhouette"], markers=True, title="Silhouette vs k"), width="stretch")
        c2.plotly_chart(px.line(ks, x="k", y="inertia", markers=True, title="Elbow - inertia vs k"), width="stretch")
        st.plotly_chart(px.scatter(ri, x="pc1", y="pc2", color="cluster_name", symbol=ri["dbscan_outlier"].map({0: "core", 1: "DBSCAN outlier"}),
                                   hover_name="route_id", size="avg_daily_ridership", height=520,
                                   title="Route segments in PCA space (symbol = DBSCAN outlier)"), width="stretch")
        prof = ri.groupby("cluster_name")[["avg_daily_ridership", "productivity", "mean_occupancy", "mean_speed_mph",
                                           "am_peak_share", "weekend_ratio", "length_mi", "reliability"]].median()
        st.dataframe(prof.style.background_gradient(axis=0, cmap="Blues"), width="stretch")
        st.markdown("**DBSCAN outliers (atypical routes)**: " + ", ".join(ri.loc[ri["dbscan_outlier"] == 1, "route_id"]))
    with t2:
        cl = M["classification"]
        st.success(f"Selected model: **{cl['best']}** (highest macro-F1 on the {C.VALIDATION_DAYS}-day hold-out).")
        rows = [{"model": m, "accuracy": cl[m]["accuracy"], "balanced_accuracy": cl[m]["balanced_accuracy"],
                 "f1_macro": cl[m]["f1_macro"], "f1_weighted": cl[m]["f1_weighted"], "train_rows": cl[m]["train_rows"],
                 "train_seconds": cl[m]["train_seconds"]} for m in ("RandomForest", "XGBoost")]
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        c1, c2 = st.columns(2)
        for c, m in zip((c1, c2), ("RandomForest", "XGBoost")):
            cm = pd.DataFrame(cl[m]["confusion_matrix"], index=C.CLASS_LABELS, columns=C.CLASS_LABELS)
            c.plotly_chart(px.imshow(cm.div(cm.sum(axis=1), axis=0), text_auto=".2f", color_continuous_scale="Blues",
                                     title=f"{m} - normalised confusion matrix", labels=dict(x="Predicted", y="Actual")),
                           width="stretch")
            c.dataframe(pd.DataFrame(cl[m]["report"]).T.round(3), width="stretch")
        imp = pd.Series(cl["feature_importance"][cl["best"]]).head(20).reset_index()
        imp.columns = ["feature", "importance"]
        st.plotly_chart(px.bar(imp, x="importance", y="feature", orientation="h", title="Feature importance")
                        .update_layout(yaxis=dict(autorange="reversed"), height=520), width="stretch")
    with t3:
        fc = M["forecasting"]
        st.success(f"Selected model: **{fc['best']}** (lowest MAE on the hold-out).")
        rows = [{"model": m, **{k: fc[m][k] for k in ("mae", "rmse", "r2", "wape")}}
                for m in ("SeasonalProfileBaseline", "RandomForest", "XGBoost")]
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        vp = pd.read_parquet(C.PROCESSED_DIR / "validation_predictions.parquet")
        rid = st.selectbox("Route", sorted(vp["route_id"].unique()), format_func=svc.route_label)
        r = vp[vp["route_id"] == rid]
        st.plotly_chart(px.line(r, x="ts", y=["ridership", "pred"], title=f"{rid}: validation actual vs forecast"),
                        width="stretch")
        net = vp.groupby("ts")[["ridership", "pred"]].sum().reset_index()
        st.plotly_chart(px.line(net, x="ts", y=["ridership", "pred"], title="Network: validation actual vs forecast"),
                        width="stretch")
        imp = pd.Series(fc["feature_importance"][fc["best"]]).head(20).reset_index()
        imp.columns = ["feature", "importance"]
        st.plotly_chart(px.bar(imp, x="importance", y="feature", orientation="h", title="Forecaster feature importance")
                        .update_layout(yaxis=dict(autorange="reversed"), height=520), width="stretch")
        for f in ("forecast_fit", "forecast_comparison"):
            if f in M["figures"]:
                st.image(str(ROOT / M["figures"][f]), width="stretch")


# ====================================================================================================
# PAGE: Data & Coverage
# ====================================================================================================
def page_data_coverage():
    """Data & Coverage page."""
    setup_page("Data & Coverage", "Where the data comes from, how complete it is, how fresh it is - and analyse "
                                  "your own GTFS feed.", "📂")
    svc = require_service()
    man = svc.manifest

    st.subheader("Data sources")
    src = pd.DataFrame(man["sources"]).T.reset_index(names="key")
    src["rows pulled"] = src["key"].map({"ridership": man["raw_rows"].get("ridership"),
                                         "schedules": man["raw_rows"].get("tph"),
                                         "segment_speeds": man["raw_rows"].get("seg"),
                                         "route_speeds": man["raw_rows"].get("monthly"),
                                         "wait_assessment": man["raw_rows"].get("wait"),
                                         "routes": man["raw_rows"].get("routes"), "stops": man["raw_rows"].get("stops")})
    st.dataframe(src[["name", "id", "granularity", "role", "rows pulled", "url"]], hide_index=True, width="stretch",
                 column_config={"url": st.column_config.LinkColumn("link")})
    st.info(f"**Granularity: HOURLY.** Core table = boardings per route per clock hour "
            f"({man['route_hours']:,} route-hours, {man['routes']} routes, {man['data_start']} → {man['data_end']}). "
            "Daily values are sums of hours.")

    c1, c2 = st.columns([1, 1])
    with c1:
        st.subheader("Freshness")
        if st.button("🔄 Check data.ny.gov for newer data"):
            lt = latest_timestamp()
            if lt is None:
                st.warning("API not reachable (offline?).")
            else:
                st.write(f"Latest published hour: **{lt}** (New York) · our model data ends **{man['last_timestamp_local']}**")
                if lt > pd.Timestamp(man["last_timestamp_local"]):
                    st.warning("Newer data is available - run `python backend/main.py train` to retrain.")
                else:
                    st.success("Models are up to date.")
        st.write(f"Models built: **{man['built_at_ist']}** · checked {fmt_ist(now_ist())}")
        st.json(man["assumptions"], expanded=False)
    with c2:
        st.subheader("Route coverage map")
        st.plotly_chart(route_map(svc, dict(zip(svc.route_info["route_id"], svc.route_info["borough"])), height=360),
                        width="stretch")

    st.subheader("Completeness")
    h = svc.history
    cov = h.groupby(["route_id", pd.Grouper(key="date", freq="W")])["ridership"].apply(lambda s: (s > 0).mean()).reset_index()
    mat = cov.pivot(index="route_id", columns="date", values="ridership")
    st.plotly_chart(px.imshow(mat, aspect="auto", color_continuous_scale="Greens", height=900,
                              title="Share of hours with recorded boardings (route x week)"), width="stretch")
    b = svc.route_info.groupby(["borough", "route_type"]).size().reset_index(name="routes")
    st.plotly_chart(px.bar(b, x="borough", y="routes", color="route_type", title="Routes by borough and type"),
                    width="stretch")

    st.divider()
    st.subheader("📤 Analyse your own GTFS feed")
    st.caption("Upload any GTFS .zip (e.g. Lepton Software feeds for Delhi, Bengaluru, Mumbai, Hyderabad, Pune ...). "
               "Required: routes.txt, trips.txt, stop_times.txt, stops.txt; optional calendar.txt, frequencies.txt, shapes.txt.")
    up = st.file_uploader("GTFS zip", type="zip")
    if up:
        with st.spinner("Parsing GTFS and clustering routes ..."):
            try:
                res = analyse_gtfs(up.getvalue())
            except Exception as e:  # noqa: BLE001
                st.error(f"Could not parse feed: {e}")
                st.stop()
        p = res["profiles"]
        k = st.columns(4)
        k[0].metric("Routes", len(p)); k[1].metric("KMeans k", res["k"])
        k[2].metric("Silhouette", f"{res['silhouette']:.2f}"); k[3].metric("Overlapping pairs", len(res["overlap"]))
        st.json(res["tables"], expanded=False)
        st.plotly_chart(px.scatter(p, x="route_length_km", y="trips_per_day", color=p["kmeans_cluster"].astype(str),
                                   size="n_stops", hover_name="route_id", hover_data=["route_long_name", "flags"]
                                   if "route_long_name" in p else ["flags"],
                                   title="Uploaded routes - clusters"), width="stretch")
        s = res["stops"]
        st.plotly_chart(px.scatter_map(s, lat="latitude", lon="longitude", color="route_id", hover_name="stop_name",
                                       zoom=10, height=480, map_style="carto-positron").update_layout(showlegend=False),
                        width="stretch")
        st.dataframe(p, hide_index=True, width="stretch")
        st.dataframe(res["overlap"], hide_index=True, width="stretch")


# ====================================================================================================
# PAGE: Pipeline & Architecture
# ====================================================================================================
def page_pipeline_architecture():
    """Pipeline & Architecture page."""
    setup_page("Pipeline & Architecture", "How RouteRanker is built - from raw open data to the dashboard and API.", "🧭")
    svc = require_service()
    figs = svc.metrics["figures"]

    st.subheader("System architecture")
    st.image(str(ROOT / figs["architecture"]), width="stretch")
    st.markdown(textwrap.dedent("""
    **Architecture style:** layered *modular monolith* with a shared service layer and two presentation channels.

    | Layer | Component | Responsibility |
    |---|---|---|
    | Data | `backend/main.py` §1-2 | configuration; SODA/SoQL pulls, server-side aggregation, monthly parquet cache, incremental refresh |
    | Processing | `backend/main.py` §3-5 | cleaning, feature engineering / KPIs, encoding, scaling, time split |
    | EDA | `eda/main.py` | all exploratory analysis -> `eda/figures`, `eda/eda_summary.json` |
    | ML | `backend/main.py` §6-7 | KMeans, DBSCAN, Random Forest, XGBoost (classifier + regressor) |
    | Service | `backend/main.py` §8-12 | optimisation, simulation, prediction, ranking, explanation, validation, GTFS analysis, training pipeline |
    | Backend API | `backend/main.py` §13-14 | FastAPI REST API + command-line interface |
    | Frontend | `frontend/main.py` | UI helpers + 11 Streamlit pages + navigation |
    """))
    st.subheader("ML pipeline")
    st.image(str(ROOT / figs["pipeline"]), width="stretch")
    st.subheader("Last pipeline run")
    t = pd.Series(svc.manifest["stage_seconds"]).reset_index()
    t.columns = ["stage", "seconds"]
    st.plotly_chart(px.bar(t, x="seconds", y="stage", orientation="h", title=f"Stage timings "
                           f"(total {svc.manifest['total_seconds'] / 60:.1f} min, built {svc.manifest['built_at_ist']})")
                    .update_layout(yaxis=dict(autorange="reversed")), width="stretch")
    st.subheader("Model figures")
    for k in ("k_selection", "clusters_pca", "confusion", "importance"):
        if k in figs:
            st.image(str(ROOT / figs[k]), width="stretch")


# ====================================================================================================
# APP ENTRY POINT - navigation
# ====================================================================================================
def run_app() -> None:
    """Configure the page, build the grouped navigation and run the selected page."""
    st.set_page_config(page_title="RouteRanker · AI Transit Route Optimisation", page_icon="🚌", layout="wide",
                       initial_sidebar_state="expanded")
    pages = {
        "Overview": [
            st.Page(page_network_overview, title="Network Overview", icon=":material/map:", url_path="network_overview", default=True),
            st.Page(page_best_route, title="Best Route Today (Live)", icon=":material/emoji_events:", url_path="best_route")
        ],
        "Analysis": [
            st.Page(page_productivity_ranking, title="Productivity Ranking", icon=":material/leaderboard:", url_path="productivity_ranking"),
            st.Page(page_route_comparison, title="Route Comparison", icon=":material/compare_arrows:", url_path="route_comparison"),
            st.Page(page_historical_replay, title="Historical Replay", icon=":material/history:", url_path="historical_replay"),
            st.Page(page_eda_insights, title="EDA Insights", icon=":material/insights:", url_path="eda_insights")
        ],
        "Optimisation": [
            st.Page(page_scenario_simulator, title="Scenario Simulator", icon=":material/science:", url_path="scenario_simulator"),
            st.Page(page_recommendations, title="Optimisation Actions", icon=":material/tune:", url_path="recommendations")
        ],
        "Models & Data": [
            st.Page(page_model_performance, title="Model Performance", icon=":material/model_training:", url_path="model_performance"),
            st.Page(page_data_coverage, title="Data & Coverage", icon=":material/database:", url_path="data_coverage"),
            st.Page(page_pipeline_architecture, title="Pipeline & Architecture", icon=":material/account_tree:", url_path="pipeline_architecture")
        ]
    }
    nav = st.navigation(pages)
    st.sidebar.markdown("### 🚌 RouteRanker")
    st.sidebar.caption("AI-powered public transit route optimisation")
    ist_clock_sidebar()
    nav.run()


if __name__ == "__main__":
    run_app()
