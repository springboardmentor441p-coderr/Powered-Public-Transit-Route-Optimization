import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from common import SEQ, date_hour_picker, require_service, route_map, setup_page
from routeranker.inference import COMPONENTS

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
fig.update_layout(title=f"Score components for the window (rank among selected)", height=420,
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
