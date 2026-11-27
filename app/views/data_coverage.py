import pandas as pd
import plotly.express as px
import streamlit as st

from common import fmt_ist, require_service, route_map, setup_page
from routeranker import config as C
from routeranker.data_collection import latest_timestamp
from routeranker.gtfs import analyse_gtfs
from routeranker.inference import now_ist

setup_page("Data & Coverage", "Where the data comes from, how complete it is, how fresh it is - and analyse "
                              "your own GTFS feed.", "📂")
svc = require_service()
man = svc.manifest

st.subheader("Data sources")
src = pd.DataFrame(man["sources"]).T.reset_index(names="key")
src["rows pulled"] = src["key"].map({"ridership": man["raw_rows"].get("ridership"),
                                     "schedules": man["raw_rows"].get("tph"),
                                     "segment_speeds": man["raw_rows"].get("seg"),
                                     "route_speeds": man["raw_rows"].get("monthly"),
                                     "wait_assessment": man["raw_rows"].get("wait"),
                                     "routes": man["raw_rows"].get("routes"), "stops": man["raw_rows"].get("stops")})
st.dataframe(src[["name", "id", "granularity", "role", "rows pulled", "url"]], hide_index=True, width="stretch",
             column_config={"url": st.column_config.LinkColumn("link")})
st.info(f"**Granularity: HOURLY.** Core table = boardings per route per clock hour "
        f"({man['route_hours']:,} route-hours, {man['routes']} routes, {man['data_start']} → {man['data_end']}). "
        "Daily values are sums of hours.")

c1, c2 = st.columns([1, 1])
with c1:
    st.subheader("Freshness")
    if st.button("🔄 Check data.ny.gov for newer data"):
        lt = latest_timestamp()
        if lt is None:
            st.warning("API not reachable (offline?).")
        else:
            st.write(f"Latest published hour: **{lt}** (New York) · our model data ends **{man['last_timestamp_local']}**")
            if lt > pd.Timestamp(man["last_timestamp_local"]):
                st.warning("Newer data is available - run `python -m routeranker.pipeline` to retrain.")
            else:
                st.success("Models are up to date.")
    st.write(f"Models built: **{man['built_at_ist']}** · checked {fmt_ist(now_ist())}")
    st.json(man["assumptions"], expanded=False)
with c2:
    st.subheader("Route coverage map")
    st.plotly_chart(route_map(svc, dict(zip(svc.route_info["route_id"], svc.route_info["borough"])), height=360),
                    width="stretch")

st.subheader("Completeness")
h = svc.history
cov = h.groupby(["route_id", pd.Grouper(key="date", freq="W")])["ridership"].apply(lambda s: (s > 0).mean()).reset_index()
mat = cov.pivot(index="route_id", columns="date", values="ridership")
st.plotly_chart(px.imshow(mat, aspect="auto", color_continuous_scale="Greens", height=900,
                          title="Share of hours with recorded boardings (route x week)"), width="stretch")
b = svc.route_info.groupby(["borough", "route_type"]).size().reset_index(name="routes")
st.plotly_chart(px.bar(b, x="borough", y="routes", color="route_type", title="Routes by borough and type"),
                width="stretch")

st.divider()
st.subheader("📤 Analyse your own GTFS feed")
st.caption("Upload any GTFS .zip (e.g. Lepton Software feeds for Delhi, Bengaluru, Mumbai, Hyderabad, Pune ...). "
           "Required: routes.txt, trips.txt, stop_times.txt, stops.txt; optional calendar.txt, frequencies.txt, shapes.txt.")
up = st.file_uploader("GTFS zip", type="zip")
if up:
    with st.spinner("Parsing GTFS and clustering routes ..."):
        try:
            res = analyse_gtfs(up.getvalue())
        except Exception as e:  # noqa: BLE001
            st.error(f"Could not parse feed: {e}")
            st.stop()
    p = res["profiles"]
    k = st.columns(4)
    k[0].metric("Routes", len(p)); k[1].metric("KMeans k", res["k"])
    k[2].metric("Silhouette", f"{res['silhouette']:.2f}"); k[3].metric("Overlapping pairs", len(res["overlap"]))
    st.json(res["tables"], expanded=False)
    st.plotly_chart(px.scatter(p, x="route_length_km", y="trips_per_day", color=p["kmeans_cluster"].astype(str),
                               size="n_stops", hover_name="route_id", hover_data=["route_long_name", "flags"]
                               if "route_long_name" in p else ["flags"],
                               title="Uploaded routes - clusters"), width="stretch")
    s = res["stops"]
    st.plotly_chart(px.scatter_map(s, lat="latitude", lon="longitude", color="route_id", hover_name="stop_name",
                                   zoom=10, height=480, map_style="carto-positron").update_layout(showlegend=False),
                    width="stretch")
    st.dataframe(p, hide_index=True, width="stretch")
    st.dataframe(res["overlap"], hide_index=True, width="stretch")
