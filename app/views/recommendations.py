import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from common import CLASS_COLORS, date_hour_picker, require_service, setup_page

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
