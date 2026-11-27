import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from common import CLASS_COLORS, date_hour_picker, require_service, setup_page
from routeranker.optimization import simulate_scenario

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
