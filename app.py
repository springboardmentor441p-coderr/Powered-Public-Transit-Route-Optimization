"""Streamlit route forecast evaluation and review dashboard."""

import json
from datetime import timedelta
from io import BytesIO
from pathlib import Path

import pandas as pd
import streamlit as st

from src.data_loader import load_bus_ridership
from src.predict_v3 import load_v3_bundle, predict_daily_routes_from_bundle

REPORT_PATH = Path(__file__).parent / "outputs" / "reports" / "service_model_comparison.json"
V3_REPORT_PATH = Path(__file__).parent / "outputs" / "reports" / "model_selection_v3.json"

MODEL_LABELS = {
    "past_four_same_weekdays": "Past four same weekdays",
    "last_week_same_day": "Last week same day",
    "demand_only": "Demand only",
    "service_aware": "Service aware",
    "hybrid": "Adaptive hybrid",
}


def _format_metric(value: float | None, metric: str) -> str:
    if value is None:
        return "—"
    if metric == "wape":
        return f"{value:.2%}"
    return f"{value:,.1f} rides"


@st.cache_data

def load_report(path: str, modified_time: float) -> dict:
    del modified_time  # Include the file modification time in Streamlit's cache key.
    return json.loads(Path(path).read_text())


@st.cache_data(max_entries=3)
def load_uploaded_ridership(contents: bytes) -> pd.DataFrame:
    return load_bus_ridership(BytesIO(contents))


@st.cache_data(max_entries=3)
def load_uploaded_service(contents: bytes) -> pd.DataFrame:
    return pd.read_csv(BytesIO(contents), dtype={"route": "string", "source_snapshot": "string"})


@st.cache_resource(max_entries=2)
def load_uploaded_v3_bundle(contents: bytes) -> dict:
    return load_v3_bundle(contents)


def _fixed_origin_data(report: dict):
    fixed = report["fixed_origin_evaluation"]
    overall = {
        "past_four_same_weekdays": fixed["seasonal_baselines"]["past_four_same_weekdays"],
        "last_week_same_day": fixed["seasonal_baselines"]["last_week_same_day"],
    }
    routes = {
        "past_four_same_weekdays": fixed["seasonal_baselines_by_route"]["past_four_same_weekdays"],
        "last_week_same_day": fixed["seasonal_baselines_by_route"]["last_week_same_day"],
    }
    daytypes = {}
    for name in ("past_four_same_weekdays", "last_week_same_day"):
        for daytype, metrics in fixed["seasonal_baselines_by_daytype"][name].items():
            daytypes.setdefault(daytype, {})[name] = metrics
    for name, result in fixed["models"].items():
        overall[name] = result["metrics"]
        routes[name] = result["metrics_by_route"]
        for daytype, metrics in result["metrics_by_daytype"].items():
            daytypes.setdefault(daytype, {})[name] = metrics
    description = (
        f"Forecast origin {fixed['forecast_origin']} · window {fixed['forecast_window'][0]} to "
        f"{fixed['forecast_window'][1]} · schedule {fixed['schedule_snapshot']} "
        f"(available {fixed['schedule_available_from']}) · "
        f"coverage {fixed['scored_rows']:,}/{fixed['test_observation_rows']:,} "
        f"({fixed['coverage_pct']:.2f}%)"
    )
    return fixed, overall, routes, daytypes, description


def _walk_forward_data(report: dict):
    walk = report["hybrid_walk_forward_development"]
    description = (
        f"Monthly refits · {len(walk['folds'])} folds from "
        f"{walk['folds'][0]['forecast_window'][0]} to {walk['folds'][-1]['forecast_window'][1]} · "
        f"coverage {walk['matched_rows']:,}/{walk['demand_rows']:,} "
        f"({walk['matched_coverage_pct']:.2f}%) · daily rolling one-step scores"
    )
    return walk, walk["overall_metrics"], walk["metrics_by_route"], walk["metrics_by_daytype"], description


st.set_page_config(page_title="CTA Route Review", page_icon="🚌", layout="wide")
st.title("CTA Route Forecast Review")
st.caption(
    "Review forecast accuracy by horizon, route, and day type. These are model evaluation results, "
    "not live predictions or service-quality rankings."
)

if not REPORT_PATH.exists():
    st.error(f"Evaluation report not found: {REPORT_PATH}")
    st.stop()

try:
    report = load_report(str(REPORT_PATH), REPORT_PATH.stat().st_mtime)
except (OSError, json.JSONDecodeError) as exc:
    st.error(f"Could not read the evaluation report: {exc}")
    st.stop()

mode = st.sidebar.radio(
    "Evaluation horizon",
    ["Fixed-origin August", "Daily rolling development"],
    help="These scores answer different questions. Fixed-origin does not use actual rides from its forecast window as future lags.",
)
if mode == "Fixed-origin August":
    data, overall, route_metrics, daytype_metrics, description = _fixed_origin_data(report)
    model_choices = list(overall)
    default_model = "service_aware"
    evaluation_note = (
        "Recursive forecast: one forecast issued at the end of July for all of August. "
        "The seasonal baseline scored better overall in this evaluation."
    )
else:
    data, overall, route_metrics, daytype_metrics, description = _walk_forward_data(report)
    model_choices = list(overall)
    default_model = "service_aware"
    evaluation_note = (
        "Daily rolling one-step development scores: earlier observed rides are available as lag features. "
        "The model is refit monthly. August was previously inspected during development."
    )

st.caption(description)
st.info(evaluation_note)

model_key = st.sidebar.selectbox(
    "Forecast or baseline to review",
    model_choices,
    index=model_choices.index(default_model) if default_model in model_choices else 0,
    format_func=lambda key: MODEL_LABELS.get(key, key),
)
reference_key = "past_four_same_weekdays"
selected = overall[model_key]
reference = overall[reference_key]
mae_change = selected["mae"] - reference["mae"]
change_word = "higher" if mae_change > 0 else "lower"

kpi1, kpi2, kpi3, kpi4 = st.columns(4)
kpi1.metric("Selected method MAE", _format_metric(selected.get("mae"), "mae"))
kpi2.metric("Past-four-weekday MAE", _format_metric(reference.get("mae"), "mae"))
kpi3.metric("Selected method RMSE", _format_metric(selected.get("rmse"), "rmse"))
kpi4.metric("Selected method WAPE", _format_metric(selected.get("wape"), "wape"))
st.caption(
    f"Selected method MAE is {abs(mae_change):,.1f} rides {change_word} than the past-four-same-weekdays baseline. "
    "Positive route differences below mean the selected method has higher error."
)

if V3_REPORT_PATH.exists():
    try:
        v3_report = load_report(str(V3_REPORT_PATH), V3_REPORT_PATH.stat().st_mtime)
        v3_selection = v3_report["model_selection"]
        v3_validation = v3_selection["selected_validation_metrics"]
        with st.container(border=True):
            st.subheader("Selected v3 one-day model")
            st.caption(
                f"{v3_selection['serving_configuration']} · {v3_selection['serving_estimator']} · "
                "selected by MAE on the matched validation split"
            )
            v3_col1, v3_col2, v3_col3 = st.columns(3)
            v3_col1.metric("Validation MAE", f"{v3_validation['mae']:,.1f} rides")
            v3_col2.metric("Validation RMSE", f"{v3_validation['rmse']:,.1f} rides")
            v3_col3.metric("Validation WAPE", f"{v3_validation['wape']:.2%}")
            st.caption(
                "Development result: the source hash differs from the mentor's frozen export, "
                "June–July was seen in earlier iterations, and the replay assumes rides through D−1 are available."
            )
    except (OSError, KeyError, json.JSONDecodeError, TypeError) as exc:
        st.warning(f"The v3 model-selection summary could not be shown: {exc}")

st.subheader("Error by day type")
day_rows = []
for daytype in sorted(daytype_metrics):
    values = daytype_metrics[daytype]
    selected_metrics = values.get(model_key)
    reference_metrics = values.get(reference_key)
    if selected_metrics and reference_metrics:
        day_rows.append({
            "Day type": {"W": "Weekday", "A": "Saturday", "U": "Sunday/holiday"}.get(daytype, daytype),
            MODEL_LABELS.get(model_key, model_key): selected_metrics["mae"],
            MODEL_LABELS[reference_key]: reference_metrics["mae"],
        })
if day_rows:
    day_frame = pd.DataFrame(day_rows).set_index("Day type")
    st.bar_chart(day_frame)
    st.dataframe(day_frame.style.format("{:.1f} rides"))
else:
    st.info("Day-type metrics are unavailable for this report.")

st.subheader("Route review")
route_rows = []
for route, metrics_by_method in route_metrics.items():
    forecast = metrics_by_method.get(model_key)
    baseline = metrics_by_method.get(reference_key)
    if not forecast or not baseline:
        continue
    delta = forecast["mae"] - baseline["mae"]
    route_rows.append({
        "Route": str(route),
        "Selected method MAE": forecast["mae"],
        "Seasonal baseline MAE": baseline["mae"],
        "MAE difference": delta,
        "Difference %": (100 * delta / baseline["mae"]) if baseline["mae"] else None,
        "Scored route-days": forecast.get("scored_rows"),
    })
route_frame = pd.DataFrame(route_rows)
if route_frame.empty:
    st.warning("Route-level scores are unavailable for this report.")
else:
    sort_choice = st.selectbox(
        "Sort routes",
        ["Largest model error vs baseline", "Largest model gain vs baseline", "Route number"],
    )
    if sort_choice == "Largest model error vs baseline":
        route_frame = route_frame.sort_values("MAE difference", ascending=False)
    elif sort_choice == "Largest model gain vs baseline":
        route_frame = route_frame.sort_values("MAE difference", ascending=True)
    else:
        route_frame = route_frame.sort_values("Route", key=lambda values: values.str.extract(r"(\d+)")[0].astype(float))
    route_filter = st.selectbox("Route filter", ["All routes", *route_frame["Route"].tolist()])
    if route_filter != "All routes":
        route_frame = route_frame.loc[route_frame["Route"].eq(route_filter)]
    st.dataframe(
        route_frame.style.format({
            "Selected method MAE": "{:.1f}",
            "Seasonal baseline MAE": "{:.1f}",
            "MAE difference": "{:+.1f}",
            "Difference %": "{:+.1f}%",
        }),
        hide_index=True,
    )

with st.expander("How to read this review"):
    st.markdown(
        "- MAE is the average absolute difference in measured daily boardings per route-day.\n"
        "- A positive route difference means the selected method made larger errors than the seasonal baseline for that route.\n"
        "- Route scores measure forecast error, not crowding, unmet demand, route quality, or the effect of changing service.\n"
        "- The fixed-origin and daily rolling modes use different forecast assumptions and should not be compared as if they were the same task."
    )
    st.caption(f"Report source: `{REPORT_PATH.relative_to(Path(__file__).parent)}`")

st.divider()
st.header("One-day forecast with the v3 model")
st.write(
    "Upload the Colab result ZIP and CTA ridership CSV to rank route boardings for one date. "
    "The forecast date must follow the latest ride observation in the uploaded file."
)
st.info(
    "Choose the CTA day type for the target date (W weekday, A Saturday, U Sunday/holiday). "
    "Confirm holidays yourself; the app does not infer the official CTA holiday calendar."
)

forecast_model_upload = st.file_uploader(
    "Colab results ZIP or v3 joblib model",
    type=["zip", "joblib"],
    key="v3_model_upload",
    help="Use cta_route_ranker_v3_results.zip from the Colab final cell, or its cta_ridership_v3.joblib member.",
)
forecast_history_upload = st.file_uploader(
    "CTA daily bus ridership CSV",
    type=["csv"],
    key="v3_ridership_upload",
    help="Upload the real CTA export containing route, date, daytype, and rides.",
)

if forecast_model_upload is not None and forecast_history_upload is not None:
    try:
        model_bundle = load_uploaded_v3_bundle(forecast_model_upload.getvalue())
        forecast_history = load_uploaded_ridership(forecast_history_upload.getvalue())
    except Exception as exc:
        st.error(f"Could not load the model or ridership CSV: {exc}")
    else:
        latest_observed_date = forecast_history["date"].max().date()
        earliest_forecast_date = latest_observed_date + timedelta(
            days=int(model_bundle["reporting_delay_days"])
        )
        available_routes = sorted(forecast_history["route"].astype(str).unique().tolist())
        service_upload = None
        if model_bundle.get("model_requires_schedule"):
            service_upload = st.file_uploader(
                "Route/date service schedule CSV",
                type=["csv"],
                key="v3_service_upload",
                help="Required for a service-aware model; include archive_available_from and capture dates strictly before the target date.",
            )

        st.caption(
            f"Latest ride date in this CSV: {latest_observed_date.isoformat()}. "
            f"Earliest permitted target date with the model's one-day delay: {earliest_forecast_date.isoformat()}."
        )
        with st.form("v3_one_day_forecast"):
            forecast_date = st.date_input(
                "Forecast date",
                value=earliest_forecast_date,
                min_value=earliest_forecast_date,
                key="v3_forecast_date",
            )
            daytype_label = st.selectbox(
                "CTA day type",
                ["W", "A", "U"],
                format_func=lambda value: {
                    "W": "W — Weekday",
                    "A": "A — Saturday",
                    "U": "U — Sunday/holiday",
                }[value],
                key="v3_forecast_daytype",
            )
            selected_routes = st.multiselect(
                "Routes to rank",
                available_routes,
                default=available_routes,
                key="v3_forecast_routes",
            )
            forecast_submitted = st.form_submit_button("Generate route forecasts")

        if forecast_submitted:
            if not selected_routes:
                st.error("Select at least one route.")
            elif model_bundle.get("model_requires_schedule") and service_upload is None:
                st.error("This selected model requires the route/date service schedule CSV.")
            else:
                try:
                    target_frame = pd.DataFrame({
                        "route": selected_routes,
                        "date": forecast_date,
                        "daytype": daytype_label,
                    })
                    service_frame = (
                        load_uploaded_service(service_upload.getvalue())
                        if service_upload is not None else None
                    )
                    forecast_frame = predict_daily_routes_from_bundle(
                        model_bundle, forecast_history, target_frame, service_frame
                    )
                except (OSError, KeyError, ValueError, pd.errors.ParserError, UnicodeDecodeError) as exc:
                    st.error(f"Could not create the forecast: {exc}")
                else:
                    ranked_forecasts = forecast_frame.sort_values(
                        "predicted_rides", ascending=False
                    ).reset_index(drop=True)
                    forecast_total = float(ranked_forecasts["predicted_rides"].sum())
                    st.metric("Predicted boardings across selected routes", f"{forecast_total:,.0f}")
                    st.caption(
                        f"Method: {model_bundle['serving_method']} · model trained through "
                        f"{model_bundle.get('training_cutoff', 'unknown date')} · issue date: {forecast_date.isoformat()} · "
                        f"ridership inputs allowed through {(forecast_date - timedelta(days=model_bundle['reporting_delay_days'])).isoformat()}"
                    )
                    st.dataframe(
                        ranked_forecasts,
                        hide_index=True,
                        column_config={
                            "predicted_rides": st.column_config.NumberColumn(
                                "Predicted daily boardings", format="%,.0f"
                            ),
                        },
                    )
                    st.download_button(
                        "Download route forecast CSV",
                        ranked_forecasts.to_csv(index=False),
                        file_name=f"cta_route_forecast_{forecast_date.isoformat()}.csv",
                        mime="text/csv",
                    )
                    st.caption(
                        "Route order reflects predicted daily boardings only. It is not passenger load, crowding, "
                        "route quality, or a service-change recommendation."
                    )

st.divider()
st.header("Trip allocation scenario sandbox")
st.write(
    "Upload one row per route with predicted daily boardings and current scheduled daily trips. "
    "The scenario keeps the systemwide trip total unchanged and limits each route's trip change."
)
st.warning(
    "This balances an aggregate boardings-per-trip proxy. It does not estimate vehicle load or crowding, "
    "and it omits fleet, travel-time, peak-period, transfer, equity, and route-overlap constraints. "
    "Review scenarios with a transit planner before using them."
)

sample_routes = pd.DataFrame({
    "route": ["Example A", "Example B", "Example C"],
    "predicted_rides": [12000, 7000, 5000],
    "scheduled_trips": [20, 16, 14],
})
blank_template = pd.DataFrame(columns=["route", "predicted_rides", "scheduled_trips"])
scenario_template, scenario_example = st.columns(2)
scenario_template.download_button(
    "Download blank CSV template",
    blank_template.to_csv(index=False),
    file_name="route_scenario_template.csv",
    mime="text/csv",
)
scenario_example.download_button(
    "Download synthetic example CSV",
    sample_routes.to_csv(index=False),
    file_name="synthetic_route_scenario_example.csv",
    mime="text/csv",
    help="Contains invented example values for trying the calculator; it is not CTA data.",
)

scenario_upload = st.file_uploader(
    "Upload route forecast and scheduled trips CSV",
    type=["csv"],
    help="Required columns: route, predicted_rides, scheduled_trips. Use forecasts and trip counts for the same route and date/window.",
)
max_shift_percent = st.slider(
    "Maximum change allowed per route",
    min_value=0,
    max_value=50,
    value=10,
    step=5,
    format="%d%%",
)
if scenario_upload is not None:
    try:
        from src.scenarios import optimize_trip_allocation

        scenario_input = pd.read_csv(scenario_upload, dtype={"route": "string"})
        scenario_result = optimize_trip_allocation(
            scenario_input, max_shift_pct=max_shift_percent / 100
        )
        result_routes = pd.DataFrame(scenario_result["routes"])
        metric_a, metric_b, metric_c = st.columns(3)
        metric_a.metric("Scheduled trips", f"{scenario_result['scenario_total_trips']:,}",
                        delta=f"{scenario_result['scenario_total_trips'] - scenario_result['total_scheduled_trips']:+,} vs current")
        metric_b.metric("Highest boardings per trip", f"{scenario_result['scenario_max_boardings_per_trip']:.1f}",
                        delta=f"{scenario_result['scenario_max_boardings_per_trip'] - scenario_result['current_max_boardings_per_trip']:+.1f} vs current",
                        delta_color="inverse")
        metric_c.metric("Mean across routes", f"{scenario_result['scenario_mean_route_boardings_per_trip']:.1f}",
                        delta=f"{scenario_result['scenario_mean_route_boardings_per_trip'] - scenario_result['current_mean_route_boardings_per_trip']:+.1f} vs current",
                        delta_color="inverse")
        st.caption(scenario_result["objective"])
        st.dataframe(
            result_routes.style.format({
                "predicted_rides": "{:,.0f}",
                "current_scheduled_trips": "{:,.0f}",
                "scenario_scheduled_trips": "{:,.0f}",
                "trip_change": "{:+,.0f}",
                "boardings_per_current_trip": "{:,.1f}",
                "boardings_per_scenario_trip": "{:,.1f}",
            }),
            hide_index=True,
        )
    except (OSError, UnicodeDecodeError, pd.errors.ParserError, ValueError) as exc:
        st.error(f"Could not calculate this scenario: {exc}")
