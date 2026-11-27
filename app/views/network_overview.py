import pandas as pd
import plotly.express as px
import streamlit as st

from common import CLASS_COLORS, fmt_ist, require_service, route_map, setup_page
from routeranker.inference import ist_to_transit, now_ist

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
