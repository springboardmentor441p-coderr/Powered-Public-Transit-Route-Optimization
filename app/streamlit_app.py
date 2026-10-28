"""
RouteRanker — AI-Powered Public Transit Route Optimization & Demand Intelligence Platform
Interactive Streamlit Application: app/streamlit_app.py
"""

import os
import json
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from pathlib import Path

# Set Page Config
st.set_page_config(
    page_title="RouteRanker | Transit Intelligence",
    page_icon="🚌",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1f2937;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.05rem;
        color: #4b5563;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background-color: #f8fafc;
        border-radius: 8px;
        padding: 16px;
        border-left: 4px solid #2563eb;
    }
    .tier1-badge {
        background-color: #fee2e2;
        color: #991b1b;
        padding: 4px 8px;
        border-radius: 4px;
        font-weight: 600;
    }
    .tier2-badge {
        background-color: #e0f2fe;
        color: #075985;
        padding: 4px 8px;
        border-radius: 4px;
        font-weight: 600;
    }
    .tier3-badge {
        background-color: #fef3c7;
        color: #92400e;
        padding: 4px 8px;
        border-radius: 4px;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# Resolve Paths
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR = WORKSPACE_ROOT / "data" / "processed"
REPORTS_DIR = WORKSPACE_ROOT / "reports"

@st.cache_data
def load_data():
    df_boardings = pd.read_parquet(PROCESSED_DIR / "boardings_clean.parquet")
    df_boardings["date"] = pd.to_datetime(df_boardings["date"])

    df_rankings = pd.read_parquet(PROCESSED_DIR / "productivity_rankings.parquet")
    df_structure = pd.read_parquet(PROCESSED_DIR / "route_structure.parquet")
    df_overlap = pd.read_parquet(PROCESSED_DIR / "route_overlap.parquet")
    df_preds = pd.read_parquet(PROCESSED_DIR / "model_predictions_test.parquet")
    df_preds["date"] = pd.to_datetime(df_preds["date"])

    with open(REPORTS_DIR / "model_metrics.json", "r") as f:
        metrics_data = json.load(f)

    with open(REPORTS_DIR / "source_manifest.json", "r") as f:
        manifest_data = json.load(f)

    return df_boardings, df_rankings, df_structure, df_overlap, df_preds, metrics_data, manifest_data

try:
    df_boardings, df_rankings, df_structure, df_overlap, df_preds, metrics_data, manifest_data = load_data()
except Exception as e:
    st.error(f"Error loading processed artifacts from {PROCESSED_DIR}: {e}. Please ensure the analytics pipeline has run.")
    st.stop()

# Sidebar Navigation
st.sidebar.image("https://img.icons8.com/fluency/96/bus.png", width=70)
st.sidebar.title("RouteRanker v2.0")
st.sidebar.caption("CTA Transit Demand & Optimization Intelligence")

nav_choice = st.sidebar.radio(
    "Navigation",
    [
        "📊 Network Overview & KPIs",
        "📈 Longitudinal Trends & Demand",
        "🔍 Route Explorer & Forecasts",
        "⚖️ Route Comparison & Overlap",
        "🎯 Productivity & Review Tiers",
        "🧮 Frequency Scenario Engine",
        "🤖 ML Model Benchmark & Audit",
        "🛡️ Data Provenance & Integrity"
    ]
)

st.sidebar.markdown("---")
st.sidebar.info("""
**Data Summary**
- **Boardings:** 1,120,604 rows (2001–2026)
- **Active Bus Routes:** 124 routes
- **Test Set WAPE:** 7.34% (XGBoost)
""")

# ========================================================
# 1. NETWORK OVERVIEW & KPIS
# ========================================================
if nav_choice == "📊 Network Overview & KPIs":
    st.markdown('<div class="main-header">🚌 CTA Transit Network Overview</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Executive summary of ridership volume, operational supply, and schedule alignment.</div>', unsafe_allow_html=True)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Historical Records", f"{len(df_boardings):,}", "2001 – 2026")
    with col2:
        st.metric("Active Bus Routes", f"{df_rankings['route_id'].nunique()}", "GTFS Schedule Match")
    with col3:
        mean_2026 = df_boardings[df_boardings["date"] >= "2026-01-01"]["rides"].mean()
        st.metric("Avg Daily Boardings (2026)", f"{int(mean_2026):,}", "Per route-day")
    with col4:
        top_route = df_rankings.iloc[0]["route_id"]
        top_prod = df_rankings.iloc[0]["rides_per_weekday_trip"]
        st.metric("Top Productive Route", f"Route {top_route}", f"{top_prod} rides/trip")

    st.markdown("---")

    col_left, col_right = st.columns([1, 1])
    with col_left:
        st.subheader("Top 10 Busiest Weekday Bus Routes (2026)")
        top10_w = df_rankings.sort_values("mean_weekday_rides", ascending=False).head(10)
        fig_bar = px.bar(
            top10_w,
            x="route_id",
            y="mean_weekday_rides",
            color="mean_weekday_rides",
            color_continuous_scale="Blues",
            labels={"route_id": "Route ID", "mean_weekday_rides": "Avg Weekday Rides"},
            title="Average Weekday Boardings"
        )
        fig_bar.update_layout(xaxis_type='category')
        st.plotly_chart(fig_bar, use_container_width=True)

    with col_right:
        st.subheader("Review Priority Distribution")
        priority_counts = df_rankings["review_priority"].value_counts().reset_index()
        priority_counts.columns = ["Priority Tier", "Count"]
        fig_pie = px.pie(
            priority_counts,
            values="Count",
            names="Priority Tier",
            color="Priority Tier",
            color_discrete_map={
                "Tier 1: Frequency Expansion Review (High Boardings-per-Trip)": "#ef4444",
                "Tier 2: Balanced Operational Baseline": "#3b82f6",
                "Tier 3: Route Consolidation Review (Low Boardings-per-Trip, High Overlap)": "#f59e0b"
            },
            hole=0.4
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    st.subheader("Operational Archetype Breakdown")
    st.dataframe(
        df_rankings[["route_id", "route_short_name", "mean_weekday_rides", "weekday_scheduled_trips", "rides_per_weekday_trip", "archetype", "review_priority"]].head(15),
        use_container_width=True
    )

# ========================================================
# 2. LONGITUDINAL TRENDS & DEMAND
# ========================================================
elif nav_choice == "📈 Longitudinal Trends & Demand":
    st.markdown('<div class="main-header">📈 Longitudinal Ridership & Seasonality</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Macro demand dynamics from 2001 to 2026, including pandemic disruption and daytype variance.</div>', unsafe_allow_html=True)

    st.subheader("Daily Total Network Boardings (2001 – 2026)")
    daily_network = df_boardings.groupby("date")["rides"].sum().reset_index()
    fig_line = px.line(
        daily_network,
        x="date",
        y="rides",
        title="CTA Bus Network: Daily Boardings Timeline",
        labels={"rides": "Total Daily Boardings", "date": "Date"}
    )
    fig_line.add_vline(x=pd.to_datetime("2020-03-15"), line_dash="dash", line_color="red", annotation_text="COVID-19 Lockdown")
    st.plotly_chart(fig_line, use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Monthly Volume (2018–2026 Modern Horizon)")
        df_modern = df_boardings[df_boardings["date"] >= "2018-01-01"].copy()
        df_modern["ym"] = df_modern["date"].dt.to_period("M").dt.to_timestamp()
        monthly = df_modern.groupby("ym")["rides"].sum().reset_index()
        fig_m = px.bar(
            monthly,
            x="ym",
            y="rides",
            labels={"rides": "Total Monthly Boardings", "ym": "Month"},
            color="rides",
            color_continuous_scale="Viridis"
        )
        st.plotly_chart(fig_m, use_container_width=True)

    with col2:
        st.subheader("Day of Week Volume Variance")
        df_modern["dow_name"] = df_modern["date"].dt.day_name()
        dow_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        dow_agg = df_modern.groupby("dow_name")["rides"].mean().reindex(dow_order).reset_index()
        fig_dow = px.bar(
            dow_agg,
            x="dow_name",
            y="rides",
            color="rides",
            labels={"rides": "Mean Daily Boardings per Route", "dow_name": "Day of Week"},
            color_continuous_scale="Teal"
        )
        st.plotly_chart(fig_dow, use_container_width=True)

# ========================================================
# 3. ROUTE EXPLORER & FORECASTS
# ========================================================
elif nav_choice == "🔍 Route Explorer & Forecasts":
    st.markdown('<div class="main-header">🔍 Route Explorer & Out-of-Sample Forecasts</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Inspect historical boardings and evaluate machine learning predictions on test set (Jan – Jul 2026).</div>', unsafe_allow_html=True)

    all_routes = sorted(df_rankings["route_id"].unique())
    selected_route = st.selectbox("Select Bus Route:", all_routes, index=all_routes.index("79") if "79" in all_routes else 0)

    route_info = df_rankings[df_rankings["route_id"] == selected_route].iloc[0]

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Avg Weekday Rides", f"{int(route_info['mean_weekday_rides']):,}")
    with col2:
        st.metric("Scheduled Weekday Trips", f"{int(route_info['weekday_scheduled_trips'])}")
    with col3:
        st.metric("Productivity Ratio", f"{route_info['rides_per_weekday_trip']} rides/trip")
    with col4:
        st.metric("Review Tier", route_info["review_priority"].split(":")[0])

    st.markdown("---")

    # Filter predictions for route
    route_preds = df_preds[df_preds["route"] == selected_route].sort_values("date")
    if not route_preds.empty:
        st.subheader(f"Route {selected_route}: Out-of-Sample Demand Forecasts (2026 Test Set)")
        fig_forecast = go.Figure()
        fig_forecast.add_trace(go.Scatter(x=route_preds["date"], y=route_preds["rides"], mode="lines", name="Actual Boardings", line=dict(color="#0f172a", width=2)))
        fig_forecast.add_trace(go.Scatter(x=route_preds["date"], y=route_preds["pred_xgboost"], mode="lines", name="XGBoost Prediction", line=dict(color="#ef4444", width=1.8, dash="dash")))
        fig_forecast.add_trace(go.Scatter(x=route_preds["date"], y=route_preds["pred_random_forest"], mode="lines", name="Random Forest", line=dict(color="#10b981", width=1.2, dash="dot")))
        fig_forecast.add_trace(go.Scatter(x=route_preds["date"], y=route_preds["pred_baseline_lag7"], mode="lines", name="Lag-7 Baseline", line=dict(color="#94a3b8", width=1, dash="dot")))

        fig_forecast.update_layout(
            title=f"Daily Boarding Demand vs. Predictions for Route {selected_route}",
            xaxis_title="Date",
            yaxis_title="Daily Passenger Trips",
            hovermode="x unified"
        )
        st.plotly_chart(fig_forecast, use_container_width=True)

        # Route Specific Error Metrics
        route_mae = float(np.mean(np.abs(route_preds["rides"] - route_preds["pred_xgboost"])))
        route_wape = float((np.sum(np.abs(route_preds["rides"] - route_preds["pred_xgboost"])) / np.sum(route_preds["rides"])) * 100)

        st.write(f"**Route {selected_route} XGBoost Performance:** MAE: `{route_mae:.1f}` rides | WAPE: `{route_wape:.2f}%`")
    else:
        st.warning(f"No test-set predictions found for Route {selected_route}.")

# ========================================================
# 4. ROUTE COMPARISON & OVERLAP
# ========================================================
elif nav_choice == "⚖️ Route Comparison & Overlap":
    st.markdown('<div class="main-header">⚖️ Route Comparison & Corridor Overlap</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Evaluate pairwise corridor overlap (Jaccard similarity and containment) between bus lines.</div>', unsafe_allow_html=True)

    col_a, col_b = st.columns(2)
    routes_list = sorted(df_rankings["route_id"].unique())
    with col_a:
        r_a = st.selectbox("Select Route A:", routes_list, index=routes_list.index("49") if "49" in routes_list else 0)
    with col_b:
        r_b = st.selectbox("Select Route B:", routes_list, index=routes_list.index("X49") if "X49" in routes_list else 1)

    p_a = df_rankings[df_rankings["route_id"] == r_a].iloc[0]
    p_b = df_rankings[df_rankings["route_id"] == r_b].iloc[0]

    comp_df = pd.DataFrame({
        "Metric": [
            "Route Long Name", "Stops Served", "Exclusive Stops", "Exclusivity %",
            "Weekday Scheduled Trips", "Avg Weekday Rides", "Rides per Trip", "Archetype", "Review Priority"
        ],
        f"Route {r_a}": [
            p_a["route_long_name"], p_a["stops_count"], p_a["exclusive_stops"], f"{p_a['exclusivity_pct']}%",
            p_a["weekday_scheduled_trips"], f"{int(p_a['mean_weekday_rides']):,}", p_a["rides_per_weekday_trip"],
            p_a["archetype"], p_a["review_priority"]
        ],
        f"Route {r_b}": [
            p_b["route_long_name"], p_b["stops_count"], p_b["exclusive_stops"], f"{p_b['exclusivity_pct']}%",
            p_b["weekday_scheduled_trips"], f"{int(p_b['mean_weekday_rides']):,}", p_b["rides_per_weekday_trip"],
            p_b["archetype"], p_b["review_priority"]
        ]
    })
    st.table(comp_df)

    # Check Overlap
    pair_match = df_overlap[
        ((df_overlap["route_a"] == r_a) & (df_overlap["route_b"] == r_b)) |
        ((df_overlap["route_a"] == r_b) & (df_overlap["route_b"] == r_a))
    ]

    st.subheader(f"Corridor Overlap: Route {r_a} vs Route {r_b}")
    if not pair_match.empty:
        match_info = pair_match.iloc[0]
        col1, col2, col3 = st.columns(3)
        col1.metric("Shared Stops", f"{match_info['shared_stops']}")
        col2.metric("Jaccard Overlap", f"{match_info['jaccard_similarity'] * 100:.1f}%")
        col3.metric("Smaller Route Containment", f"{match_info['smaller_route_containment'] * 100:.1f}%")

        if match_info['smaller_route_containment'] > 0.8:
            st.warning(f"**High Redundancy Detected:** One route is {match_info['smaller_route_containment']*100:.1f}% contained within the other. Candidate for headway harmonization or branch consolidation.")
    else:
        st.info("These two routes share 0 stops (disjoint transit corridors).")

# ========================================================
# 5. PRODUCTIVITY & REVIEW TIERS
# ========================================================
elif nav_choice == "🎯 Productivity & Review Tiers":
    st.markdown('<div class="main-header">🎯 Route Productivity & Review Priorities</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Evaluating passenger boardings against GTFS scheduled supply to flag capacity imbalances.</div>', unsafe_allow_html=True)

    tier_filter = st.selectbox(
        "Filter by Review Priority Tier:",
        ["All Routes", "Tier 1: Expand Frequency", "Tier 2: Balanced", "Tier 3: Streamline / Consolidate"]
    )

    df_filtered = df_rankings.copy()
    if tier_filter == "Tier 1: Expand Frequency":
        df_filtered = df_filtered[df_filtered["review_priority"].str.contains("Tier 1")]
    elif tier_filter == "Tier 2: Balanced":
        df_filtered = df_filtered[df_filtered["review_priority"].str.contains("Tier 2")]
    elif tier_filter == "Tier 3: Streamline / Consolidate":
        df_filtered = df_filtered[df_filtered["review_priority"].str.contains("Tier 3")]

    st.subheader(f"Route Productivity Leaderboard ({len(df_filtered)} routes)")
    st.dataframe(
        df_filtered[["route_id", "route_short_name", "mean_weekday_rides", "weekday_scheduled_trips", "rides_per_weekday_trip", "exclusivity_pct", "archetype", "review_priority"]],
        use_container_width=True
    )

    st.subheader("Scheduled Supply vs. Observed Passenger Volume")
    fig_scatter = px.scatter(
        df_rankings,
        x="weekday_scheduled_trips",
        y="mean_weekday_rides",
        color="review_priority",
        hover_data=["route_id", "route_short_name", "rides_per_weekday_trip"],
        labels={"weekday_scheduled_trips": "Scheduled Weekday Trips", "mean_weekday_rides": "Avg Weekday Rides"},
        color_discrete_map={
            "Tier 1: Frequency Expansion Review (High Boardings-per-Trip)": "#ef4444",
            "Tier 2: Balanced Operational Baseline": "#3b82f6",
            "Tier 3: Route Consolidation Review (Low Boardings-per-Trip, High Overlap)": "#f59e0b"
        }
    )
    st.plotly_chart(fig_scatter, use_container_width=True)

# ========================================================
# 6. FREQUENCY SCENARIO ENGINE
# ========================================================
elif nav_choice == "🧮 Frequency Scenario Engine":
    st.markdown('<div class="main-header">🧮 Operational Frequency Scenario Simulator</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Simulate frequency adjustments and calculate ridership response using empirical transit service elasticities.</div>', unsafe_allow_html=True)

    routes_list = sorted(df_rankings["route_id"].unique())
    sel_route = st.selectbox("Select Route for Scenario:", routes_list, index=routes_list.index("8") if "8" in routes_list else 0)

    r_prof = df_rankings[df_rankings["route_id"] == sel_route].iloc[0]

    col1, col2 = st.columns([1, 1])
    with col1:
        st.subheader("Scenario Parameters")
        pct_change = st.slider("Service Frequency Adjustment (%):", min_value=-40, max_value=50, value=20, step=5)
        elasticity = st.slider("Transit Frequency Elasticity (ε):", min_value=0.20, max_value=0.60, value=0.42, step=0.02)
        cost_per_trip = st.number_input("Est. Operating Cost per Trip ($):", value=85.0, step=5.0)

    # Run calculation via scenario engine
    from src.optimization.scenario_engine import simulate_frequency_adjustment
    res = simulate_frequency_adjustment(
        route_id=sel_route,
        base_weekday_rides=r_prof["mean_weekday_rides"],
        base_scheduled_trips=int(r_prof["weekday_scheduled_trips"]),
        percent_trip_change=pct_change,
        elasticity=elasticity,
        cost_per_trip=cost_per_trip
    )

    with col2:
        st.subheader("Simulation Results")
        st.markdown(f"**Planner Recommendation:** *{res['recommendation']}*")

        m1, m2 = st.columns(2)
        m1.metric("Scheduled Trips", f"{res['simulated_scheduled_trips']}", f"{res['delta_trips']:+d} trips")
        m2.metric("Projected Weekday Rides", f"{int(res['simulated_weekday_rides']):,}", f"{int(res['delta_rides']):+d} rides")

        m3, m4 = st.columns(2)
        m3.metric("Rides per Trip", f"{res['simulated_rides_per_trip']}", f"{res['simulated_rides_per_trip'] - res['base_rides_per_trip']:+.2f}")
        m4.metric("Daily Cost Delta", f"${res['daily_operating_cost_delta_usd']:+,.2f}")

    st.markdown("---")
    st.subheader("Scenario Comparison Table")
    st.table(pd.DataFrame([res]))

# ========================================================
# 7. ML MODEL BENCHMARK & AUDIT
# ========================================================
elif nav_choice == "🤖 ML Model Benchmark & Audit":
    st.markdown('<div class="main-header">🤖 Machine Learning Model Benchmarks</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Rigorous chronological out-of-time evaluation preventing temporal look-ahead leakage.</div>', unsafe_allow_html=True)

    st.info("""
    **Evaluation Protocol:**
    - **Train Period:** 2018-01-29 to 2024-12-31 (288,795 rows)
    - **Validation Period:** 2025-01-01 to 2025-12-31 (42,037 rows)
    - **Test Period:** 2026-01-01 to 2026-07-31 (24,299 rows)
    - **Rules:** No random shuffling, strict calendar-aligned lags (lag_1, lag_7, lag_14, lag_28), backward-looking rolling statistics.
    """)

    rows = []
    for model_name, res in metrics_data["models"].items():
        rows.append({
            "Model": model_name.replace("_", " "),
            "Validation MAE": res["validation"]["MAE"],
            "Validation RMSE": res["validation"]["RMSE"],
            "Validation WAPE (%)": res["validation"]["WAPE_pct"],
            "Test MAE (2026)": res["test"]["MAE"],
            "Test RMSE (2026)": res["test"]["RMSE"],
            "Test WAPE (%) (2026)": res["test"]["WAPE_pct"]
        })
    df_eval = pd.DataFrame(rows).sort_values("Test WAPE (%) (2026)")
    st.dataframe(df_eval, use_container_width=True)

    fig_eval = px.bar(
        df_eval,
        x="Model",
        y="Test WAPE (%) (2026)",
        color="Test WAPE (%) (2026)",
        color_continuous_scale="Reds_r",
        title="Test Set WAPE (%) Comparison across Models (Lower is Better)"
    )
    st.plotly_chart(fig_eval, use_container_width=True)

# ========================================================
# 8. DATA PROVENANCE & INTEGRITY
# ========================================================
elif nav_choice == "🛡️ Data Provenance & Integrity":
    st.markdown('<div class="main-header">🛡️ Data Provenance & Cryptographic Audit</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Raw dataset registration, SHA-256 integrity digests, and temporal boundary checks.</div>', unsafe_allow_html=True)

    st.subheader("Raw File SHA-256 Manifest")
    st.json(manifest_data)

    st.subheader("Temporal Boundary Audit")
    st.markdown("""
    | Dataset | Start Date | End Date | Span |
    |---|---|---|---|
    | **CTA Ridership CSV** | `2001-01-01` | `2026-07-31` | 9,343 days (~25.5 years) |
    | **GTFS Service Calendar** | `2026-09-11` | `2026-11-30` | 81 days |

    > **Audit Note:** A 42-day calendar gap separates the ridership export from the GTFS schedule feed. Direct day-by-day joins are structurally infeasible without retroactive look-ahead leakage. GTFS data was incorporated as a contemporary network topology baseline.
    """)

    st.subheader("CTA Developer License Compliance")
    st.markdown("""
    - **Permitted Use:** Academic, planning, and non-commercial transit optimization applications comply with Section I.
    - **Attribution:** *"Data provided by Chicago Transit Authority (CTA)"*.
    - **Brand Usage:** Compliance confirmed; application does not claim official CTA affiliation.
    """)
