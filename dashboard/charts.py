"""Small interactive charts with visible units and explicit observation dates."""
import altair as alt
import pandas as pd
import pydeck as pdk
import streamlit as st

TEAL = "#087F8C"
NAVY = "#183B56"
ORANGE = "#D17A30"


def line(frame, x, y, ylabel, color=None, height=260):
    encoding = dict(x=alt.X(f"{x}:T", title=None), y=alt.Y(f"{y}:Q", title=ylabel, scale=alt.Scale(zero=False)),
                    tooltip=[alt.Tooltip(f"{x}:T", title="Date", format="%d %b %Y"),
                             alt.Tooltip(f"{y}:Q", title=ylabel, format=",.2f")])
    if color:
        encoding["color"] = alt.Color(f"{color}:N", title=None, scale=alt.Scale(range=[TEAL, ORANGE, NAVY]))
        encoding["tooltip"].append(alt.Tooltip(f"{color}:N", title="Series"))
    chart = alt.Chart(frame).mark_line(color=TEAL, point=True, invalid="break-paths-show-domains").encode(**encoding)
    st.altair_chart(chart.properties(height=height).interactive(), width="stretch")


def bar(frame, x, y, xlabel, ylabel, color=None, height=280):
    encoding = dict(x=alt.X(f"{x}:N", title=xlabel, sort=None),
                    y=alt.Y(f"{y}:Q", title=ylabel),
                    tooltip=[alt.Tooltip(x, title=xlabel), alt.Tooltip(y, title=ylabel, format=",.2f")])
    if color:
        encoding["color"] = alt.Color(f"{color}:N", title=None)
    st.altair_chart(alt.Chart(frame).mark_bar(color=TEAL, cornerRadiusTopLeft=3,
                                            cornerRadiusTopRight=3).encode(**encoding).properties(height=height), width="stretch")


def route_map(paths):
    if not paths:
        st.info("No geometry is available for this route in the map snapshot.")
        return
    coordinates = [point for route in paths for point in route["path"]]
    lon, lat = zip(*coordinates)
    span = max(max(lat) - min(lat), max(lon) - min(lon))
    zoom = 12.2 if span < .05 else 11.1 if span < .13 else 10.1
    chart = pdk.Deck(
        layers=[pdk.Layer("PathLayer", data=[{'_color':[8,127,140], **p} for p in paths], get_path="path", get_color="_color",
                          get_width=5, width_units="pixels", pickable=True)],
        initial_view_state=pdk.ViewState(latitude=(min(lat) + max(lat)) / 2,
                                         longitude=(min(lon) + max(lon)) / 2, zoom=zoom),
        map_provider="carto", map_style="light",
        tooltip={"text": "Route {route}\nShape {shape}"})
    st.pydeck_chart(chart, height=440, width="stretch")
    st.caption("Geometry: 3 September 2026 snapshot · route variants shown together. Basemap tiles require internet.")


def preview_chart(points, ranges, level):
    base = alt.Chart(points).encode(x=alt.X("payment_date:T", title=None, axis=alt.Axis(format="%d %b", tickCount=7)))
    chart = base.mark_line(color=TEAL, point=True).encode(
        y=alt.Y("prediction:Q", title="Daily boardings", scale=alt.Scale(zero=True)),
        tooltip=[alt.Tooltip("payment_date:T", title="Target date", format="%d %b %Y"),
                 alt.Tooltip("prediction:Q", title="Point estimate", format=",.1f")])
    if level is not None:
        band = alt.Chart(ranges.loc[ranges.level.eq(level)]).mark_area(color=TEAL, opacity=.16).encode(
            x=alt.X("payment_date:T", title=None, axis=alt.Axis(format="%d %b", tickCount=7)), y="lower:Q", y2="upper:Q",
            tooltip=[alt.Tooltip("payment_date:T", title="Target date"),
                     alt.Tooltip("lower:Q", format=",.1f"), alt.Tooltip("upper:Q", format=",.1f")])
        chart = band + chart
    st.altair_chart(chart.properties(height=300).interactive(), width="stretch")
