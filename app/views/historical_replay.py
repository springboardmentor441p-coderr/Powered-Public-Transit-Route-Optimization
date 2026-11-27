import pandas as pd
import plotly.express as px
import streamlit as st

from common import CLASS_COLORS, require_service, setup_page

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
