import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from common import SEQ, date_hour_picker, fmt_ist, require_service, route_map, setup_page, weight_picker
from routeranker.inference import COMPONENTS, now_ist

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
