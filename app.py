"""Chicago CTA RouteRanker planning and forecast review workspace."""

import hashlib
import json
import math
import os
from datetime import timedelta
from io import BytesIO
from pathlib import Path
from zipfile import BadZipFile, ZipFile

import pandas as pd
import requests
import streamlit as st

from src.data_loader import load_bus_ridership
from src.predict_v3 import load_v3_bundle, predict_daily_routes_from_bundle
from src.scenarios import optimize_trip_allocation

ROOT = Path(__file__).parent
REPORT_PATH = ROOT / "outputs" / "reports" / "model_selection_v3.json"
FORECAST_PATH = ROOT / "outputs" / "predictions" / "cta_june_july_replay_v3.csv"
ACTUALS_PATH = ROOT / "outputs" / "predictions" / "cta_june_july_replay_v3_actuals_for_scoring.csv"
MODEL_PATH = ROOT / "models" / "cta_route_ranker_v3_results.zip"
RIDERSHIP_PATH = ROOT / "data" / "raw" / "cta_bus_ridership.csv"
CTA_ROUTE_GEOJSON_URL = "https://data.cityofchicago.org/api/v3/views/6uva-a5ei/query.geojson?accessType=DOWNLOAD"
CTA_BUS_VEHICLES_URL = "https://www.ctabustracker.com/bustime/api/v3/getvehicles"


@st.cache_data
def load_report(path: str, modified_time: float) -> dict:
    del modified_time
    return json.loads(Path(path).read_text())


@st.cache_data(max_entries=3)
def load_uploaded_ridership(contents: bytes) -> pd.DataFrame:
    return load_bus_ridership(BytesIO(contents))


@st.cache_data(max_entries=2)
def load_local_ridership(path: str, modified_time: float, size: int) -> tuple[pd.DataFrame, str]:
    del modified_time, size
    contents = Path(path).read_bytes()
    return load_bus_ridership(BytesIO(contents)), hashlib.sha256(contents).hexdigest()


@st.cache_data(max_entries=2)
def load_uploaded_service(contents: bytes) -> pd.DataFrame:
    return pd.read_csv(BytesIO(contents), dtype={"route": "string", "source_snapshot": "string"})


@st.cache_data(max_entries=2)
def load_gtfs_route_shapes(contents: bytes, route_name: str) -> tuple[pd.DataFrame, str]:
    """Read route geometry for one route from an uploaded static GTFS ZIP."""
    try:
        archive = ZipFile(BytesIO(contents))
    except BadZipFile as exc:
        raise ValueError("The GTFS upload is not a valid ZIP archive.") from exc
    with archive:
        files = {}
        for required in ("routes.txt", "trips.txt", "shapes.txt"):
            matches = [name for name in archive.namelist() if name.rsplit("/", 1)[-1].lower() == required]
            if len(matches) != 1:
                raise ValueError(f"GTFS ZIP must contain exactly one {required} file.")
            info = archive.getinfo(matches[0])
            if info.file_size > 512 * 1024 * 1024:
                raise ValueError(f"GTFS member {required} exceeds the 512 MB safety limit.")
            files[required] = pd.read_csv(archive.open(info), dtype="string")

    routes = files["routes.txt"]
    trips = files["trips.txt"]
    shapes = files["shapes.txt"]
    required_fields = {
        "routes.txt": {"route_id", "route_short_name"},
        "trips.txt": {"route_id", "shape_id"},
        "shapes.txt": {"shape_id", "shape_pt_sequence", "shape_pt_lat", "shape_pt_lon"},
    }
    for filename, required in required_fields.items():
        missing = required - set(files[filename].columns)
        if missing:
            raise ValueError(f"{filename} is missing required columns: {sorted(missing)}")

    routes["route_short_name"] = routes["route_short_name"].astype("string").str.strip()
    route_ids = routes.loc[routes["route_short_name"].eq(route_name), "route_id"].dropna().unique()
    if len(route_ids) != 1:
        raise ValueError(f"Expected one GTFS route matching CTA route {route_name}; found {len(route_ids)}.")
    route_trips = trips.loc[trips["route_id"].eq(route_ids[0]), "shape_id"].dropna().value_counts()
    if route_trips.empty:
        raise ValueError(f"No GTFS shapes are linked to route {route_name}.")
    shape_counts = route_trips.head(8).rename("scheduled trip variants").rename_axis("shape_id").reset_index()
    route_shapes = shapes.loc[shapes["shape_id"].isin(shape_counts["shape_id"])].copy()
    for column in ("shape_pt_sequence", "shape_pt_lat", "shape_pt_lon"):
        route_shapes[column] = pd.to_numeric(route_shapes[column], errors="coerce")
    route_shapes = route_shapes.dropna(subset=["shape_pt_sequence", "shape_pt_lat", "shape_pt_lon"])
    route_shapes = route_shapes.sort_values(["shape_id", "shape_pt_sequence"])
    counts = shape_counts.set_index("shape_id")["scheduled trip variants"]
    rows = []
    colors = ([0, 125, 128], [239, 132, 61], [65, 102, 173], [170, 86, 137], [90, 138, 90], [190, 155, 55], [95, 93, 145], [130, 105, 80])
    for index, (shape_id, group) in enumerate(route_shapes.groupby("shape_id", sort=False)):
        points = group[["shape_pt_lon", "shape_pt_lat"]].to_numpy(dtype=float)
        if len(points) > 600:
            stride = int(len(points) / 600) + 1
            points = points[::stride]
        rows.append({
            "shape_id": str(shape_id),
            "trips": int(counts.loc[shape_id]),
            "path": points.tolist(),
            "color": list(colors[index % len(colors)]),
        })
    if not rows:
        raise ValueError(f"No usable shape points were found for route {route_name}.")
    return pd.DataFrame(rows), route_ids[0]


@st.cache_data(max_entries=2)
def load_route_geojson(contents: bytes) -> tuple[pd.DataFrame, str]:
    """Convert the City of Chicago CTA bus-route GeoJSON export to map paths."""
    if len(contents) > 100 * 1024 * 1024:
        raise ValueError("GeoJSON exceeds the 100 MB upload limit.")
    try:
        payload = json.loads(contents)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Could not read a valid GeoJSON document.") from exc
    if payload.get("type") != "FeatureCollection" or not isinstance(payload.get("features"), list):
        raise ValueError("Expected a GeoJSON FeatureCollection.")

    rows = []
    route_keys = set()
    for feature in payload["features"]:
        properties = feature.get("properties") or {}
        route_key = next((key for key in properties if key.lower() in {
            "route", "route_number", "route_num", "route_short_name", "rt", "name",
        }), None)
        if route_key is None:
            continue
        route_keys.add(route_key)
        route = str(properties[route_key]).strip()
        geometry = feature.get("geometry") or {}
        coordinates = geometry.get("coordinates") or []
        geom_type = geometry.get("type")
        paths = [coordinates] if geom_type == "LineString" else coordinates if geom_type == "MultiLineString" else []
        for path in paths:
            # GeoJSON coordinates are [longitude, latitude].
            points = [[float(point[0]), float(point[1])] for point in path if len(point) >= 2]
            if len(points) >= 2 and route:
                rows.append({"route": route, "path": points})
    if not rows:
        keys = sorted({key for feature in payload["features"] for key in (feature.get("properties") or {})})
        raise ValueError(f"No route line geometries found. Available feature properties: {keys}")
    if len(route_keys) > 1:
        raise ValueError(f"Ambiguous route-name fields in GeoJSON: {sorted(route_keys)}")
    return pd.DataFrame(rows), next(iter(route_keys))


@st.cache_data(ttl=86400, max_entries=1, show_spinner=False)
def fetch_official_route_geojson() -> bytes:
    """Fetch the official static route network and reuse it for one day."""
    response = requests.get(CTA_ROUTE_GEOJSON_URL, timeout=(5, 15))
    response.raise_for_status()
    if len(response.content) > 100 * 1024 * 1024:
        raise ValueError("Official route GeoJSON exceeds the 100 MB safety limit.")
    return response.content


@st.cache_data(ttl=30, max_entries=8, show_spinner=False)
def fetch_live_vehicles(api_key: str, route_codes: tuple[str, ...]) -> tuple[pd.DataFrame, str]:
    """Fetch near-real-time bus positions for up to ten selected routes."""
    response = requests.get(
        CTA_BUS_VEHICLES_URL,
        params={"key": api_key, "rt": ",".join(route_codes), "format": "json", "tmres": "s"},
        timeout=(5, 15),
    )
    response.raise_for_status()
    body = response.json().get("bustime-response", {})
    if body.get("error"):
        details = body["error"]
        raise ValueError("CTA Bus Tracker API error: " + str(details))
    vehicles = body.get("vehicle", [])
    if isinstance(vehicles, dict):
        vehicles = [vehicles]
    frame = pd.DataFrame(vehicles)
    if not frame.empty:
        for column in ("lat", "lon"):
            if column not in frame:
                raise ValueError(f"CTA vehicle response is missing `{column}` coordinates.")
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        frame = frame.dropna(subset=["lat", "lon"])
        frame["position"] = frame.apply(lambda row: [row["lon"], row["lat"]], axis=1)
        palette = [[0, 125, 128, 240], [239, 132, 61, 240], [65, 102, 173, 240], [170, 86, 137, 240], [90, 138, 90, 240], [190, 155, 55, 240], [95, 93, 145, 240], [130, 105, 80, 240], [40, 140, 180, 240], [210, 90, 70, 240]]
        route_colors = {route: palette[index % len(palette)] for index, route in enumerate(route_codes)}
        frame["color"] = frame.get("rt", pd.Series(index=frame.index, dtype="string")).map(route_colors)
    return frame, str(body.get("tmst", "time unavailable"))


def get_bus_tracker_key() -> str | None:
    """Read the optional CTA key from deployment secrets or the environment."""
    key = os.environ.get("CTA_BUS_TRACKER_API_KEY", "").strip()
    if key:
        return key
    try:
        return str(st.secrets.get("CTA_BUS_TRACKER_API_KEY", "")).strip() or None
    except (FileNotFoundError, AttributeError):
        return None


def render_route_map(route: str, period: pd.DataFrame) -> None:
    st.markdown("#### CTA route network map")
    st.caption(
        "The dashboard fetches and caches official route geometry automatically. You can upload a GeoJSON or "
        "GTFS ZIP to override it. Near-real-time bus markers are optional and require your CTA API key."
    )
    st.markdown(
        "[Open the official CTA Bus Routes dataset](https://data.cityofchicago.org/Transportation/CTA-Bus-Routes/6uva-a5ei) "
        "· [Download its GeoJSON export](https://data.cityofchicago.org/api/v3/views/6uva-a5ei/query.geojson?accessType=DOWNLOAD)"
    )
    map_options = ["Highlight selected route"]
    if not period.empty:
        map_options.append("Color by mean daily boardings")
    map_mode = st.radio("Map display", map_options, horizontal=True, key="route_map_mode")
    upload = st.file_uploader(
        "Optional route geometry override", type=["geojson", "json", "zip"], key="route_geometry_zip",
        help="GeoJSON replaces the automatic network export. A GTFS ZIP shows the selected route's scheduled shapes.",
    )
    try:
        is_geojson = upload is None or upload.name.lower().endswith((".geojson", ".json"))
        if upload is None:
            with st.spinner("Loading the official CTA route network…"):
                geometry_bytes = fetch_official_route_geojson()
            geometry_source = "official City of Chicago route network (cached for 24 hours)"
        else:
            geometry_bytes = upload.getvalue()
            geometry_source = f"uploaded file `{upload.name}`"
        if is_geojson:
            geometry, route_field = load_route_geojson(geometry_bytes)
            geometry["selected"] = geometry["route"].astype(str).eq(str(route))
            matched_route = bool(geometry["selected"].any())
            map_caption = f"{len(geometry['route'].unique())} route labels · source field `{route_field}` · {geometry_source}"
            if map_mode == "Color by mean daily boardings":
                means = period.assign(route=period["route"].astype(str)).groupby("route")["rides"].mean()
                geometry["mean_boardings"] = geometry["route"].map(means)
                values = geometry["mean_boardings"]
                low, high = values.min(), values.max()
                scaled = (values - low) / (high - low) if pd.notna(high) and high > low else values * 0
                geometry["color"] = scaled.fillna(0).map(
                    lambda value: [int(40 + 210 * value), int(150 - 90 * value), int(220 - 190 * value), 210]
                )
                geometry["line_width"] = 2 + 4 * scaled.fillna(0)
                tooltip = {"text": "CTA route: {route}\nMean boardings / observed day: {mean_boardings}"}
                map_caption += f" · boardings averaged over the selected dates and day types"
                map_legend = "🔵 Lower mean boardings / thinner line  →  🟠 Higher mean boardings / thicker line"
            else:
                geometry["color"] = geometry["selected"].map({True: [0, 125, 128, 240], False: [139, 151, 163, 95]})
                geometry["line_width"] = 4
                tooltip = {"text": "CTA route: {route}"}
                map_legend = None
                if matched_route:
                    map_caption += f" · selected CTA route {route} highlighted"
                else:
                    map_caption += f" · route {route} not found in this geometry export"
        else:
            variants, route_id = load_gtfs_route_shapes(geometry_bytes, route)
            variants["selected"] = True
            variants["color"] = variants["color"].map(lambda color: [*color, 220])
            variants["line_width"] = 4
            geometry = variants
            map_caption = f"CTA route {route} · GTFS route_id `{route_id}` · {len(variants)} shape variants shown"
            tooltip = {"text": "Shape: {shape_id}\nTrips in feed: {trips}"}
            map_legend = None
        import pydeck as pdk

        layers = [pdk.Layer(
            "PathLayer", data=geometry, get_path="path", get_color="color", get_width="line_width",
            width_min_pixels=2, pickable=True, auto_highlight=True, get_width_units="pixels",
        )]
        api_key = get_bus_tracker_key()
        if is_geojson and api_key:
            live_routes = st.multiselect(
                "Routes for live bus markers (up to 10)",
                sorted(geometry["route"].astype(str).unique()),
                default=[str(route)] if str(route) in set(geometry["route"].astype(str)) else [],
                max_selections=10,
                key="live_bus_routes",
            )
            if live_routes:
                if st.button("Refresh live bus positions", key="refresh_live_bus_positions"):
                    fetch_live_vehicles.clear()
                try:
                    with st.spinner("Fetching near-real-time CTA bus positions…"):
                        vehicles, feed_time = fetch_live_vehicles(api_key, tuple(live_routes))
                except (requests.RequestException, ValueError) as exc:
                    st.warning(f"Live bus positions are temporarily unavailable ({type(exc).__name__}); route map still works.")
                else:
                    if not vehicles.empty:
                        vehicles["route"] = vehicles["rt"].astype(str)
                        layers.append(pdk.Layer(
                            "ScatterplotLayer", data=vehicles, get_position="position", get_fill_color="color",
                            get_radius=55, radius_min_pixels=5, radius_max_pixels=10, stroked=True,
                            get_line_color=[255, 255, 255, 230], line_width_min_pixels=1,
                            pickable=True, auto_highlight=True,
                        ))
                        st.caption(f"{len(vehicles):,} buses · CTA feed timestamp {feed_time} (Chicago local time)")
                    else:
                        st.info(f"No active vehicle positions returned for the selected routes. CTA feed time: {feed_time}.")
        elif is_geojson:
            st.info(
                "Live bus positions are not configured for this deployment. Add `CTA_BUS_TRACKER_API_KEY` "
                "to its environment or Streamlit secrets after applying for a CTA key. "
                "CTA says its Bus Tracker feed updates about every 30 seconds. "
                "[Apply through CTA](https://www.transitchicago.com/developers/bustracker/)."
            )
        deck = pdk.Deck(
            layers=layers,
            initial_view_state=pdk.ViewState(latitude=41.8781, longitude=-87.6298, zoom=10, pitch=0),
            map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
            tooltip=tooltip,
        )
        st.pydeck_chart(deck, height=460)
        if map_legend:
            st.caption(map_legend)
        st.caption(
            f"{map_caption}. Demand colors show route-level averages; they do not describe individual street segments. "
            "Static route geometry; it does not show active service or vehicle positions."
        )
    except (OSError, KeyError, TypeError, ValueError, pd.errors.ParserError, UnicodeDecodeError) as exc:
        st.error(f"Could not load or draw route geometry / live bus data: {exc}")
    except requests.RequestException as exc:
        st.warning("The automatic CTA map download could not be reached from this app deployment.")
        st.caption(f"Connection detail: {type(exc).__name__}. Upload a GeoJSON override above to display route geometry now.")


@st.cache_resource(max_entries=2)
def load_uploaded_v3_bundle(contents: bytes) -> dict:
    return load_v3_bundle(contents)


@st.cache_resource(max_entries=1)
def load_local_v3_bundle(path: str, modified_time: float, size: int) -> dict:
    del modified_time, size
    return load_v3_bundle(path)


@st.cache_data
def load_replay_files(forecasts_path: str, forecasts_mtime: float, actuals_path: str, actuals_mtime: float):
    del forecasts_mtime, actuals_mtime
    forecasts = pd.read_csv(forecasts_path, dtype={"route": "string"})
    actuals = pd.read_csv(actuals_path, dtype={"route": "string"})
    forecasts["target_date"] = pd.to_datetime(forecasts["target_date"], errors="coerce").dt.normalize()
    actuals["date"] = pd.to_datetime(actuals["date"], errors="coerce").dt.normalize()
    return forecasts, actuals


def fmt_rides(value: float) -> str:
    return f"{value:,.1f} rides"


def render_network_map(source: pd.DataFrame | None) -> None:
    st.subheader("Chicago CTA network map")
    st.caption("Explore route geometry, compare observed route demand, and—when configured—view current bus locations.")
    if source is None or source.empty:
        period = pd.DataFrame(columns=["route", "rides", "date", "daytype"])
        route = "1"
        st.info("Route geometry can display without ridership data. Add a CTA ridership CSV to enable demand coloring.")
    else:
        latest = source["date"].max()
        earliest = max(source["date"].min(), latest - pd.Timedelta(days=83))
        period = source.loc[source["date"].between(earliest, latest)].copy()
        routes = sorted(source["route"].astype(str).unique())
        default_route = "1" if "1" in routes else str(
            period.groupby(period["route"].astype(str))["rides"].mean().idxmax()
        )
        route = st.selectbox("Highlight route", routes, index=routes.index(default_route), key="network_map_route")
        first, second = st.columns(2)
        first.metric("Latest ridership date", latest.strftime("%b %-d, %Y"))
        second.metric("Routes in ridership file", f"{source['route'].nunique():,}")
        st.caption(f"Demand colors summarize observed daily boardings from {earliest.date()} through {latest.date()}.")
    render_route_map(route, period)


def render_overview(report: dict, source: pd.DataFrame | None, source_sha256: str | None) -> None:
    del source_sha256
    selection = report["model_selection"]
    paired = report["paired_matched_experiment"]
    winner = selection["paired_matched_validation_winner"]
    test = paired["test_metrics_common_methods"][winner]
    baseline = paired["test_metrics_common_methods"]["past_four_same_weekdays"]
    validation = selection["selected_validation_metrics"]
    improvement = 100 * (baseline["mae"] - test["mae"]) / baseline["mae"]

    st.subheader("Route demand and forecast performance")
    st.write("Review how the trained model performed, explore route histories, and try planning scenarios.")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Selected model", "Random Forest", "Demand-only")
    col2.metric("Test MAE", f"{test['mae']:,.1f}", f"{improvement:.1f}% lower than baseline")
    col3.metric("Test WAPE", f"{test['wape']:.2%}")
    col4.metric("Matched test route-days", f"{test['rows']:,}")
    st.caption(
        f"Validation MAE: {validation['mae']:,.1f} rides across {validation['rows']:,} route-days. "
        "Model choice was made on validation MAE; June–July test results were not used to choose it."
    )

    if source is not None:
        st.markdown("#### Recent observed ridership")
        latest = source["date"].max()
        start = latest - pd.Timedelta(days=83)
        recent = source.loc[source["date"].between(start, latest)]
        totals = recent.groupby("route", as_index=False)["rides"].sum().sort_values("rides", ascending=False)
        a, b, c = st.columns(3)
        a.metric("Source rows", f"{len(source):,}")
        b.metric("Routes", f"{source['route'].nunique():,}")
        c.metric("Latest observation", latest.strftime("%b %-d, %Y"))
        daily = recent.groupby("date", as_index=False)["rides"].sum().set_index("date")
        st.line_chart(daily, y="rides", x_label="Date", y_label="Daily boardings")
        st.caption("Network totals use the most recent 84 calendar days in the uploaded file.")
        st.dataframe(
            totals.head(10).rename(columns={"route": "Route", "rides": "Boardings in period"}),
            hide_index=True,
            column_config={"Boardings in period": st.column_config.NumberColumn(format="%,.0f")},
        )
    else:
        st.info("Add a CTA ridership CSV in the sidebar to enable route histories, demand coloring, and forecasts.")


def render_routes(source: pd.DataFrame | None) -> None:
    st.subheader("Route explorer and comparison")
    st.caption("Use exact observed route-days from the uploaded CTA file; missing dates remain missing.")
    if source is None:
        st.info("Upload a validated CTA ridership CSV in the sidebar to use these views.")
        return

    routes = sorted(source["route"].astype(str).unique())
    latest = source["date"].max()
    earliest = source["date"].min()
    default_start = max(earliest, latest - pd.Timedelta(days=179))
    controls = st.columns([1, 1, 1.5])
    route = controls[0].selectbox("Route profile", routes, key="profile_route")
    daytypes = controls[1].multiselect("Day types", ["W", "A", "U"], default=["W", "A", "U"], key="profile_daytypes")
    selected_range = controls[2].date_input(
        "Observation window",
        value=(default_start.date(), latest.date()),
        min_value=earliest.date(),
        max_value=latest.date(),
        key="profile_dates",
    )
    if not isinstance(selected_range, tuple) or len(selected_range) != 2:
        st.info("Choose both a start and end date.")
        return
    start, end = map(pd.Timestamp, selected_range)
    period = source.loc[
        source["date"].between(start, end) & source["daytype"].isin(daytypes)
    ].copy()
    route_rows = period.loc[period["route"].astype(str).eq(route)].sort_values("date")

    if route_rows.empty:
        st.warning("No observations for this route, day-type selection, and date range.")
    else:
        k1, k2, k3 = st.columns(3)
        k1.metric("Observed route-days", f"{len(route_rows):,}")
        k2.metric("Mean boardings / observed day", f"{route_rows['rides'].mean():,.0f}")
        k3.metric("Total boardings in window", f"{route_rows['rides'].sum():,.0f}")
        series = route_rows.set_index("date")["rides"]
        st.line_chart(series, x_label="Date", y_label="Daily boardings")
        st.caption("Only reported route-days are plotted. Missing dates are not filled or interpolated.")
        by_daytype = (
            route_rows.groupby("daytype")["rides"].agg(["count", "mean", "median", "std"])
            .rename(index={"W": "Weekday", "A": "Saturday", "U": "Sunday / holiday"})
        )
        st.dataframe(by_daytype, column_config={
            "count": "Observed days",
            "mean": st.column_config.NumberColumn("Mean rides", format="%,.1f"),
            "median": st.column_config.NumberColumn("Median rides", format="%,.1f"),
            "std": st.column_config.NumberColumn("Std. dev.", format="%,.1f"),
        })

    render_route_map(route, period)

    st.divider()
    st.markdown("#### Compare two routes on the same observed dates")
    cmp_controls = st.columns(3)
    route_a = cmp_controls[0].selectbox("Route A", routes, index=0, key="compare_a")
    route_b = cmp_controls[1].selectbox("Route B", routes, index=min(1, len(routes) - 1), key="compare_b")
    comparison_mode = cmp_controls[2].selectbox(
        "Compare as", ["Daily boardings", "Index to first common date"], key="compare_mode"
    )
    common = period.loc[period["route"].astype(str).isin([route_a, route_b])].pivot_table(
        index="date", columns="route", values="rides", aggfunc="first"
    ).dropna(subset=[route_a, route_b])
    if route_a == route_b:
        st.info("Choose two different routes to compare.")
    elif common.empty:
        st.warning("The selected routes have no common observed dates in this window.")
    else:
        view = common[[route_a, route_b]].copy()
        if comparison_mode == "Index to first common date":
            view = view.div(view.iloc[0]).mul(100)
            st.caption("Each route is set to 100 on the first common date. This compares trend, not route size.")
        st.line_chart(view, x_label="Common observed date", y_label="Index (first date = 100)" if comparison_mode.startswith("Index") else "Daily boardings")
        st.caption(f"Matched coverage: {len(common):,} common route-days from {common.index.min().date()} through {common.index.max().date()}.")

    st.divider()
    st.markdown("#### Ridership review signals")
    recent_start = source["date"].max() - pd.Timedelta(days=83)
    prior_start = source["date"].max() - pd.Timedelta(days=167)
    prior_end = recent_start - pd.Timedelta(days=1)
    st.caption(
        f"Compares day-type-standardized means from {recent_start.date()}–{source['date'].max().date()} "
        f"with {prior_start.date()}–{prior_end.date()}. Routes need at least five observations for all "
        "three day types in both windows; weekday, Saturday, and Sunday/holiday means receive equal weight. "
        "This is a review queue, not a service-quality or route-cut ranking."
    )
    review = build_review_signals(source)
    if review.empty:
        st.info("There are not enough matched observations to form review signals.")
    else:
        sort = st.selectbox("Order review queue", ["Largest increase", "Largest decrease"], key="review_order")
        review = review.sort_values("change_pct", ascending=sort != "Largest increase")
        st.dataframe(
            review.rename(columns={
                "route": "Route", "recent_mean": "Recent standardized rides/day",
                "prior_mean": "Prior standardized rides/day", "change_pct": "Change (%)",
                "daytypes": "Day types represented",
                "observed_days": "Observed route-days across both windows",
            }).style.format({
                "Recent standardized rides/day": "{:,.1f}",
                "Prior standardized rides/day": "{:,.1f}",
                "Change (%)": "{:+.1f}%",
            }),
            hide_index=True,
        )

    st.divider()
    st.markdown("#### Exploratory route groups")
    st.caption(
        "Groups compare route demand scale and weekend-to-weekday shape over the selected date range. "
        "They describe similarity only; group IDs do not imply service need or performance."
    )
    group_controls = st.columns(2)
    minimum_days = group_controls[0].slider("Minimum observations per day type", 5, 30, 10, key="group_min_days")
    group_count = group_controls[1].slider("Number of exploratory groups", 2, 8, 4, key="group_count")
    grouping_source = source.loc[source["date"].between(start, end)]
    st.caption(
        f"Grouping window: {start.date()}–{end.date()} · features: log weekday mean, "
        "Saturday/weekday mean ratio, Sunday-holiday/weekday mean ratio · routes need the selected "
        "minimum observations for all three day types."
    )
    try:
        route_groups, group_summary = cluster_route_profiles(grouping_source, group_count, minimum_days)
    except (ValueError, ImportError) as exc:
        st.error(f"Route groups could not be formed: {exc}")
    else:
        if route_groups.empty:
            st.info("Too few routes meet the selected weekday, Saturday, and Sunday/holiday sample minimums.")
        else:
            st.dataframe(group_summary, hide_index=True, column_config={
                "median_weekday_rides": st.column_config.NumberColumn("Median weekday rides", format="%,.0f"),
                "median_saturday_ratio": st.column_config.NumberColumn("Saturday / weekday", format="%.2f"),
                "median_sunday_ratio": st.column_config.NumberColumn("Sunday-holiday / weekday", format="%.2f"),
            })
            st.dataframe(
                route_groups[["route", "group", "weekday_mean", "saturday_to_weekday", "sunday_to_weekday"]].rename(columns={
                    "route": "Route", "group": "Group", "weekday_mean": "Mean weekday rides",
                    "saturday_to_weekday": "Saturday / weekday", "sunday_to_weekday": "Sunday-holiday / weekday",
                }),
                hide_index=True,
                column_config={
                    "Mean weekday rides": st.column_config.NumberColumn(format="%,.0f"),
                    "Saturday / weekday": st.column_config.NumberColumn(format="%.2f"),
                    "Sunday-holiday / weekday": st.column_config.NumberColumn(format="%.2f"),
                },
            )
            st.download_button(
                "Download route group assignments", route_groups.to_csv(index=False),
                file_name="cta_exploratory_route_groups.csv", mime="text/csv",
            )


@st.cache_data(max_entries=2)
def build_review_signals(source: pd.DataFrame) -> pd.DataFrame:
    latest = source["date"].max()
    recent_start = latest - pd.Timedelta(days=83)
    prior_start = latest - pd.Timedelta(days=167)
    prior_end = recent_start - pd.Timedelta(days=1)
    recent = source.loc[source["date"].between(recent_start, latest)]
    prior = source.loc[source["date"].between(prior_start, prior_end)]
    keys = ["route", "daytype"]
    recent_summary = recent.groupby(keys)["rides"].agg(recent_mean="mean", recent_days="size").reset_index()
    prior_summary = prior.groupby(keys)["rides"].agg(prior_mean="mean", prior_days="size").reset_index()
    paired = recent_summary.merge(prior_summary, on=keys, how="inner")
    paired = paired.loc[(paired["recent_days"] >= 5) & (paired["prior_days"] >= 5)].copy()
    if paired.empty:
        return pd.DataFrame()
    rows = []
    for route, group in paired.groupby("route"):
        if len(group) != 3:
            continue
        # Standardize both periods to the same three-daytype mix. Equal
        # weighting prevents differing data completeness from changing the mix.
        recent_mean = float(group["recent_mean"].mean())
        prior_mean = float(group["prior_mean"].mean())
        rows.append({
            "route": str(route),
            "recent_mean": recent_mean,
            "prior_mean": prior_mean,
            "change_pct": 100 * (recent_mean - prior_mean) / prior_mean if prior_mean else None,
            "daytypes": int(len(group)),
            "observed_days": int(group["recent_days"].sum() + group["prior_days"].sum()),
        })
    if not rows:
        return pd.DataFrame(columns=["route", "recent_mean", "prior_mean", "change_pct", "daytypes", "observed_days"])
    return pd.DataFrame(rows).dropna(subset=["change_pct"])


@st.cache_data(max_entries=3)
def cluster_route_profiles(source: pd.DataFrame, n_clusters: int, minimum_daytype_days: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Group routes by observed weekday volume and weekend-to-weekday profile."""
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import StandardScaler

    summary = source.groupby(["route", "daytype"])["rides"].agg(["mean", "count"]).reset_index()
    means = summary.pivot(index="route", columns="daytype", values="mean")
    counts = summary.pivot(index="route", columns="daytype", values="count")
    required = ["W", "A", "U"]
    if not set(required).issubset(means.columns):
        return pd.DataFrame(), pd.DataFrame()
    eligible = means[required].notna().all(axis=1) & counts[required].ge(minimum_daytype_days).all(axis=1)
    means = means.loc[eligible, required]
    if len(means) < n_clusters:
        return pd.DataFrame(), pd.DataFrame()
    weekday = means["W"].where(means["W"].ne(0))
    features = pd.DataFrame({
        "weekday_volume_log": means["W"].clip(lower=0).map(math.log1p),
        "saturday_to_weekday": means["A"] / weekday,
        "sunday_to_weekday": means["U"] / weekday,
    }).replace([float("inf"), float("-inf")], pd.NA).dropna()
    means = means.loc[features.index]
    if len(features) < n_clusters:
        return pd.DataFrame(), pd.DataFrame()
    scaled = StandardScaler().fit_transform(features)
    labels = KMeans(n_clusters=n_clusters, random_state=42, n_init=20).fit_predict(scaled)
    profiles = means.copy()
    profiles["route"] = profiles.index.astype(str)
    profiles["group"] = labels + 1
    profiles["weekday_mean"] = profiles.pop("W")
    profiles["saturday_mean"] = profiles.pop("A")
    profiles["sunday_holiday_mean"] = profiles.pop("U")
    profiles["saturday_to_weekday"] = features["saturday_to_weekday"]
    profiles["sunday_to_weekday"] = features["sunday_to_weekday"]
    group_summary = profiles.groupby("group").agg(
        routes=("route", "count"),
        median_weekday_rides=("weekday_mean", "median"),
        median_saturday_ratio=("saturday_to_weekday", "median"),
        median_sunday_ratio=("sunday_to_weekday", "median"),
    ).reset_index()
    return profiles.reset_index(drop=True), group_summary


def render_evaluation(report: dict) -> None:
    st.subheader("Forecast evidence")
    selection = report["model_selection"]
    paired = report["paired_matched_experiment"]
    validation = paired["validation_metrics_common_methods"]
    test = paired["test_metrics_common_methods"]
    candidate_names = [
        "demand_only::pooled_linear_regression",
        "demand_only::random_forest",
        "demand_only::hist_gradient_boosting_reference",
        "service_aware::pooled_linear_regression",
        "service_aware::random_forest",
        "service_aware::hist_gradient_boosting_reference",
    ]
    labels = {
        "demand_only::pooled_linear_regression": "Demand · Linear regression",
        "demand_only::random_forest": "Demand · Random Forest (selected)",
        "demand_only::hist_gradient_boosting_reference": "Demand · HistGradientBoosting",
        "service_aware::pooled_linear_regression": "Service-aware · Linear regression",
        "service_aware::random_forest": "Service-aware · Random Forest",
        "service_aware::hist_gradient_boosting_reference": "Service-aware · HistGradientBoosting",
    }
    rows = []
    for name in candidate_names:
        rows.append({
            "Candidate": labels[name],
            "Validation MAE": validation[name]["mae"],
            "Validation WAPE": validation[name]["wape"],
            "Test MAE": test[name]["mae"],
            "Test WAPE": test[name]["wape"],
            "Test rows": test[name]["rows"],
        })
    rows.extend([
        {"Candidate": "Baseline · past four same weekdays", "Validation MAE": validation["past_four_same_weekdays"]["mae"], "Validation WAPE": validation["past_four_same_weekdays"]["wape"], "Test MAE": test["past_four_same_weekdays"]["mae"], "Test WAPE": test["past_four_same_weekdays"]["wape"], "Test rows": test["past_four_same_weekdays"]["rows"]},
        {"Candidate": "Baseline · last week same day", "Validation MAE": validation["last_week_same_day"]["mae"], "Validation WAPE": validation["last_week_same_day"]["wape"], "Test MAE": test["last_week_same_day"]["mae"], "Test WAPE": test["last_week_same_day"]["wape"], "Test rows": test["last_week_same_day"]["rows"]},
    ])
    results = pd.DataFrame(rows)
    st.caption(
        f"Validation winner: {selection['paired_matched_validation_winner']}. "
        "Validation selects; the test period assesses that frozen choice."
    )
    st.dataframe(
        results.style.format({
            "Validation MAE": "{:,.1f}", "Validation WAPE": "{:.2%}",
            "Test MAE": "{:,.1f}", "Test WAPE": "{:.2%}", "Test rows": "{:,.0f}",
        }),
        hide_index=True,
    )

    st.markdown("#### Where did the selected model help or struggle?")
    diagnostics = paired["selected_test_diagnostics"]
    route_metrics = diagnostics.get("route", {})
    if route_metrics:
        diagnostic_rows = []
        for route, metrics in route_metrics.items():
            diagnostic_rows.append({
                "Route": route,
                "Model MAE": metrics["mae"],
                "Model WAPE": metrics["wape"],
                "Route-days": metrics["rows"],
            })
        route_table = pd.DataFrame(diagnostic_rows).sort_values("Model MAE", ascending=False)
        st.dataframe(route_table.head(15).style.format({"Model MAE": "{:,.1f}", "Model WAPE": "{:.2%}"}), hide_index=True)
        st.caption("Routes are ordered by model MAE; route-level sample sizes vary. This is not a baseline-relative service ranking.")
    else:
        st.info("Route-level matched diagnostics are not available in the report.")

    daytype_rows = []
    for daytype, metrics in diagnostics.get("daytype", {}).items():
        daytype_rows.append({
            "CTA day type": {"W": "Weekday", "A": "Saturday", "U": "Sunday / holiday"}.get(daytype, daytype),
            "Selected model MAE": metrics["mae"],
            "Route-days": metrics["rows"],
        })
    if daytype_rows:
        daytype_frame = pd.DataFrame(daytype_rows).set_index("CTA day type")
        st.bar_chart(daytype_frame["Selected model MAE"], y_label="Mean absolute error (rides)")
        st.dataframe(daytype_frame, column_config={"Selected model MAE": st.column_config.NumberColumn(format="%,.1f")})

    st.warning(
        "This is retrospective development evidence: the evaluation CSV "
        f"{'matches' if report['source']['matches_mentor_reference'] else 'does not match'} the mentor's frozen export, "
        "the June–July window was inspected in earlier iterations, and the D−1 reporting assumption is unverified."
    )


def render_replay() -> None:
    st.subheader("Historical replay")
    st.caption(
        "Step through the saved June–July forecast replay. Actuals are revealed only after the assumed "
        "one-day reporting delay; this replays saved results and does not retrain the model."
    )
    if not FORECAST_PATH.exists() or not ACTUALS_PATH.exists():
        st.info("Saved forecast and separate scoring actuals are required for historical replay.")
        return
    forecasts, actuals = load_replay_files(
        str(FORECAST_PATH), FORECAST_PATH.stat().st_mtime,
        str(ACTUALS_PATH), ACTUALS_PATH.stat().st_mtime,
    )
    routes = sorted(forecasts["route"].dropna().astype(str).unique())
    target_start, target_end = forecasts["target_date"].min(), forecasts["target_date"].max()
    virtual = st.slider(
        "Advance the replay date",
        min_value=target_start.date(),
        max_value=(target_end + pd.Timedelta(days=1)).date(),
        value=target_start.date(),
        key="replay_clock",
    )
    route = st.selectbox("Route to replay", routes, key="replay_route")
    virtual_date = pd.Timestamp(virtual)
    route_forecasts = forecasts.loc[
        forecasts["route"].astype(str).eq(route) & (forecasts["target_date"] <= virtual_date)
    ].copy()
    route_actuals = actuals.loc[actuals["route"].astype(str).eq(route)].copy()
    route_forecasts = route_forecasts.merge(
        route_actuals[["route", "date", "daytype", "rides"]],
        left_on=["route", "target_date"], right_on=["route", "date"], how="left", validate="one_to_one",
    )
    actual_release_date = route_forecasts["target_date"] + pd.Timedelta(days=1)
    released = actual_release_date <= virtual_date
    route_forecasts["released_actual"] = route_forecasts["rides"].where(released)
    route_forecasts["status"] = released.map({True: "Actual released", False: "Forecast only"})
    released_rows = route_forecasts.loc[released]
    col1, col2, col3 = st.columns(3)
    col1.metric("Virtual date", virtual_date.strftime("%b %-d, %Y"))
    col2.metric("Forecasts issued", f"{len(route_forecasts):,}")
    col3.metric("Actuals released", f"{int(released.sum()):,}")
    if not route_forecasts.empty:
        chart = route_forecasts.set_index("target_date")[["predicted_rides"]].rename(columns={"predicted_rides": "Forecast"})
        if not released_rows.empty:
            observed = released_rows.set_index("target_date")["released_actual"].rename("Released actual")
            chart = chart.join(observed)
        st.line_chart(chart, x_label="Target date", y_label="Daily boardings")
        st.dataframe(
            route_forecasts[["target_date", "daytype", "predicted_rides", "released_actual", "status"]].rename(columns={
                "target_date": "Target date", "daytype": "Day type", "predicted_rides": "Forecast rides",
                "released_actual": "Released actual rides", "status": "Status",
            }),
            hide_index=True,
            column_config={
                "Forecast rides": st.column_config.NumberColumn(format="%,.0f"),
                "Released actual rides": st.column_config.NumberColumn(format="%,.0f"),
            },
        )
    st.caption("Replay uses separated forecast and actuals files and the declared D−1 availability assumption.")


def render_forecast(report: dict, source: pd.DataFrame | None, source_sha256: str | None) -> None:
    st.subheader("One-day route forecast")
    st.caption("Forecasts one date at a time from eligible observed rides and a user-confirmed CTA day type.")
    if source is None:
        st.info("Upload the CTA ridership CSV in the sidebar first.")
        return

    reporting_delay = int(report["information_policy"]["reporting_delay_days"])
    expected_method = report["model_selection"]["paired_matched_validation_winner"]
    expected_source_sha256 = report["source"]["ridership_sha256"]
    expected_cutoff = report["artifacts"]["final_refit"]["training_cutoff"]
    model_requires_schedule = bool(report["model_selection"].get("serving_model_requires_schedule", False))
    latest = source["date"].max()
    earliest = latest + pd.Timedelta(days=reporting_delay)
    routes = sorted(source["route"].astype(str).unique())
    st.info(
        f"Planned model: `{expected_method}`. Latest ride in file: {latest.date()}. "
        f"With the configured {reporting_delay}-day delay, "
        f"the earliest target date is {earliest.date()}. Day type is supplied by you; verify holidays."
    )
    service_upload = None
    if model_requires_schedule:
        service_upload = st.file_uploader("Required route/date service CSV", type=["csv"], key="forecast_service")
    model_upload = None
    if not MODEL_PATH.exists():
        model_upload = st.file_uploader("Colab results ZIP or v3 joblib", type=["zip", "joblib"], key="forecast_bundle")
        if model_upload is None:
            st.info("Upload the model artifact that matches the report's selected method and fingerprints.")
    with st.form("forecast_form"):
        cols = st.columns([1, 1, 2])
        target_date = cols[0].date_input(
            "Forecast date", value=earliest.date(), min_value=earliest.date(), max_value=earliest.date(),
            help="The serving model is a one-day forecaster; multi-day forecasts need a separate recursive evaluation.",
        )
        daytype = cols[1].selectbox("CTA day type", ["W", "A", "U"], format_func=lambda v: {
            "W": "Weekday", "A": "Saturday", "U": "Sunday / holiday",
        }[v])
        selected_routes = cols[2].multiselect("Routes", routes, default=routes)
        submitted = st.form_submit_button("Generate forecast")
    if not submitted:
        return
    if not selected_routes:
        st.error("Choose at least one route.")
        return
    if model_requires_schedule and service_upload is None:
        st.error("This service-aware model requires schedule rows with capture-date provenance.")
        return
    if not MODEL_PATH.exists() and model_upload is None:
        st.error("Upload the selected model artifact before generating a forecast.")
        return

    try:
        with st.spinner("Loading the saved model artifact…"):
            if MODEL_PATH.exists():
                stat = MODEL_PATH.stat()
                bundle = load_local_v3_bundle(str(MODEL_PATH), stat.st_mtime, stat.st_size)
                model_origin = "local results bundle"
            else:
                bundle = load_uploaded_v3_bundle(model_upload.getvalue())
                model_origin = "uploaded Colab artifact"
    except Exception as exc:
        st.error(f"Could not load the model artifact: {exc}")
        return

    artifact_source_sha256 = bundle.get("data_sha256")
    mismatches = []
    if bundle.get("serving_method") != expected_method:
        mismatches.append(f"method `{bundle.get('serving_method')}` does not match report `{expected_method}`")
    if int(bundle.get("reporting_delay_days", -1)) != reporting_delay:
        mismatches.append("reporting-delay setting does not match the report")
    if artifact_source_sha256 != expected_source_sha256:
        mismatches.append("training source SHA-256 does not match the report")
    if bundle.get("training_cutoff") != expected_cutoff:
        mismatches.append("training cutoff does not match the report")
    if mismatches:
        st.error("Model artifact/report mismatch: " + "; ".join(mismatches) + ". Update the model and report together.")
        return
    st.caption(
        f"Using {model_origin} · training source SHA-256: `{artifact_source_sha256}` · "
        f"active inference CSV SHA-256: `{source_sha256 or 'not available'}`"
    )
    if source_sha256 and artifact_source_sha256 != source_sha256:
        st.info(
            "The uploaded history differs from the model's training CSV. The model will use this upload "
            "for eligible lag features; its training and evaluation history remains the one recorded in the artifact."
        )
    targets = pd.DataFrame({"route": selected_routes, "date": target_date, "daytype": daytype})
    service = load_uploaded_service(service_upload.getvalue()) if service_upload else None
    try:
        forecasts = predict_daily_routes_from_bundle(bundle, source, targets, service)
    except (OSError, KeyError, ValueError, pd.errors.ParserError, UnicodeDecodeError) as exc:
        st.error(f"Forecast could not be generated: {exc}")
        return
    forecasts = forecasts.sort_values("predicted_rides", ascending=False).reset_index(drop=True)
    st.metric("Predicted daily boardings across selected routes", f"{forecasts['predicted_rides'].sum():,.0f}")
    st.caption(
        f"{bundle['serving_method']} · trained through {bundle.get('training_cutoff', 'unknown')} · "
        f"allowed ridership through {(target_date - timedelta(days=bundle['reporting_delay_days'])).isoformat()}"
    )
    st.dataframe(forecasts, hide_index=True, column_config={
        "predicted_rides": st.column_config.NumberColumn("Predicted boardings / day", format="%,.0f")
    })
    st.download_button(
        "Download forecast CSV", forecasts.to_csv(index=False),
        file_name=f"cta_route_forecast_{target_date.isoformat()}.csv", mime="text/csv",
    )
    st.caption("A demand forecast is not passenger load, crowding, route quality, or a service-change recommendation.")


def render_scenario() -> None:
    st.subheader("Trip-allocation scenario sandbox")
    st.write(
        "Explore a bounded redistribution of a fixed systemwide trip total using predicted daily boardings "
        "and current scheduled trips."
    )
    st.warning(
        "This minimizes the highest boardings-per-scheduled-trip ratio. Daily boardings divided by trips "
        "is not vehicle load or crowding. Fleet, crew, running time, accessibility, equity, transfers, and "
        "route overlap are not modeled; treat every result as a scenario for planner review."
    )
    template = pd.DataFrame(columns=["route", "predicted_rides", "scheduled_trips"])
    example = pd.DataFrame({
        "route": ["Example A", "Example B", "Example C"],
        "predicted_rides": [12000, 7000, 5000],
        "scheduled_trips": [20, 16, 14],
    })
    blank, sample = st.columns(2)
    blank.download_button("Download blank template", template.to_csv(index=False), "route_scenario_template.csv", "text/csv")
    sample.download_button("Download synthetic example", example.to_csv(index=False), "synthetic_route_scenario_example.csv", "text/csv")
    upload = st.file_uploader(
        "Scenario input CSV", type=["csv"], key="scenario_input",
        help="One row per route; required columns: route, predicted_rides, scheduled_trips.",
    )
    max_shift = st.slider("Maximum trip change per route", 0, 50, 10, step=5, format="%d%%")
    if upload is None:
        return
    try:
        source = pd.read_csv(upload, dtype={"route": "string"})
        result = optimize_trip_allocation(source, max_shift_pct=max_shift / 100)
    except (OSError, UnicodeDecodeError, pd.errors.ParserError, ValueError) as exc:
        st.error(f"Scenario could not be calculated: {exc}")
        return
    a, b, c = st.columns(3)
    a.metric("System trips", f"{result['scenario_total_trips']:,}", delta=f"{result['scenario_total_trips'] - result['total_scheduled_trips']:+,} vs current")
    b.metric("Highest ratio", f"{result['scenario_max_boardings_per_trip']:.1f}", delta=f"{result['scenario_max_boardings_per_trip'] - result['current_max_boardings_per_trip']:+.1f}", delta_color="inverse")
    c.metric("Mean route ratio", f"{result['scenario_mean_route_boardings_per_trip']:.1f}", delta=f"{result['scenario_mean_route_boardings_per_trip'] - result['current_mean_route_boardings_per_trip']:+.1f}", delta_color="inverse")
    route_results = pd.DataFrame(result["routes"])
    st.dataframe(route_results, hide_index=True, column_config={
        "predicted_rides": st.column_config.NumberColumn(format="%,.0f"),
        "current_scheduled_trips": st.column_config.NumberColumn(format="%,.0f"),
        "scenario_scheduled_trips": st.column_config.NumberColumn(format="%,.0f"),
        "trip_change": st.column_config.NumberColumn(format="%+,.0f"),
        "boardings_per_current_trip": st.column_config.NumberColumn(format="%,.1f"),
        "boardings_per_scenario_trip": st.column_config.NumberColumn(format="%,.1f"),
    })
    st.download_button("Download scenario CSV", route_results.to_csv(index=False), "cta_trip_allocation_scenario.csv", "text/csv")


def render_methods(report: dict, source: pd.DataFrame | None, source_sha256: str | None) -> None:
    st.subheader("Data, assumptions, and model card")
    source_info = report["source"]
    model = report["model_selection"]
    artifacts = report["artifacts"]["final_refit"]
    policy = report["information_policy"]
    st.markdown("#### Dataset and lineage")
    st.markdown(
        f"- **Outcome:** CTA measured daily bus rides by route.\n"
        f"- **Model evaluation window:** {source_info['ridership_date_range_used_for_evaluation'][0]} to {source_info['ridership_date_range_used_for_evaluation'][1]}.\n"
        f"- **Source coverage in model report:** {source_info['ridership_source_date_range'][0]} to {source_info['ridership_source_date_range'][1]}.\n"
        f"- **Current run SHA-256:** `{source_info['ridership_sha256']}`.\n"
        f"- **Mentor frozen SHA-256:** `{source_info['mentor_reference_sha256']}`. Match: **{source_info['matches_mentor_reference']}**."
    )
    if source is not None:
        st.caption(
            f"Uploaded CSV SHA-256: `{source_sha256}`. "
            f"This upload {'matches' if source_sha256 == source_info['ridership_sha256'] else 'differs from'} the evaluated source. "
            f"Rows: {len(source):,}; routes: {source['route'].nunique():,}; latest observation: {source['date'].max().date()}."
        )
    st.markdown("#### Model and evaluation policy")
    st.markdown(
        f"- **Validation selection:** {model['paired_matched_validation_winner']} by validation MAE.\n"
        f"- **Final serving refit:** {artifacts['training_rows']:,} rows from {artifacts['training_start']} through {artifacts['training_cutoff']}.\n"
        f"- **Evaluation predictions:** retained from pre-refit candidates; final refit did not change test metrics.\n"
        f"- **Reporting assumption:** {policy['assumption']} Publication timing verified: {policy['publication_timing_verified']}.\n"
        f"- **Schedule policy:** {policy['schedule_snapshot_policy']}"
    )
    st.markdown("#### Feature contract")
    st.markdown(
        "Demand features include route identity, day of week, month, weekend and Sunday/holiday day-type "
        "flags, exact-date ridership lags at 1/7/14/21/28 days, and the mean/count of available same-weekday "
        "lags. The selected model is demand-only; schedule features were evaluated as a paired challenger."
    )
    st.markdown("#### Scope limits")
    st.markdown(
        "Daily boardings do not reveal simultaneous onboard occupancy, unique riders, directional loads, "
        "capacity, waiting, delays, or completed service. Route comparisons and trip scenarios are screening "
        "evidence only. Service changes need route geometry, travel-time and fleet constraints, accessibility "
        "and equity review, and a transit planner."
    )
    paired = report["paired_matched_experiment"]
    winner = model["paired_matched_validation_winner"]
    test = paired["test_metrics_common_methods"]
    baseline = test["past_four_same_weekdays"]
    selected_test = test[winner]
    manifest = {
        "project": "CTA RouteRanker",
        "artifact_version": "3.0.0",
        "selected_model": winner,
        "evaluation": {
            "selection_rule": model["selected_on"],
            "validation": model["selected_validation_metrics"],
            "test_selected_model": selected_test,
            "test_past_four_same_weekdays_baseline": baseline,
            "test_mae_reduction_vs_baseline_pct": round(
                100 * (baseline["mae"] - selected_test["mae"]) / baseline["mae"], 3
            ),
            "window": source_info["ridership_date_range_used_for_evaluation"],
        },
        "data_lineage": {
            "evaluation_source_sha256": source_info["ridership_sha256"],
            "mentor_reference_sha256": source_info["mentor_reference_sha256"],
            "evaluation_source_matches_mentor": source_info["matches_mentor_reference"],
            "active_upload_sha256": source_sha256,
            "active_upload_matches_evaluation_source": (
                source_sha256 == source_info["ridership_sha256"] if source_sha256 else None
            ),
        },
        "serving_policy": {
            "reporting_delay_days": policy["reporting_delay_days"],
            "publication_timing_verified": policy["publication_timing_verified"],
            "daytype": policy["daytype"],
            "final_refit_training_cutoff": artifacts["training_cutoff"],
            "final_refit_training_rows": artifacts["training_rows"],
        },
        "limitations": [
            "Retrospective development evidence; the June-July test window was previously inspected.",
            "The assumed one-day ridership publication delay is unverified.",
            "Daily boardings are not occupancy, crowding, service quality, or a causal service measure.",
        ],
    }
    if not source_info["matches_mentor_reference"]:
        manifest["limitations"].append("The evaluation source does not match the mentor frozen CSV.")
    st.download_button(
        "Download evidence and data-lineage JSON",
        data=json.dumps(manifest, indent=2, sort_keys=True),
        file_name="cta_routeranker_evidence_manifest.json",
        mime="application/json",
        help="Captures the displayed evaluation metrics, input fingerprints, serving assumptions, and known limits.",
    )


def main() -> None:
    st.set_page_config(page_title="CTA RouteRanker", page_icon="🚌", layout="wide")
    st.title("CTA RouteRanker")
    st.caption("Chicago bus demand exploration · forecast evidence · bounded planning scenarios")

    if not REPORT_PATH.exists():
        st.error(f"Model-selection report not found: {REPORT_PATH}")
        st.stop()
    try:
        report = load_report(str(REPORT_PATH), REPORT_PATH.stat().st_mtime)
    except (OSError, json.JSONDecodeError) as exc:
        st.error(f"Could not read the model-selection report: {exc}")
        st.stop()

    with st.sidebar:
        st.header("Chicago planning workspace")
        workspace = st.radio(
            "Workspace",
            ["Network map", "Overview", "Routes", "Forecast evidence", "Historical replay", "One-day forecast", "Scenarios", "Methods & data"],
            label_visibility="collapsed",
            key="workspace_navigation_v2",
        )
        st.divider()
        st.caption("Ridership data")
        source_upload = st.file_uploader("CTA ridership CSV", type=["csv"], key="shared_ridership")
        source = None
        source_sha256 = None
        if source_upload is not None:
            try:
                source_bytes = source_upload.getvalue()
                source_sha256 = hashlib.sha256(source_bytes).hexdigest()
                source = load_uploaded_ridership(source_bytes)
            except (OSError, ValueError, pd.errors.ParserError, UnicodeDecodeError) as exc:
                st.error(f"Ridership file rejected: {exc}")
        elif RIDERSHIP_PATH.is_file():
            try:
                stat = RIDERSHIP_PATH.stat()
                source, source_sha256 = load_local_ridership(str(RIDERSHIP_PATH), stat.st_mtime, stat.st_size)
            except (OSError, ValueError, pd.errors.ParserError, UnicodeDecodeError) as exc:
                st.error(f"Local ridership file rejected: {exc}")
        st.divider()
        st.caption("Route changes are never recommended automatically. Review scenario assumptions before use.")
    if workspace == "Network map":
        render_network_map(source)
    elif workspace == "Overview":
        render_overview(report, source, source_sha256)
    elif workspace == "Routes":
        render_routes(source)
    elif workspace == "Forecast evidence":
        render_evaluation(report)
    elif workspace == "Historical replay":
        render_replay()
    elif workspace == "One-day forecast":
        render_forecast(report, source, source_sha256)
    elif workspace == "Scenarios":
        render_scenario()
    else:
        render_methods(report, source, source_sha256)


if __name__ == "__main__":
    main()
