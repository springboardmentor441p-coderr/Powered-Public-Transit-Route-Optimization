import json

import pandas as pd
import plotly.express as px
import streamlit as st

from common import ROOT, require_service, setup_page
from routeranker import config as C

setup_page("EDA Insights", "Exploratory data analysis - high-traffic windows, density heatmaps, distributions, "
                           "correlations, outliers and overlaps.", "🔍")
svc = require_service()
eda = json.loads((C.METRICS_DIR / "eda_summary.json").read_text())
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
