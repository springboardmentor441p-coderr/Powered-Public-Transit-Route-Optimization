"""Streamlit route forecast evaluation and review dashboard."""

import json
from pathlib import Path

import pandas as pd
import streamlit as st

REPORT_PATH = Path(__file__).parent / "outputs" / "reports" / "service_model_comparison.json"

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
    st.dataframe(day_frame.style.format("{:.1f} rides"), use_container_width=True)
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
        use_container_width=True,
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
