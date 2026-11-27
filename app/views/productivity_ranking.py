import plotly.express as px
import streamlit as st

from common import date_hour_picker, require_service, setup_page, weight_picker

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
