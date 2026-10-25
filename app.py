"""Local RouteRanker dashboard for the Chennai GTFS analysis outputs."""
from __future__ import annotations
from pathlib import Path
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
PROCESSED = ROOT / "dataset" / "processed"

st.set_page_config(page_title="RouteRanker · Chennai", page_icon="🚌", layout="wide")
st.title("RouteRanker · Chennai")
st.caption("GTFS schedule analysis and explicitly labeled synthetic demand scenarios")


def dated_files(prefix: str) -> dict[str, Path]:
    files = sorted(PROCESSED.glob(f"{prefix}_*.csv"))
    return {path.stem.rsplit("_", 1)[-1]: path for path in files}


def read_csv(path: Path, **kwargs) -> pd.DataFrame:
    return pd.read_csv(path, **kwargs)


feature_files = dated_files("route_features")
if not feature_files:
    st.warning("No analysis files found yet. Run notebooks 02–04 to create the route supply and feature CSVs under dataset/processed/.")
    st.stop()

service_date = st.sidebar.selectbox("Service date", options=sorted(feature_files, reverse=True))
features = read_csv(feature_files[service_date], dtype={"route_id": str})
supply_path = dated_files("chennai_route_hour_supply").get(service_date)
ridership_path = dated_files("synthetic_route_hour_ridership").get(service_date)
clusters_path = dated_files("route_schedule_clusters").get(service_date)
overlap_path = dated_files("route_overlap_candidates").get(service_date)

supply = read_csv(supply_path, dtype={"route_id": str}) if supply_path else pd.DataFrame()
scenario = read_csv(ridership_path, dtype={"route_id": str}) if ridership_path else pd.DataFrame()
clusters = read_csv(clusters_path, dtype={"route_id": str}) if clusters_path else pd.DataFrame()
overlaps = read_csv(overlap_path, dtype={"route_a_id": str, "route_b_id": str}) if overlap_path else pd.DataFrame()

tabs = st.tabs(["Overview", "Route explorer", "Schedule clusters", "Overlap review"])

with tabs[0]:
    st.subheader(f"Service profile · {service_date}")
    total_trips = int(features["scheduled_trips"].sum())
    st.metric("Routes with scheduled service", f"{features['route_id'].nunique():,}")
    st.metric("Scheduled trip departures", f"{total_trips:,}")
    if not scenario.empty:
        synthetic_total = int(scenario["synthetic_ridership_estimate"].sum())
        st.warning("Synthetic scenario only — these are allocated estimates, not observed passenger counts. Do not interpret them as evidence of overcrowding.")
        st.metric("Illustrative network total", f"{synthetic_total:,}", help="Aggregate calibration value allocated by schedule assumptions; not route-level ground truth.")
    if not supply.empty:
        hourly = supply.groupby("departure_hour")["scheduled_trip_count"].sum().reindex(range(24), fill_value=0)
        st.markdown("#### Scheduled trip departures by hour")
        st.bar_chart(hourly.rename("Scheduled trips"))
    if not scenario.empty:
        hourly_scenario = scenario.groupby("departure_hour")["synthetic_ridership_estimate"].sum().reindex(range(24), fill_value=0)
        st.markdown("#### Synthetic allocation by hour")
        st.bar_chart(hourly_scenario.rename("Synthetic estimate"))
    st.caption("Schedule counts come from GTFS. The synthetic allocation depends on the assumptions in notebook 03.")

with tabs[1]:
    st.subheader("Explore a route")
    search = st.text_input("Filter by route number, ID, or endpoint", placeholder="e.g. 29A, 18751, Perambur")
    options = features.copy()
    if search:
        search_mask = (
            options["route_id"].astype(str).str.contains(search, case=False, na=False)
            | options["route_short_name"].astype(str).str.contains(search, case=False, na=False)
            | options["route_long_name"].astype(str).str.contains(search, case=False, na=False)
        )
        options = options[search_mask]
    options = options.sort_values("scheduled_trips", ascending=False).head(300)
    if options.empty:
        st.info("No matching route. Try another search term.")
    else:
        route_ids = options["route_id"].astype(str).tolist()
        selected_id = st.selectbox("Route", route_ids, format_func=lambda rid: (
            f"{rid} · {options.loc[options.route_id.astype(str)==rid, 'route_short_name'].iloc[0]} — "
            f"{options.loc[options.route_id.astype(str)==rid, 'route_long_name'].iloc[0]}"
        ))
        row = features.loc[features["route_id"].astype(str)==selected_id].iloc[0]
        c1,c2,c3,c4 = st.columns(4)
        c1.metric("Scheduled trips", f"{int(row['scheduled_trips']):,}")
        c2.metric("Operating hours", f"{int(row['scheduled_hours']):,}")
        c3.metric("Distinct stops", f"{int(row['distinct_stop_count']):,}")
        c4.metric("Median scheduled trip (min)", f"{row['median_trip_duration_min']:.0f}" if pd.notna(row['median_trip_duration_min']) else "—")
        st.write(row["route_long_name"])
        if not scenario.empty:
            estimate = scenario[scenario["route_id"].astype(str)==selected_id]
            if not estimate.empty:
                st.info(f"Scenario-only estimate for this route: {int(estimate['synthetic_ridership_estimate'].sum()):,}. This is not measured ridership.")
                by_hour = estimate.groupby("departure_hour")["synthetic_ridership_estimate"].sum().reindex(range(24),fill_value=0)
                st.bar_chart(by_hour.rename("Synthetic estimate"))
        if not clusters.empty:
            cluster_row = clusters[clusters["route_id"].astype(str)==selected_id]
            if not cluster_row.empty:
                st.caption(f"Schedule-pattern cluster: {int(cluster_row.iloc[0]['schedule_cluster'])} (cluster numbers are arbitrary).")

with tabs[2]:
    st.subheader("Scheduled service patterns")
    if clusters.empty:
        st.info("Run notebook 05 to generate route schedule cluster labels.")
    else:
        cluster_summary = features.merge(clusters[["route_id","schedule_cluster"]], on="route_id", how="inner")
        summary = (cluster_summary.groupby("schedule_cluster")
                   .agg(routes=("route_id","nunique"),
                        median_scheduled_trips=("scheduled_trips","median"),
                        median_operating_hours=("scheduled_hours","median"),
                        median_distinct_stops=("distinct_stop_count","median"),
                        median_trip_duration_min=("median_trip_duration_min","median"))
                   .reset_index())
        st.dataframe(summary, use_container_width=True, hide_index=True)
        st.bar_chart(summary.set_index("schedule_cluster")["routes"])
        st.caption("These are GTFS schedule clusters, not demand, performance, or overcrowding classes.")

with tabs[3]:
    st.subheader("Route stop-overlap review")
    if overlaps.empty:
        st.info("Run notebook 06 to create route overlap candidates.")
    else:
        st.warning("A shared-stop shortlist for planner review only. Stop-set overlap does not prove route redundancy; inspect route direction, stop sequence, and observed demand before considering service changes.")
        categories = sorted(overlaps["review_category"].dropna().unique().tolist())
        selected_categories = st.multiselect("Review categories", categories, default=categories)
        view = overlaps[overlaps["review_category"].isin(selected_categories)]
        st.metric("Pairs shown", f"{len(view):,}")
        columns = ["route_a_id","route_short_name_a","route_long_name_a","scheduled_trips_a",
                   "route_b_id","route_short_name_b","route_long_name_b","scheduled_trips_b",
                   "shared_stop_count","smaller_route_stop_coverage","stop_set_jaccard","review_category"]
        st.dataframe(view[columns], use_container_width=True, hide_index=True)
