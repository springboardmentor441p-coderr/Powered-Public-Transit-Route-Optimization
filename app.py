"""RouteRanker - Streamlit dashboard for transit planners.  Run: streamlit run app.py"""
import json, tempfile
from pathlib import Path
import numpy as np, pandas as pd, plotly.express as px, plotly.graph_objects as go, streamlit as st
from src.config import *
from src import pipeline, data_loader, eda
from src.optimizer import optimize, DEFAULTS
from src.forecast import apply_scenario

st.set_page_config(page_title="RouteRanker", page_icon="🚌", layout="wide")
NEW_MAP = hasattr(px, "scatter_map")
if not ((OUT_DIR / "routes.csv").exists() and (MODEL_DIR / "routeranker_models.joblib").exists()):   # first start on a fresh server
    with st.spinner("First start: preparing data and training models (about a minute) ..."):
        import train; train.main()
COLORS = {"underutilized": "#4c78a8", "balanced": "#54a24b", "overcrowded": "#e45756"}

def style_map(fig):
    fig.update_layout(**({"map_style": "open-street-map"} if NEW_MAP else {"mapbox_style": "open-street-map"}),
                      margin=dict(l=0, r=0, t=30, b=0), height=520); return fig
scatter_map = px.scatter_map if NEW_MAP else px.scatter_mapbox
density_map = px.density_map if NEW_MAP else px.density_mapbox
line_map = px.line_map if NEW_MAP else px.line_mapbox

@st.cache_resource
def get_models():
    p = MODEL_DIR / "routeranker_models.joblib"; return pipeline.load_art(p) if p.exists() else None

@st.cache_data
def get_demo():
    return pipeline.load_results() if (OUT_DIR / "routes.csv").exists() else None

@st.cache_data
def get_metrics():
    p = OUT_DIR / "metrics.json"; return json.load(open(p)) if p.exists() else None

def run_optimizer(res, params, scen="today"):
    routes, hourly = apply_scenario(res["routes"], res["hourly"], scen)
    recs, impact, city_impact, after = optimize(routes, hourly, res["overlap_pairs"], params)
    return {**res, "routes": routes, "hourly": hourly, "recs": recs, "impact": impact, "city_impact": city_impact, "after_hourly": after}

# ------------------------------------------------------------------ sidebar
st.sidebar.title("🚌 RouteRanker")
st.sidebar.caption("AI-powered public transit route optimisation")
src = st.sidebar.radio("Data source", ["Demo: 23 Indian cities", "Upload GTFS", "Generate a synthetic city"])
st.sidebar.subheader("Optimisation settings")
params = dict(
    capacity=st.sidebar.slider("Bus capacity (passengers)", 30, 120, BUS_CAPACITY, 5),
    target_lf=st.sidebar.slider("Target load factor", 0.4, 1.0, TARGET_LF, 0.05),
    min_tph=st.sidebar.slider("Minimum trips / hour", 1, 6, MIN_TRIPS_PER_HOUR),
    max_tph=st.sidebar.slider("Maximum trips / hour", 8, 40, 20),
    merge_overlap=st.sidebar.slider("Merge: min stop overlap", 0.3, 0.9, 0.5, 0.05),
    split_km=st.sidebar.slider("Split suggestion: route length ≥ (km)", 10, 40, 20))

base = None
if src.startswith("Demo"):
    base = get_demo()
    if base is None: st.error("No results found. Run `python train.py` first."); st.stop()
else:
    art = get_models()
    if art is None: st.error("Models missing. Run `python train.py` first."); st.stop()
    if src == "Upload GTFS":
        city = st.sidebar.text_input("City name", "MyCity")
        z = st.sidebar.file_uploader("GTFS .zip (routes, trips, stop_times, stops, calendar)", type="zip")
        rid = st.sidebar.file_uploader("Optional ridership.csv (route_id, day_type, hour, boardings)", type="csv")
        hist = st.sidebar.file_uploader("Optional past ridership (ridership_history.csv: route_id, month, boardings)", type="csv")
        if st.sidebar.button("Analyse", type="primary") and z is not None:
            try:
                with st.spinner("Cleaning, engineering features, running models ..."):
                    feed = data_loader.read_feed_zip(z)
                    ridership = pd.read_csv(rid) if rid is not None else None
                    hh = pd.read_csv(hist).assign(city=city) if hist is not None else None
                    st.session_state["user"] = pipeline.analyze(pipeline.build_bundle({city: (feed, ridership)}, hh), art)
            except Exception as e: st.sidebar.error(f"Could not process feed: {e}")
    else:
        import importlib.util
        spec = importlib.util.spec_from_file_location("gen", ROOT / "data" / "generate_synthetic_gtfs.py")
        gen = importlib.util.module_from_spec(spec); spec.loader.exec_module(gen)
        city = st.sidebar.selectbox("City", list(gen.CITIES), index=6); seed = st.sidebar.number_input("Random seed", 0, 9999, 123)
        if st.sidebar.button("Generate & analyse", type="primary"):
            with st.spinner("Generating GTFS feed and running models ..."):
                feed, rid = gen.generate_city(city, int(seed))
                hh = gen.generate_history(rid, city, int(seed)).assign(city=city)
                st.session_state["user"] = pipeline.analyze(pipeline.build_bundle({city: (feed, rid)}, hh), art)
    base = st.session_state.get("user")
    if base is None: st.info("Provide a feed in the sidebar and press the button. A sample is in `sample_uploads/`."); st.stop()

SC = {"Today (current demand)": "today", "Next 12 months (forecast average)": "avg", "Busiest forecast month": "peak"}
has_fc = "fc_mult_avg" in base["routes"]
st.sidebar.subheader("Planning horizon")
scen = SC[st.sidebar.radio("Plan service for", list(SC))] if has_fc else "today"
if not has_fc: st.sidebar.caption("Add a ridership history file to unlock forecasting.")
res = run_optimizer(base, params, scen)
cities = sorted(res["routes"].city.unique())
sel = st.sidebar.multiselect("Cities", cities, default=cities)
if not sel: st.warning("Select at least one city."); st.stop()
R = res["routes"][res["routes"].city.isin(sel)]; H = res["hourly"][res["hourly"].city.isin(sel)]
S = res["stops"][res["stops"].city.isin(sel)]; REC = res["recs"][res["recs"].city.isin(sel)]
if "city_impact" in res: CI = res["city_impact"][res["city_impact"].city.isin(sel)]

st.title("RouteRanker – transit route optimisation")
tabs = st.tabs(["📊 Overview", "🔎 EDA", "🧩 Clusters", "🤖 Predictions", "🔮 Forecast", "🛠 Recommendations", "📈 Impact", "🧹 Data quality"])

# ------------------------------------------------------------------ overview
with tabs[0]:
    with st.expander("ℹ️ How to use this site (30 seconds)", expanded=False):
        st.markdown("1. **Pick a city** (sidebar) or upload your own GTFS bus feed.\n2. Choose **what to plan for**: today, or the forecast next 12 months.\n"
                    "3. Open **Recommendations** to see which routes need more buses, fewer buses or merging, and **Impact** for the expected benefit.\n"
                    "4. Download the list as CSV. Every setting (bus size, target crowding, ...) can be changed on the left and results update instantly.")
    c = st.columns(5)
    c[0].metric("Cities", len(sel)); c[1].metric("Routes", len(R))
    c[2].metric("Overcrowded", int((R.pred_class == "overcrowded").sum())); c[3].metric("Underutilized", int((R.pred_class == "underutilized").sum()))
    c[4].metric("Balanced", int((R.pred_class == "balanced").sum()))
    a, b = st.columns(2)
    cnt = R.groupby(["city", "pred_class"]).size().reset_index(name="routes")
    a.plotly_chart(px.bar(cnt, x="city", y="routes", color="pred_class", color_discrete_map=COLORS, title="Predicted route class by city"), width="stretch")
    b.plotly_chart(px.scatter(R, x="avg_lf", y="peak_lf", color="pred_class", color_discrete_map=COLORS, hover_data=["city", "route_short_name"],
                              title="Average vs peak load factor").add_hline(y=OVER_PEAK_LF, line_dash="dot").add_vline(x=UNDER_AVG_LF, line_dash="dot"), width="stretch")
    st.caption(f"Ridership source: **{R.ridership_source.iloc[0]}**. "
               + ("Boardings come from the supplied ridership file." if R.ridership_source.iloc[0] == "observed" else "No ridership supplied: demand is estimated from stop attraction (distance to core × network coverage)."))
    st.subheader("Top 10 priority routes")
    st.dataframe(REC.head(10)[["city", "route_short_name", "pred_class", "action", "detail", "structural_option"]], width="stretch", hide_index=True)

# ------------------------------------------------------------------ EDA
with tabs[1]:
    city = st.selectbox("City for detail views", sel, key="eda_city")
    a, b = st.columns(2)
    g = H[H.city == city].groupby(["day_type", "hour"]).boardings.sum().reset_index()
    a.plotly_chart(px.line(g, x="hour", y="boardings", color="day_type", markers=True, title=f"Hourly ridership curve – {city}"), width="stretch")
    hm = eda.city_hour_heatmap_df(H); b.plotly_chart(px.imshow(hm, aspect="auto", color_continuous_scale="YlOrRd", title="Share of weekday boardings by hour"), width="stretch")
    s = S[S.city == city]
    st.plotly_chart(style_map(density_map(s, lat="stop_lat", lon="stop_lon", z="est_boardings_day", radius=18, zoom=10, title=f"Route / stop density heat-map – {city}")), width="stretch")
    st.subheader("Overlapping & under-used routes")
    pairs = res["overlap_pairs"]; pairs = pairs[pairs.city == city] if len(pairs) else pairs
    ov = eda.underused_overlapping(R[R.city == city], pairs, 0.5) if len(pairs) else pairs
    nm = R.set_index("route_uid").route_short_name
    if len(ov):
        ov = ov.assign(route_a=ov.route_a.map(nm), route_b=ov.route_b.map(nm))[["route_a", "route_b", "shared_stops", "overlap_ratio", "jaccard"]]
        st.dataframe(ov.round(2), width="stretch", hide_index=True)
    else: st.write("No underused route pairs with ≥50 % stop overlap in this city.")

# ------------------------------------------------------------------ clusters
with tabs[2]:
    a, b = st.columns(2)
    a.plotly_chart(px.scatter(R, x="pca1", y="pca2", color="kmeans_cluster", hover_data=["city", "route_short_name"], title="KMeans route clusters (PCA projection)"), width="stretch")
    R2 = R.assign(dbscan=R.dbscan_cluster.map(lambda x: "noise / outlier" if x == -1 else f"cluster {x}"))
    b.plotly_chart(px.scatter(R2, x="pca1", y="pca2", color="dbscan", hover_data=["city", "route_short_name"], title="DBSCAN clusters & outliers"), width="stretch")
    prof = R.groupby("kmeans_cluster").agg(routes=("route_uid", "size"), boardings_day=("daily_boardings", "mean"), avg_lf=("avg_lf", "mean"),
                                           peak_lf=("peak_lf", "mean"), trips_day=("trips_per_day", "mean"), length_km=("route_length_km", "mean")).round(2)
    st.subheader("Cluster profiles"); st.dataframe(prof, width="stretch")
    m = get_metrics()
    if m: st.caption(f"KMeans k={m['clustering']['k']} (silhouette {m['clustering']['kmeans_silhouette']:.2f}); DBSCAN eps={m['clustering']['dbscan_eps']:.2f}, {m['clustering']['dbscan_clusters']} clusters, {m['clustering']['dbscan_noise_frac']:.0%} outliers.")

# ------------------------------------------------------------------ predictions
with tabs[3]:
    m = get_metrics()
    if m:
        best = m["best"]; st.subheader(f"Classifier comparison (best: {best.replace('_', ' ')})")
        rows = [{"model": k, "CV accuracy": v["grouped_cv"]["accuracy"], "CV macro-F1": v["grouped_cv"]["macro_f1"], "Val macro-F1": v["stratified_val"]["macro_f1"],
                 "Unseen-city macro-F1": v.get("unseen_cities", {}).get("macro_f1")} for k, v in m["classifier"].items()]
        st.dataframe(pd.DataFrame(rows).round(3), hide_index=True, width="stretch")
        a, b = st.columns(2)
        cm = np.array(m["classifier"][best]["grouped_cv"]["confusion"])
        a.plotly_chart(px.imshow(cm, x=CLASSES, y=CLASSES, text_auto=True, color_continuous_scale="Blues", labels=dict(x="Predicted", y="Actual"), title="Confusion matrix (city-grouped CV)"), width="stretch")
        fi = pd.Series(m["feature_importance"]).sort_values()
        b.plotly_chart(px.bar(fi, orientation="h", title="Top feature importances"), width="stretch")
    st.subheader("Route predictions")
    f = st.multiselect("Filter predicted class", CLASSES, default=["overcrowded", "underutilized"])
    cols = ["city", "route_short_name", "route_long_name", "pred_class", "confidence", "label", "peak_lf", "avg_lf", "trips_per_day", "route_length_km"]
    st.dataframe(R[R.pred_class.isin(f)][cols].sort_values("confidence", ascending=False).round(2), width="stretch", hide_index=True)

# ------------------------------------------------------------------ forecast
with tabs[4]:
    FC, HI = res.get("forecast"), res.get("history")
    if FC is None or HI is None or len(FC) == 0:
        st.info("No forecast available: provide past monthly ridership (file `ridership_history.csv`) to forecast future demand.")
    else:
        FC = FC[FC.city.isin(sel)]; HI = HI[HI.city.isin(sel)]; fm = (get_metrics() or {}).get("forecast")
        st.markdown("The model **learns from past monthly ridership** (trend, seasonality, city-wide patterns) and predicts the **next 12 months** for every route. "
                    "Those forecasts then drive the *Recommendations* and *Impact* tabs when you pick a future planning horizon in the sidebar.")
        if fm:
            c = st.columns(4); c[0].metric("Forecast error (WAPE)", f"{fm['model']['wape']:.1%}", f"{(fm['model']['wape'] - fm['seasonal_naive_drift']['wape']) * 100:+.1f} pts vs best baseline", delta_color="inverse")
            c[1].metric("Naive 'same as last 3 months'", f"{fm['naive_last3']['wape']:.1%}"); c[2].metric("Past months used for the test", fm["train_months"]); c[3].metric("80% interval coverage", f"{fm['interval80_coverage']:.0%}")
            st.caption(f"Honest backtest: trained only on the first {fm['train_months']} months, then predicted the next {fm['test_months']} months it had never seen. WAPE = total absolute error ÷ total riders.")
        city = st.selectbox("City", sel, key="fc_city")
        hc = HI[HI.city == city].groupby("month").boardings.sum().reset_index(); fc = FC[FC.city == city].groupby("month").forecast.sum().reset_index()
        f = go.Figure(); f.add_scatter(x=pd.to_datetime(hc.month + "-01"), y=hc.boardings, name="Past (actual)")
        f.add_scatter(x=pd.to_datetime(fc.month + "-01"), y=fc.forecast, name="Forecast", line=dict(dash="dash"))
        bt = res.get("backtest_city")
        if bt is not None and city in set(bt.city):
            b = bt[bt.city == city]; f.add_scatter(x=pd.to_datetime(b.month + "-01"), y=b.model, name="Backtest prediction (made from older data)", line=dict(dash="dot"))
        f.update_layout(title=f"Weekday boardings per day, all routes – {city}", yaxis_title="Boardings / weekday"); st.plotly_chart(f, width="stretch")
        nm = R.set_index("route_uid").route_short_name
        ropts = R[R.city == city].route_uid.tolist()
        ru = st.selectbox("Route", ropts, format_func=lambda u: nm.get(u, u), key="fc_route")
        hr, fr = HI[HI.route_uid == ru], FC[FC.route_uid == ru]
        g = go.Figure(); g.add_scatter(x=pd.to_datetime(hr.month + "-01"), y=hr.boardings, name="Past")
        g.add_scatter(x=pd.to_datetime(fr.month + "-01"), y=fr.hi, line=dict(width=0), showlegend=False)
        g.add_scatter(x=pd.to_datetime(fr.month + "-01"), y=fr.lo, fill="tonexty", line=dict(width=0), name="80% range")
        g.add_scatter(x=pd.to_datetime(fr.month + "-01"), y=fr.forecast, name="Forecast", line=dict(dash="dash"))
        g.update_layout(title=f"{nm.get(ru, ru)} – next 12 months", yaxis_title="Boardings / weekday"); st.plotly_chart(g, width="stretch")
        st.subheader("Routes expected to get busier or become overcrowded")
        Q = R.copy(); Q["class_now"] = Q.route_uid.map(base["routes"].set_index("route_uid").pred_class)
        if "class_avg" in Q:
            Q["class_next12_avg"] = Q.route_uid.map(base["routes"].set_index("route_uid").class_avg); Q["class_at_peak_month"] = Q.route_uid.map(base["routes"].set_index("route_uid").class_peak)
            risk = Q[(Q.class_at_peak_month == "overcrowded") & (Q.class_now != "overcrowded")]
            st.metric("Routes that will become overcrowded at the forecast peak if service stays unchanged", len(risk))
            st.dataframe(Q.sort_values("fc_growth_pct", ascending=False).head(25)[["city", "route_short_name", "fc_growth_pct", "fc_peak_month", "class_now", "class_next12_avg", "class_at_peak_month"]].round(1), hide_index=True, width="stretch")

# ------------------------------------------------------------------ recommendations
with tabs[5]:
    acts = st.multiselect("Action", sorted(REC.action.unique()), default=[a for a in sorted(REC.action.unique()) if a != "No change"])
    T = REC[REC.action.isin(acts)]
    cols = ["city", "route_short_name", "pred_class", "action", "detail", "structural_option", "trips_day_before", "trips_day_after",
            "peak_headway_before_min", "peak_headway_after_min", "delta_bus_km"]
    st.dataframe(T[cols].round(1), width="stretch", hide_index=True)
    st.download_button("⬇ Download recommendations (CSV)", T.to_csv(index=False), "route_recommendations.csv", "text/csv")
    st.subheader("Route drill-down")
    opts = T.route_uid.tolist() or REC.route_uid.tolist()
    ru = st.selectbox("Route", opts, format_func=lambda u: f"{R.set_index('route_uid').route_short_name.get(u, u)} – {u.split('|')[0]}")
    rr = R.set_index("route_uid").loc[ru]; rec = REC.set_index("route_uid").loc[ru]
    a, b = st.columns(2)
    hh = H[(H.route_uid == ru) & (H.day_type == "weekday")].sort_values("hour")
    aft = res["after_hourly"]; unit = res["after_hourly"].unit.eq(ru)
    ah = aft[aft.unit == ru].set_index("hour").after_trips if unit.any() else pd.Series(dtype=float)
    fig = go.Figure(); fig.add_bar(x=hh.hour, y=hh.trips, name="Trips / hr – current")
    if len(ah): fig.add_bar(x=ah.index, y=ah.values, name="Trips / hr – recommended")
    fig.add_scatter(x=hh.hour, y=np.ceil(hh.boardings * RIDE_FRAC / (params["capacity"] * params["target_lf"])), name="Needed trips @ target LF", mode="lines+markers")
    fig.update_layout(barmode="group", title=f"{rr.route_short_name}: {rec.action}", xaxis_title="Hour", yaxis_title="Trips / hour")
    a.plotly_chart(fig, width="stretch")
    rs = res["route_stops"][res["route_stops"].route_uid == ru].sort_values("stop_sequence")
    b.plotly_chart(style_map(line_map(rs, lat="stop_lat", lon="stop_lon", zoom=11, title="Route alignment")).add_trace(
        (go.Scattermap if NEW_MAP else go.Scattermapbox)(lat=rs.stop_lat, lon=rs.stop_lon, mode="markers", marker=dict(size=7), name="stops")), width="stretch")
    st.info(rec.detail + ("  \n**Structural option:** " + rec.structural_option if rec.structural_option else ""))

# ------------------------------------------------------------------ impact
with tabs[6]:
    ci = CI; names = {"total_trips_day": "Trips / day", "bus_hours_day": "Bus-hours / day", "bus_km_day": "Bus-km / day", "n_routes_overcrowded": "Overcrowded routes",
                      "n_routes_underutilized": "Under-used routes", "mean_peak_lf": "Mean peak load factor", "trip_share_nearly_empty": "Share of near-empty trips",
                      "pax_share_in_overcrowded_hours": "Passengers in overcrowded hours", "avg_wait_min": "Avg passenger wait (min)", "mean_avg_lf": "Mean average load factor"}
    tot = {k: (ci[f"before_{k}"].sum(), ci[f"after_{k}"].sum()) for k in names}
    avg = lambda k, w: (np.average(ci[f"before_{k}"], weights=ci[f"before_{w}"]), np.average(ci[f"after_{k}"], weights=ci[f"after_{w}"]))
    for k in ("mean_peak_lf", "trip_share_nearly_empty", "pax_share_in_overcrowded_hours", "avg_wait_min", "mean_avg_lf"): tot[k] = avg(k, "total_trips_day")
    rows = [{"metric": names[k], "current": b, "optimised": a, "change %": (a - b) / b * 100 if b else 0} for k, (b, a) in tot.items()]
    d = pd.DataFrame(rows); st.dataframe(d.round(2), hide_index=True, width="stretch")
    st.caption("Simulated: hourly demand is held constant, frequencies are re-allocated. Merged routes are counted as one service.")
    a, b = st.columns(2)
    sel_m = ["Overcrowded routes", "Under-used routes"]; dd = d[d.metric.isin(sel_m)].melt("metric", ["current", "optimised"])
    a.plotly_chart(px.bar(dd, x="metric", y="value", color="variable", barmode="group", title="Problem routes"), width="stretch")
    dd = d[d.metric.isin(["Trips / day", "Bus-hours / day"])].melt("metric", ["current", "optimised"])
    b.plotly_chart(px.bar(dd, x="metric", y="value", color="variable", barmode="group", title="Fleet effort"), width="stretch")
    cc = ci.assign(trips_saved=ci.before_total_trips_day - ci.after_total_trips_day, over_before=ci.before_n_routes_overcrowded, over_after=ci.after_n_routes_overcrowded)
    st.plotly_chart(px.bar(cc, x="city", y=["over_before", "over_after"], barmode="group", title="Overcrowded routes per city: current vs optimised"), width="stretch")

# ------------------------------------------------------------------ data quality
with tabs[7]:
    st.write("Cleaning applied to every feed: invalid / out-of-India coordinates removed, duplicate ids dropped, missing stop times interpolated, "
             "non-monotonic times repaired, orphan trips / routes removed.")
    cl = (get_metrics() or {}).get("cleaning") if src.startswith("Demo") else None
    if cl: st.dataframe(pd.DataFrame(cl).T, width="stretch")
    st.write("**Route feature table**"); st.dataframe(R.drop(columns=["label_idx", "route_idx", "city_idx"], errors="ignore").round(2), width="stretch", hide_index=True)
