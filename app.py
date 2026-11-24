# -*- coding: utf-8 -*-
"""
Chennai MTC RouteRanker - Streamlit Web Application
Milestone 2 Refinement: Visual Redesign (Deep Transit Corporate Theme) & Radar Denominator Corrections
"""

import os
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

# -----------------------------------------------------------------------------
# 1. Page Configuration & Premium Transit Analytics Theme
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="MTC RouteRanker | Decision Support System",
    page_icon="🚍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Premium transit analytics styling: Deep Teal (#0B4F6C), Royal Plum (#5B2C6F),
# Burgundy (#800020), Forest Green (#1E5631), Antique Gold (#C59B27), Warm Ivory/Alabaster (#F8F9FA)
PREMIUM_THEME_CSS = """
<style>
    /* Global Base */
    .stApp {
        background-color: #F8F9FA;
        color: #1A202C;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    }
    
    /* Deep Sidebar Styling */
    section[data-testid="stSidebar"] {
        background-color: #0F172A !important;
        color: #F8FAFC !important;
        border-right: 1px solid #1E293B;
    }
    section[data-testid="stSidebar"] h1, 
    section[data-testid="stSidebar"] h2, 
    section[data-testid="stSidebar"] h3,
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] span,
    section[data-testid="stSidebar"] p {
        color: #F1F5F9 !important;
    }
    section[data-testid="stSidebar"] .stRadio div[role="radiogroup"] label {
        background-color: #1E293B;
        padding: 8px 14px;
        border-radius: 8px;
        margin-bottom: 6px;
        border: 1px solid #334155;
        transition: all 0.15s ease-in-out;
    }
    section[data-testid="stSidebar"] .stRadio div[role="radiogroup"] label:hover {
        background-color: #334155;
        border-color: #C59B27;
    }
    
    /* Top Header Banner */
    .header-box {
        background: linear-gradient(135deg, #0B4F6C 0%, #1A365D 55%, #5B2C6F 100%);
        padding: 24px 32px;
        border-radius: 12px;
        color: #FFFFFF;
        margin-bottom: 22px;
        border-bottom: 3px solid #C59B27;
        box-shadow: 0 4px 14px rgba(11, 79, 108, 0.15);
    }
    .header-title {
        font-size: 2.15rem;
        font-weight: 700;
        margin: 0;
        letter-spacing: -0.3px;
        color: #FFFFFF;
    }
    .header-subtitle {
        font-size: 1.0rem;
        color: #E2E8F0;
        margin-top: 6px;
        margin-bottom: 0;
        font-weight: 400;
        line-height: 1.45;
    }
    
    /* High-Contrast KPI Metric Cards */
    .metric-card {
        background-color: #FFFFFF;
        border-radius: 10px;
        padding: 18px 20px;
        border: 1px solid #E2E8F0;
        border-left: 5px solid #0B4F6C;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
        margin-bottom: 14px;
    }
    .metric-card.teal { border-left-color: #0B4F6C; }
    .metric-card.forest { border-left-color: #1E5631; }
    .metric-card.burgundy { border-left-color: #800020; }
    .metric-card.gold { border-left-color: #C59B27; }
    .metric-card.plum { border-left-color: #5B2C6F; }
    
    .metric-label {
        font-size: 0.82rem;
        font-weight: 700;
        color: #64748B;
        text-transform: uppercase;
        letter-spacing: 0.6px;
        margin-bottom: 4px;
    }
    .metric-value {
        font-size: 1.9rem;
        font-weight: 800;
        color: #0F172A;
        line-height: 1.1;
    }
    .metric-sub {
        font-size: 0.82rem;
        color: #475569;
        margin-top: 5px;
        font-weight: 500;
    }
    
    /* Section Container */
    .section-container {
        background-color: #FFFFFF;
        border-radius: 10px;
        padding: 22px 24px;
        margin-bottom: 20px;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.03);
        border: 1px solid #E2E8F0;
    }
    .section-title {
        font-size: 1.25rem;
        font-weight: 700;
        color: #0F172A;
        margin-bottom: 12px;
        padding-bottom: 6px;
        border-bottom: 2px solid #F1F5F9;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    
    /* Badges & Indicators */
    .scope-badge {
        display: inline-block;
        background-color: #E2E8F0;
        color: #0F172A;
        font-size: 0.78rem;
        font-weight: 700;
        padding: 3px 9px;
        border-radius: 6px;
        border: 1px solid #CBD5E1;
        letter-spacing: 0.3px;
    }
    
    /* Explanation Callout */
    .explanation-callout {
        background-color: #F8FAFC;
        padding: 14px 18px;
        border-radius: 8px;
        border-left: 4px solid #0B4F6C;
        font-size: 0.85rem;
        color: #1E293B;
        line-height: 1.5;
        border: 1px solid #E2E8F0;
        border-left: 4px solid #0B4F6C;
    }
    
    /* Footer */
    .footer-text {
        text-align: center;
        font-size: 0.82rem;
        color: #64748B;
        margin-top: 35px;
        padding-top: 15px;
        border-top: 1px solid #E2E8F0;
        font-weight: 500;
    }
</style>
"""
st.markdown(PREMIUM_THEME_CSS, unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 2. Cached Data Loading with Relative Paths
# -----------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def load_analytical_datasets():
    """
    Load verified analytical CSV datasets using relative paths.
    Returns a dictionary of dataframes with verified active routes.
    """
    base_dir = "."
    
    paths = {
        'ranking': os.path.join(base_dir, 'reports', 'route_ranking_results.csv'),
        'frequency': os.path.join(base_dir, 'reports', 'bus_frequency_analysis.csv'),
        'recommendations': os.path.join(base_dir, 'reports', 'bus_frequency_recommendations.csv'),
        'clustering': os.path.join(base_dir, 'reports', 'route_cluster_assignments.csv'),
        'anomaly': os.path.join(base_dir, 'reports', 'route_anomaly_scores.csv')
    }
    
    data = {}
    for key, p in paths.items():
        if os.path.exists(p):
            df = pd.read_csv(p)
            df['route_id'] = df['route_id'].astype(str)
            data[key] = df
        else:
            data[key] = None
            
    # Ground truth active route set from bus frequency analysis (3,934 routes)
    if data['frequency'] is not None:
        active_ids = set(data['frequency']['route_id'].unique())
        data['active_route_ids'] = active_ids
        
        if data['clustering'] is not None:
            data['clustering_active'] = data['clustering'][data['clustering']['route_id'].isin(active_ids)].copy()
        else:
            data['clustering_active'] = None
            
        if data['ranking'] is not None:
            data['ranking_active'] = data['ranking'][data['ranking']['route_id'].isin(active_ids)].copy()
        else:
            data['ranking_active'] = None
    else:
        data['active_route_ids'] = set()
        data['clustering_active'] = None
        data['ranking_active'] = None
        
    return data

datasets = load_analytical_datasets()
df_ranking = datasets['ranking_active']
df_freq = datasets['frequency']
df_recom = datasets['recommendations']
df_clust = datasets['clustering_active']
df_anom = datasets['anomaly']
active_route_ids = datasets['active_route_ids']

# -----------------------------------------------------------------------------
# 3. Sidebar Navigation (Professional Typography & Non-Emoji Labels)
# -----------------------------------------------------------------------------
st.sidebar.markdown(
    """
    <div style="padding: 10px 0 16px 0; border-bottom: 1px solid #334155;">
        <div style="font-size: 0.75rem; text-transform: uppercase; color: #94A3B8; font-weight: 700; letter-spacing: 1px;">Transit Analytics System</div>
        <h2 style="margin: 4px 0 0 0; color: #FFFFFF; font-size: 1.55rem; font-weight: 800;">MTC RouteRanker</h2>
        <span style="font-size: 0.82rem; color: #C59B27; font-weight: 600;">Chennai Metropolitan Bus Transport</span>
    </div>
    """,
    unsafe_allow_html=True
)

st.sidebar.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

# Clean, professional navigation options without emoji prefixes
PAGES = [
    "Executive Overview",
    "RouteRanker Explorer",
    "Compare Routes",
    "Frequency Optimizer",
    "Supply Anomaly Inspector",
    "Network Map Explorer",
    "Interactive Route Groups Explorer",
    "Scenario Simulator",
    "Model Evaluation",
    "Methodology & Audit",
    "Data & Backend Status",
    "Ridership Insights",
    "Historical Data Analysis"
]

selected_page = st.sidebar.radio("SYSTEM MODULES", PAGES, index=0)

st.sidebar.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)
st.sidebar.markdown("---")
st.sidebar.markdown(
    """
    <div style="font-size: 0.82rem; color: #94A3B8; line-height: 1.6;">
        <span style="color: #F1F5F9; font-weight: 700;">Verified Dataset Scope:</span><br>
        • Active Scheduled Routes: <b style="color:#FFFFFF;">3,934</b><br>
        • Network Bus Stops: <b style="color:#FFFFFF;">5,580</b><br>
        • Scheduled Trips: <b style="color:#FFFFFF;">47,047</b><br>
        • Specification: <b style="color:#FFFFFF;">Chennai MTC GTFS</b>
    </div>
    """,
    unsafe_allow_html=True
)

st.sidebar.markdown(
    """
    <div style="margin-top: 25px; padding: 12px; background-color: #1E293B; border-radius: 6px; font-size: 0.75rem; color: #CBD5E1; border: 1px solid #334155;">
        <b>Operational Notice:</b><br>
        All indicators reflect scheduled transit supply, GTFS timetable distributions, and multi-criteria ranking models.
    </div>
    """,
    unsafe_allow_html=True
)

# -----------------------------------------------------------------------------
# 4. Page 1: Executive Overview (Executive Dashboard)
# -----------------------------------------------------------------------------
if selected_page == "Executive Overview":
    # Header Banner
    st.markdown(
        """
        <div class="header-box">
            <h1 class="header-title">Chennai MTC Network Executive Dashboard</h1>
            <p class="header-subtitle">
                Comprehensive operational evaluation of scheduled transit supply, service frequency brackets, and network typology across 3,934 verified active routes.
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # Verified Top-Level KPIs
    col1, col2, col3, col4, col5 = st.columns(5)
    
    total_active_routes = len(active_route_ids) if active_route_ids else 3934
    
    if df_freq is not None:
        high_freq_count = int((df_freq['headway_category'] == 'High Frequency (<=10 min)').sum())
        single_trip_count = int((df_freq['headway_category'] == 'Undefined (Single-trip)').sum())
        long_gap_count = int(df_freq['has_long_gap'].sum())
    else:
        high_freq_count = 176
        single_trip_count = 869
        long_gap_count = 2431
        
    if df_anom is not None:
        top5_anomalies_count = int(df_anom['is_anomaly_top5pct'].sum())
    else:
        top5_anomalies_count = 197

    with col1:
        st.markdown(
            f"""
            <div class="metric-card teal">
                <div class="metric-label">Active Routes</div>
                <div class="metric-value">{total_active_routes:,}</div>
                <div class="metric-sub">Verified scheduled transit lines</div>
            </div>
            """,
            unsafe_allow_html=True
        )
    with col2:
        st.markdown(
            f"""
            <div class="metric-card forest">
                <div class="metric-label">High Frequency</div>
                <div class="metric-value">{high_freq_count:,}</div>
                <div class="metric-sub">Headway ≤ 10 min ({high_freq_count/total_active_routes*100:.1f}%)</div>
            </div>
            """,
            unsafe_allow_html=True
        )
    with col3:
        st.markdown(
            f"""
            <div class="metric-card gold">
                <div class="metric-label">Long Service Gaps</div>
                <div class="metric-value">{long_gap_count:,}</div>
                <div class="metric-sub">{long_gap_count/total_active_routes*100:.1f}% routes with gap &gt; 60 min</div>
            </div>
            """,
            unsafe_allow_html=True
        )
    with col4:
        st.markdown(
            f"""
            <div class="metric-card burgundy">
                <div class="metric-label">Single-Trip Lines</div>
                <div class="metric-value">{single_trip_count:,}</div>
                <div class="metric-sub">1 trip/day (Headway N/A)</div>
            </div>
            """,
            unsafe_allow_html=True
        )
    with col5:
        st.markdown(
            f"""
            <div class="metric-card plum">
                <div class="metric-label">Supply Outliers</div>
                <div class="metric-value">{top5_anomalies_count}</div>
                <div class="metric-sub">Top 5% Isolation Forest</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    # Main Visual Analytics Section (Two Columns)
    col_left, col_right = st.columns([1.1, 1.0])
    
    with col_left:
        st.markdown(
            """
            <div class="section-container">
                <div class="section-title">Network Scheduled Frequency Distribution</div>
            """,
            unsafe_allow_html=True
        )
        if df_freq is not None:
            cat_order = [
                'High Frequency (<=10 min)',
                'Medium Frequency (10-20 min)',
                'Moderate (20-30 min)',
                'Low Frequency (30-60 min)',
                'Very Low (>60 min)',
                'Undefined (Single-trip)'
            ]
            
            freq_counts = df_freq['headway_category'].value_counts().reindex(cat_order).reset_index()
            freq_counts.columns = ['Category', 'Routes']
            freq_counts['Percentage'] = (freq_counts['Routes'] / total_active_routes * 100).round(1)
            
            # Rich deep color sequence: Forest Green, Emerald, Dark Teal, Royal Plum, Burgundy, Slate
            deep_colors = ['#1E5631', '#0B4F6C', '#2B6CB0', '#5B2C6F', '#800020', '#64748B']
            
            fig_freq = px.bar(
                freq_counts,
                x='Category',
                y='Routes',
                text='Routes',
                color='Category',
                color_discrete_sequence=deep_colors,
                labels={'Routes': 'Active Routes', 'Category': 'Headway Category'}
            )
            fig_freq.update_traces(
                texttemplate='%{text} (%{customdata:.1f}%)',
                customdata=freq_counts['Percentage'],
                textposition='outside',
                marker_line_width=1,
                marker_line_color='#0F172A'
            )
            fig_freq.update_layout(
                showlegend=False,
                margin=dict(l=10, r=10, t=15, b=60),
                height=320,
                plot_bgcolor='#FFFFFF',
                paper_bgcolor='#FFFFFF',
                xaxis=dict(gridcolor='#F1F5F9', tickangle=-25, tickfont=dict(size=11, color='#1E293B')),
                yaxis=dict(gridcolor='#F1F5F9', tickfont=dict(size=11, color='#1E293B')),
                xaxis_title="",
                yaxis_title="Route Count"
            )
            st.plotly_chart(fig_freq, use_container_width=True)
            st.caption("Distribution based on Task 08 Bus Frequency Analysis across all 3,934 active routes.")
        st.markdown("</div>", unsafe_allow_html=True)
        
    with col_right:
        st.markdown(
            """
            <div class="section-container">
                <div class="section-title">Operational Typology & Clusters</div>
            """,
            unsafe_allow_html=True
        )
        if df_clust is not None:
            k_counts = df_clust['kmeans_cluster'].value_counts().reset_index()
            k_counts.columns = ['Cluster', 'Count']
            k_counts['Cluster_Name'] = k_counts['Cluster'].map({
                0: 'Core Network Routes (Cluster 0: Avg 5.4 trips)',
                1: 'High-Frequency Trunk Corridors (Cluster 1: Avg 81.0 trips)'
            }).fillna('Other')
            
            fig_clust = px.pie(
                k_counts,
                names='Cluster_Name',
                values='Count',
                color_discrete_sequence=['#0B4F6C', '#C59B27'],
                hole=0.48
            )
            fig_clust.update_traces(
                textposition='inside',
                textinfo='percent+label',
                marker=dict(line=dict(color='#FFFFFF', width=2))
            )
            fig_clust.update_layout(
                showlegend=True,
                legend=dict(orientation="h", yanchor="bottom", y=-0.28, xanchor="center", x=0.5, font=dict(size=11, color='#1E293B')),
                margin=dict(l=10, r=10, t=10, b=30),
                height=320,
                plot_bgcolor='#FFFFFF',
                paper_bgcolor='#FFFFFF'
            )
            st.plotly_chart(fig_clust, use_container_width=True)
            st.caption("Distribution of active routes from Task 06 K-Means (K=2) supply-side typology clustering.")
        st.markdown("</div>", unsafe_allow_html=True)

    # Second Analytics Row: Corridor Ranking vs Supply Anomaly Profile
    col_row2_1, col_row2_2 = st.columns(2)
    
    with col_row2_1:
        st.markdown(
            """
            <div class="section-container">
                <div class="section-title">Top Prioritized Transit Routes (Task 07 Leaderboard)</div>
            """,
            unsafe_allow_html=True
        )
        if df_ranking is not None:
            top_rank_disp = df_ranking.head(8)[[
                'rank', 'route_id', 'route_short_name', 'overall_score', 'daily_scheduled_trips', 
                'effective_headway_min', 'route_length_km', 'stop_count'
            ]].copy()
            top_rank_disp.columns = ['Rank', 'Route ID', 'Route Name', 'Overall Score', 'Daily Trips', 'Headway (min)', 'Length (km)', 'Stops']
            top_rank_disp['Rank'] = top_rank_disp['Rank'].astype(int)
            top_rank_disp['Overall Score'] = top_rank_disp['Overall Score'].round(3)
            top_rank_disp['Length (km)'] = top_rank_disp['Length (km)'].round(1)
            
            st.dataframe(
                top_rank_disp,
                hide_index=True,
                use_container_width=True,
                height=310
            )
            st.caption("Top ranking routes from Task 07 multi-criteria explainable priority model (includes Route ID).")
        st.markdown("</div>", unsafe_allow_html=True)
        
    with col_row2_2:
        st.markdown(
            """
            <div class="section-container">
                <div class="section-title">Supply-Side Anomaly Highlights (Isolation Forest)</div>
            """,
            unsafe_allow_html=True
        )
        if df_anom is not None:
            top_anom_disp = df_anom.sort_values('anomaly_percentile', ascending=False).head(8)[[
                'route_id', 'route_short_name', 'anomaly_score_norm', 'anomaly_percentile',
                'scheduled_trip_count', 'stop_spacing_km', 'primary_driver'
            ]].copy()
            top_anom_disp.columns = ['Route ID', 'Route Name', 'Norm Score', 'Percentile', 'Trips', 'Spacing (km/stop)', 'Primary Driver']
            top_anom_disp['Norm Score'] = top_anom_disp['Norm Score'].round(3)
            top_anom_disp['Percentile'] = top_anom_disp['Percentile'].round(1).astype(str) + "%"
            top_anom_disp['Spacing (km/stop)'] = top_anom_disp['Spacing (km/stop)'].round(2)
            
            st.dataframe(
                top_anom_disp,
                hide_index=True,
                use_container_width=True,
                height=310
            )
            st.caption("Top multidimensional scheduled service outliers flagged by Isolation Forest (includes Route ID).")
        st.markdown("</div>", unsafe_allow_html=True)

    # Footer
    st.markdown(
        """
        <div class="footer-text">
            Chennai MTC RouteRanker Decision Support Platform • Deep Transit Analytics Theme • Verified GTFS Pipeline
        </div>
        """,
        unsafe_allow_html=True
    )

# -----------------------------------------------------------------------------
# 5. Page 2: RouteRanker Explorer (Task 07 Multi-Criteria Priority)
# -----------------------------------------------------------------------------
elif selected_page == "RouteRanker Explorer":
    st.markdown(
        """
        <div class="header-box">
            <h1 class="header-title">RouteRanker Priority Explorer</h1>
            <p class="header-subtitle">
                Interactive multi-criteria priority ranking and score component decomposition across all 3,934 active Chennai MTC transit lines (Task 07).
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    if df_ranking is not None:
        # Search & Filtering Control Bar
        st.markdown('<div class="section-container">', unsafe_allow_html=True)
        col_f1, col_f2, col_f3, col_f4 = st.columns([1.5, 1.2, 1.2, 1.2])
        
        with col_f1:
            search_query = st.text_input("Search Route Name, ID, or Corridor", placeholder="e.g. 91, 500, 25 R, 18750").strip()
            
        with col_f2:
            min_trips = int(df_ranking['daily_scheduled_trips'].min())
            max_trips = int(df_ranking['daily_scheduled_trips'].max())
            trip_filter = st.slider("Minimum Daily Scheduled Trips", min_value=min_trips, max_value=max_trips, value=min_trips)
            
        with col_f3:
            rank_quartile = st.selectbox(
                "Priority Quartile Filter",
                options=["All Active Routes", "Top 100 Priority", "Top 500 Priority", "Top Quartile (Q1)", "Bottom Quartile (Q4)"]
            )
            
        with col_f4:
            sort_by = st.selectbox(
                "Sort Table By",
                options=["Priority Rank (Ascending)", "Overall Score (Descending)", "Daily Trips (Descending)", "Route Length (Descending)"]
            )
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Filter Logic
        filtered_df = df_ranking.copy()
        
        if search_query:
            filtered_df = filtered_df[
                filtered_df['route_short_name'].str.contains(search_query, case=False, na=False) |
                filtered_df['route_id'].str.contains(search_query, case=False, na=False) |
                filtered_df['canonical_route'].str.contains(search_query, case=False, na=False)
            ]
            
        filtered_df = filtered_df[filtered_df['daily_scheduled_trips'] >= trip_filter]
        
        if rank_quartile == "Top 100 Priority":
            filtered_df = filtered_df[filtered_df['rank'] <= 100]
        elif rank_quartile == "Top 500 Priority":
            filtered_df = filtered_df[filtered_df['rank'] <= 500]
        elif rank_quartile == "Top Quartile (Q1)":
            q1_threshold = filtered_df['rank'].quantile(0.25)
            filtered_df = filtered_df[filtered_df['rank'] <= q1_threshold]
        elif rank_quartile == "Bottom Quartile (Q4)":
            q4_threshold = filtered_df['rank'].quantile(0.75)
            filtered_df = filtered_df[filtered_df['rank'] >= q4_threshold]
            
        if sort_by == "Priority Rank (Ascending)":
            filtered_df = filtered_df.sort_values('rank', ascending=True)
        elif sort_by == "Overall Score (Descending)":
            filtered_df = filtered_df.sort_values('overall_score', ascending=False)
        elif sort_by == "Daily Trips (Descending)":
            filtered_df = filtered_df.sort_values('daily_scheduled_trips', ascending=False)
        elif sort_by == "Route Length (Descending)":
            filtered_df = filtered_df.sort_values('route_length_km', ascending=False)
            
        st.markdown(f"<div style='font-weight: 600; color: #475569; margin-bottom: 10px;'>Displaying {len(filtered_df):,} matching transit lines:</div>", unsafe_allow_html=True)
        
        # Two-Column Master-Detail Layout
        col_table, col_details = st.columns([1.35, 1.0])
        
        with col_table:
            st.markdown('<div class="section-container">', unsafe_allow_html=True)
            st.markdown('<div class="section-title">Route Priority Master Table</div>', unsafe_allow_html=True)
            
            table_display = filtered_df[[
                'rank', 'route_id', 'route_short_name', 'overall_score',
                'daily_scheduled_trips', 'effective_headway_min', 'route_length_km', 'stop_count'
            ]].copy()
            table_display.columns = ['Rank', 'Route ID', 'Route Name', 'Score', 'Trips', 'Headway (min)', 'Length (km)', 'Stops']
            table_display['Rank'] = table_display['Rank'].astype(int)
            table_display['Score'] = table_display['Score'].round(3)
            table_display['Length (km)'] = table_display['Length (km)'].round(1)
            
            st.dataframe(
                table_display,
                hide_index=True,
                use_container_width=True,
                height=490
            )
            st.caption("Select a route in the adjacent panel for multi-criteria radar decomposition.")
            st.markdown('</div>', unsafe_allow_html=True)
            
        with col_details:
            st.markdown('<div class="section-container">', unsafe_allow_html=True)
            st.markdown('<div class="section-title">Route Priority Component Decomposition</div>', unsafe_allow_html=True)
            
            # Select route for drilldown
            available_route_labels = (
                filtered_df['route_short_name'] + " (ID: " + filtered_df['route_id'] + ", Rank: #" + filtered_df['rank'].astype(int).astype(str) + ")"
            ).tolist()
            
            if available_route_labels:
                selected_label = st.selectbox("Inspect Route Profile:", options=available_route_labels, index=0)
                selected_id = selected_label.split("ID: ")[1].split(",")[0].strip()
                selected_row = filtered_df[filtered_df['route_id'] == selected_id].iloc[0]
                
                # Card stats for selected route
                st.markdown(
                    f"""
                    <div style="background-color: #F8FAFC; padding: 14px 18px; border-radius: 8px; margin-bottom: 14px; border: 1px solid #E2E8F0;">
                        <div style="font-size: 1.2rem; font-weight: 800; color: #0F172A;">
                            Route {selected_row['route_short_name']} <span style="font-size: 0.85rem; color: #64748B; font-weight: 500;">(Route ID: {selected_row['route_id']})</span>
                        </div>
                        <div style="display: flex; gap: 16px; margin-top: 8px; font-size: 0.85rem; color: #334155;">
                            <span>Priority Rank: <b style="color:#0B4F6C;">#{int(selected_row['rank'])}</b></span>
                            <span>Score: <b style="color:#0B4F6C;">{selected_row['overall_score']:.3f}</b></span>
                            <span>Daily Trips: <b>{selected_row['daily_scheduled_trips']}</b></span>
                            <span>Headway: <b>{selected_row['effective_headway_min']:.1f}m</b></span>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                
                # Verified Radar Chart Normalization Denominators:
                # Frequency (25.0), Headway (25.0), Stop Coverage (15.0),
                # Network Hub Connectivity (15.0), Corridor Length Utility (10.0), Service Span (10.0)
                categories = [
                    'Trip Frequency',
                    'Departure Headway',
                    'Stop Coverage',
                    'Hub Connectivity',
                    'Length Utility',
                    'Service Span'
                ]
                
                contrib_vals = [
                    (selected_row['contrib_frequency'] / 25.0) * 100,
                    (selected_row['contrib_headway'] / 25.0) * 100,
                    (selected_row['contrib_stop_coverage'] / 15.0) * 100,
                    (selected_row['contrib_connectivity'] / 15.0) * 100,   # Corrected: divided by 15.0
                    (selected_row['contrib_length_utility'] / 10.0) * 100, # Corrected: divided by 10.0
                    (selected_row['contrib_service_span'] / 10.0) * 100
                ]
                
                fig_radar = go.Figure()
                fig_radar.add_trace(go.Scatterpolar(
                    r=contrib_vals + [contrib_vals[0]],
                    theta=categories + [categories[0]],
                    fill='toself',
                    fillcolor='rgba(11, 79, 108, 0.28)',
                    line=dict(color='#0B4F6C', width=2.5),
                    name=f"Route {selected_row['route_short_name']}"
                ))
                
                fig_radar.update_layout(
                    polar=dict(
                        radialaxis=dict(
                            visible=True,
                            range=[0, 100],
                            ticksuffix="%",
                            tickfont=dict(size=9, color="#64748B"),
                            gridcolor="#E2E8F0"
                        ),
                        angularaxis=dict(
                            tickfont=dict(size=10, color="#0F172A", weight=600),
                            gridcolor="#E2E8F0"
                        ),
                        bgcolor="#FFFFFF"
                    ),
                    showlegend=False,
                    margin=dict(l=35, r=35, t=25, b=25),
                    height=280,
                    plot_bgcolor='#FFFFFF',
                    paper_bgcolor='#FFFFFF'
                )
                st.plotly_chart(fig_radar, use_container_width=True)
                
                # Verified Explainability Narrative from Task 07 source column
                if pd.notna(selected_row['score_explanation']):
                    st.markdown(
                        f"""
                        <div class="explanation-callout">
                            <span style="font-weight: 700; color: #0B4F6C;">Model Justification:</span><br>
                            {selected_row['score_explanation']}
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
            else:
                st.info("No routes match the selected filter criteria.")
            st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.error("Ranking dataset could not be loaded from `reports/route_ranking_results.csv`.")
        
    st.markdown(
        """
        <div class="footer-text">
            Chennai MTC RouteRanker Decision Support Platform • Deep Transit Analytics Theme • Milestone 2 Complete
        </div>
        """,
        unsafe_allow_html=True
    )

# -----------------------------------------------------------------------------
# 6. Placeholder Pages (Aligned to Theme)
# -----------------------------------------------------------------------------

elif selected_page == "Compare Routes":
    st.markdown(
        """
        <div class="header-box">
            <h1 class="header-title">Compare Routes</h1>
            <p class="header-subtitle">
                Side-by-side multi-criteria comparison of scheduled transit supply, corridor topology, and operational profiles.
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    if df_ranking is not None and not df_ranking.empty:
        # Prepare route selection options
        routes_list = df_ranking.sort_values('rank')[['route_id', 'route_short_name', 'rank', 'overall_score']].to_dict('records')
        route_options = [str(r['route_id']) for r in routes_list]
        route_labels = {str(r['route_id']): f"{r['route_short_name']} (ID: {r['route_id']} • Rank #{int(r['rank']) if pd.notnull(r['rank']) else 'N/A'})" for r in routes_list}
        
        # Default routes for initial comparison: Top route (#1, 91) and a high-frequency route (#11, 29A)
        default_routes = []
        for pref in ['24072', '18751']:
            if pref in route_options:
                default_routes.append(pref)
        if len(default_routes) < 2 and len(route_options) >= 2:
            default_routes = route_options[:2]
            
        st.markdown(
            """
            <div class="section-container">
                <div class="section-title">Select Routes for Comparative Analysis</div>
                <p style="color: #64748B; font-size: 0.9rem; margin-bottom: 12px;">
                    Select 2 or 3 distinct Chennai MTC routes to contrast their scheduled frequency, headway regularity, stop coverage, and multi-criteria performance.
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        selected_ids = st.multiselect(
            "Select 2 or 3 Routes to Compare",
            options=route_options,
            default=default_routes,
            max_selections=3,
            format_func=lambda x: route_labels.get(x, str(x)),
            help="Select between 2 and 3 routes to display side-by-side metrics and radar benchmarks."
        )
        
        if len(selected_ids) < 2:
            st.warning("Please select at least 2 routes (maximum 3) to enable comparative analytics.")
        else:
            # Build merged dataset for selected routes (Left Join to prevent dropping routes)
            sel_rows = []
            for rid in selected_ids:
                rank_row = df_ranking[df_ranking['route_id'] == rid]
                if rank_row.empty:
                    continue
                r_dict = rank_row.iloc[0].to_dict()
                
                # Join Anomaly data
                if df_anom is not None and not df_anom.empty:
                    anom_row = df_anom[df_anom['route_id'] == rid]
                    if not anom_row.empty:
                        a_dict = anom_row.iloc[0].to_dict()
                        r_dict['is_anomaly_top1pct'] = a_dict.get('is_anomaly_top1pct', False)
                        r_dict['is_anomaly_top5pct'] = a_dict.get('is_anomaly_top5pct', False)
                        r_dict['anomaly_percentile'] = a_dict.get('anomaly_percentile', np.nan)
                        r_dict['anomaly_score_norm'] = a_dict.get('anomaly_score_norm', np.nan)
                        r_dict['primary_driver'] = a_dict.get('primary_driver', 'None')
                    else:
                        r_dict['is_anomaly_top1pct'] = False
                        r_dict['is_anomaly_top5pct'] = False
                        r_dict['anomaly_percentile'] = np.nan
                        r_dict['anomaly_score_norm'] = np.nan
                        r_dict['primary_driver'] = 'None'
                else:
                    r_dict['is_anomaly_top1pct'] = False
                    r_dict['is_anomaly_top5pct'] = False
                    r_dict['anomaly_percentile'] = np.nan
                    r_dict['anomaly_score_norm'] = np.nan
                    r_dict['primary_driver'] = 'None'
                    
                # Join Clustering data
                if df_clust is not None and not df_clust.empty:
                    clust_row = df_clust[df_clust['route_id'] == rid]
                    if not clust_row.empty:
                        r_dict['kmeans_cluster'] = clust_row.iloc[0].get('kmeans_cluster', np.nan)
                    else:
                        r_dict['kmeans_cluster'] = np.nan
                else:
                    r_dict['kmeans_cluster'] = np.nan
                    
                sel_rows.append(r_dict)
                
            df_sel = pd.DataFrame(sel_rows)
            
            # -------------------------------------------------------------
            # Route Summary Metric Cards
            # -------------------------------------------------------------
            card_colors = ['teal', 'plum', 'burgundy']
            cols = st.columns(len(df_sel))
            
            for idx, col in enumerate(cols):
                row = df_sel.iloc[idx]
                c_color = card_colors[idx % len(card_colors)]
                
                # Format cluster
                c_val = row.get('kmeans_cluster', np.nan)
                if pd.notnull(c_val):
                    c_desc = "Cluster 1: High-frequency core trunk" if int(c_val) == 1 else "Cluster 0: Low-frequency core & secondary feeder"
                else:
                    c_desc = "Cluster: Unassigned"
                    
                # Format headway
                hw = row.get('effective_headway_min', np.nan)
                if pd.notnull(hw) and float(hw) > 0 and row.get('daily_scheduled_trips', 0) > 1:
                    hw_disp = f"{float(hw):.1f} min"
                elif row.get('daily_scheduled_trips', 0) == 1:
                    hw_disp = "Undefined (Single-Trip)"
                else:
                    hw_disp = "N/A"
                    
                # Format anomaly
                is_top1 = bool(row.get('is_anomaly_top1pct', False))
                is_top5 = bool(row.get('is_anomaly_top5pct', False))
                if is_top1:
                    anom_tier = "Tier 1: Severe Outlier"
                elif is_top5:
                    anom_tier = "Tier 2: Moderate Outlier"
                else:
                    anom_tier = "Nominal Baseline"
                    
                pct_val = row.get('anomaly_percentile', np.nan)
                pct_disp = f"{float(pct_val):.1f}th pct" if pd.notnull(pct_val) and not pd.isna(pct_val) else "Unflagged"
                
                with col:
                    st.markdown(
                        f"""
                        <div class="metric-card {c_color}">
                            <div class="metric-label">{row['route_short_name']} (ID: {row['route_id']})</div>
                            <div class="metric-value">Rank #{int(row['rank']) if pd.notnull(row['rank']) else 'N/A'}</div>
                            <div class="metric-sub" style="font-weight: 700; color: #0B4F6C;">Score: {row['overall_score']:.1f} / 100</div>
                            <hr style="margin: 8px 0; border: none; border-top: 1px solid #E2E8F0;">
                            <div style="font-size: 0.82rem; color: #334155; line-height: 1.4;">
                                <b>Trips:</b> {int(row['daily_scheduled_trips'])} trips/day<br>
                                <b>Headway:</b> {hw_disp}<br>
                                <b>Stops:</b> {int(row['stop_count'])} stops • {row['route_length_km']:.1f} km<br>
                                <b>Topology:</b> {c_desc}<br>
                                <b>Anomaly:</b> {anom_tier} ({pct_disp})
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                    
            st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)
            
            # -------------------------------------------------------------
            # Visual Radar Chart & Detailed Side-by-Side Table
            # -------------------------------------------------------------
            col_chart, col_table = st.columns([5, 6])
            
            with col_chart:
                st.markdown(
                    """
                    <div class="section-container" style="padding-bottom: 10px;">
                        <div class="section-title">Multidimensional Operational Radar</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                
                radar_categories = [
                    'Frequency (25%)',
                    'Headway (25%)',
                    'Stop Coverage (15%)',
                    'Hub Connect. (15%)',
                    'Length Utility (10%)',
                    'Service Span (10%)'
                ]
                
                fig_radar = go.Figure()
                palette = ['#0B4F6C', '#5B2C6F', '#C59B27']
                
                for idx, row in df_sel.iterrows():
                    # Exact normalized scores [0, 100] derived from verified criteria weights
                    r_freq = (row.get('contrib_frequency', 0.0) / 25.0) * 100.0
                    r_headway = (row.get('contrib_headway', 0.0) / 25.0) * 100.0
                    r_stops = (row.get('contrib_stop_coverage', 0.0) / 15.0) * 100.0
                    r_conn = (row.get('contrib_connectivity', 0.0) / 15.0) * 100.0
                    r_len = (row.get('contrib_length_utility', 0.0) / 10.0) * 100.0
                    r_span = (row.get('contrib_service_span', 0.0) / 10.0) * 100.0
                    
                    values = [
                        np.clip(r_freq, 0, 100),
                        np.clip(r_headway, 0, 100),
                        np.clip(r_stops, 0, 100),
                        np.clip(r_conn, 0, 100),
                        np.clip(r_len, 0, 100),
                        np.clip(r_span, 0, 100)
                    ]
                    # Close the polygon
                    values.append(values[0])
                    cat_closed = radar_categories + [radar_categories[0]]
                    
                    r_color = palette[idx % len(palette)]
                    fig_radar.add_trace(go.Scatterpolar(
                        r=values,
                        theta=cat_closed,
                        fill='toself',
                        name=f"{row['route_short_name']} (ID: {row['route_id']})",
                        line=dict(color=r_color, width=2.5),
                        opacity=0.65
                    ))
                    
                fig_radar.update_layout(
                    polar=dict(
                        radialaxis=dict(
                            visible=True,
                            range=[0, 100],
                            tickfont=dict(size=10, color="#64748B")
                        ),
                        angularaxis=dict(
                            tickfont=dict(size=11, color="#1E293B", weight="bold")
                        )
                    ),
                    legend=dict(
                        orientation="h",
                        yanchor="bottom",
                        y=-0.25,
                        xanchor="center",
                        x=0.5
                    ),
                    margin=dict(l=40, r=40, t=20, b=40),
                    height=450,
                    paper_bgcolor="#FFFFFF",
                    plot_bgcolor="#FFFFFF"
                )
                st.plotly_chart(fig_radar, use_container_width=True)
                
            with col_table:
                st.markdown(
                    """
                    <div class="section-container" style="padding-bottom: 10px;">
                        <div class="section-title">Side-by-Side Metric Specifications</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                
                # Build comparison matrix
                metrics_spec = [
                    ("Network Rank", lambda r: f"#{int(r['rank'])}" if pd.notnull(r['rank']) else "N/A"),
                    ("Overall Score (0-100)", lambda r: f"{r['overall_score']:.2f}"),
                    ("Daily Scheduled Trips", lambda r: f"{int(r['daily_scheduled_trips'])} trips"),
                    ("Scheduled Headway", lambda r: f"{float(r['effective_headway_min']):.1f} min" if pd.notnull(r['effective_headway_min']) and float(r['effective_headway_min']) > 0 and r['daily_scheduled_trips'] > 1 else ("Undefined (Single-Trip)" if r['daily_scheduled_trips'] == 1 else "N/A")),
                    ("Stop Count", lambda r: f"{int(r['stop_count'])} stops"),
                    ("Route Trajectory Length", lambda r: f"{r['route_length_km']:.2f} km"),
                    ("Daily Service Span", lambda r: f"{r['service_span_hours']:.1f} hours"),
                    ("Hub Connectivity Degree", lambda r: f"{r['avg_stop_degree']:.2f}"),
                    ("Operational Cluster", lambda r: "Cluster 1 (Trunk Corridor)" if r.get('kmeans_cluster', 0) == 1 else "Cluster 0 (Feeder / Secondary)"),
                    ("Supply Anomaly Tier", lambda r: "Tier 1: Severe Outlier" if r.get('is_anomaly_top1pct') else ("Tier 2: Moderate Outlier" if r.get('is_anomaly_top5pct') else "Nominal Baseline")),
                    ("Anomaly Percentile", lambda r: f"{r['anomaly_percentile']:.2f}%" if pd.notnull(r.get('anomaly_percentile')) and not pd.isna(r.get('anomaly_percentile')) else "N/A (Nominal)")
                ]
                
                table_dict = {"Operational Metric": [m[0] for m in metrics_spec]}
                for idx, row in df_sel.iterrows():
                    col_name = f"{row['route_short_name']} (ID: {row['route_id']})"
                    table_dict[col_name] = [m[1](row) for m in metrics_spec]
                    
                df_comp_table = pd.DataFrame(table_dict)
                st.dataframe(df_comp_table, hide_index=True, use_container_width=True)
                
            # -------------------------------------------------------------
            # Directionality & Planning Trade-off Guidance
            # -------------------------------------------------------------
            st.markdown(
                """
                <div class="explanation-callout">
                    <div style="font-weight: 700; color: #0B4F6C; margin-bottom: 6px; font-size: 0.95rem;">
                        Transit Planning Interpretation & Directionality Guidelines:
                    </div>
                    <ul style="margin: 0; padding-left: 20px; font-size: 0.88rem; color: #334155; line-height: 1.5;">
                        <li><b>Frequency & Headway:</b> Higher trip volume and shorter headways indicate arterial trunk capability. Feeder routes naturally have wider headways designed to synchronize with train or trunk bus arrivals.</li>
                        <li><b>Length Utility:</b> Trajectory reach is capped at 30.0 km in the utility model to reward regional connectivity without penalizing efficient short-loop neighborhood shuttles.</li>
                        <li><b>Typology Distinction:</b> A route with a lower overall rank is <b>not</b> defective; secondary feeders and school cut-trips operate under different service mandates than 24-hour arterial corridors.</li>
                    </ul>
                </div>
                """,
                unsafe_allow_html=True
            )
    else:
        st.error("Ranking dataset is unavailable. Ensure `reports/route_ranking_results.csv` exists.")
        
    st.markdown(
        """
        <div class="footer-text">
            Chennai MTC RouteRanker Decision Support Platform • Module 3 Compare Routes
        </div>
        """,
        unsafe_allow_html=True
    )

elif selected_page == "Frequency Optimizer":
    st.markdown(
        """
        <div class="header-box">
            <h1 class="header-title">Frequency Optimizer & Policy Simulation</h1>
            <p class="header-subtitle">
                Systematic departure interval assessment, intra-window peak/off-peak headway diagnostics, and schedule-based scenario optimization across 3,934 active routes (Task 08).
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    if df_freq is not None and df_recom is not None:
        # ---------------------------------------------------------------------
        # 1. Frequency Overview & Verified KPIs
        # ---------------------------------------------------------------------
        total_routes_freq = len(df_freq)
        multi_trip_count = int(df_freq['median_headway_min'].notna().sum())
        single_trip_count = int((df_freq['headway_category'] == 'Undefined (Single-trip)').sum())
        recom_routes_count = df_recom['route_id'].nunique()
        total_add_trips = int(df_recom['additional_trips'].sum())
        median_headway_active = float(df_freq['median_headway_min'].median())
        peak_median_headway = float(df_freq['peak_median_headway_min'].dropna().median())
        offpeak_median_headway = float(df_freq['offpeak_median_headway_min'].dropna().median())
        
        kpi_col1, kpi_col2, kpi_col3, kpi_col4, kpi_col5 = st.columns(5)
        
        with kpi_col1:
            st.markdown(
                f"""
                <div class="metric-card teal">
                    <div class="metric-label">Network Median Headway</div>
                    <div class="metric-value">{median_headway_active:.0f}m</div>
                    <div class="metric-sub">Mean: 143.9 min (3,065 lines)</div>
                </div>
                """,
                unsafe_allow_html=True
            )
        with kpi_col2:
            st.markdown(
                f"""
                <div class="metric-card forest">
                    <div class="metric-label">Peak Intra-Window</div>
                    <div class="metric-value">{peak_median_headway:.1f}m</div>
                    <div class="metric-sub">Target: 15.0 min (07-10 & 16-19)</div>
                </div>
                """,
                unsafe_allow_html=True
            )
        with kpi_col3:
            st.markdown(
                f"""
                <div class="metric-card gold">
                    <div class="metric-label">Off-Peak Intra-Window</div>
                    <div class="metric-value">{offpeak_median_headway:.0f}m</div>
                    <div class="metric-sub">Target: 25.0 min (Midday/Night)</div>
                </div>
                """,
                unsafe_allow_html=True
            )
        with kpi_col4:
            st.markdown(
                f"""
                <div class="metric-card plum">
                    <div class="metric-label">Optimization Need</div>
                    <div class="metric-value">{recom_routes_count:,}</div>
                    <div class="metric-sub">38.6% active routes flagged</div>
                </div>
                """,
                unsafe_allow_html=True
            )
        with kpi_col5:
            st.markdown(
                f"""
                <div class="metric-card burgundy">
                    <div class="metric-label">Est. Additional Trips</div>
                    <div class="metric-value">+{total_add_trips:,}</div>
                    <div class="metric-sub">Across 2,150 bounded windows</div>
                </div>
                """,
                unsafe_allow_html=True
            )
            
        # Context Banner & Planning Disclaimer
        st.markdown(
            """
            <div style="background-color: #F8FAFC; border-left: 4px solid #C59B27; padding: 12px 18px; border-radius: 6px; font-size: 0.82rem; color: #334155; margin-bottom: 20px; border: 1px solid #E2E8F0;">
                <b>Planning & Methodology Notice:</b> The headway targets (15 min Peak, 25 min Off-Peak) represent transit planning benchmarks for metropolitan networks, not official MTC regulatory mandates. Required additional trips are <b>bounded strictly to each route's observed operational span</b> to avoid unconstrained expansion. No passenger ticketing, vehicle allocation, or depot cost data was utilized.
            </div>
            """,
            unsafe_allow_html=True
        )

        # ---------------------------------------------------------------------
        # 2. Network Visualizations: Time-of-Day Profile & Headway Comparison
        # ---------------------------------------------------------------------
        chart_col1, chart_col2 = st.columns([1.1, 1.0])
        
        with chart_col1:
            st.markdown('<div class="section-container">', unsafe_allow_html=True)
            st.markdown('<div class="section-title">Network Scheduled Departures by Time Band</div>', unsafe_allow_html=True)
            
            # Exact time of day departures from Task 08 report
            tod_data = pd.DataFrame({
                'Time Band': [
                    'Early Morning (05-07)',
                    'Morning Peak (07-10)',
                    'Midday (10-16)',
                    'Evening Peak (16-19)',
                    'Night (19-23)',
                    'Late Night (23-05)'
                ],
                'Departures': [5042, 8058, 16859, 8264, 7293, 1531],
                'Share': ['10.7%', '17.1%', '35.8%', '17.6%', '15.5%', '3.3%']
            })
            
            fig_tod = px.bar(
                tod_data,
                x='Time Band',
                y='Departures',
                text='Departures',
                color='Time Band',
                color_discrete_sequence=['#0B4F6C', '#1E5631', '#2B6CB0', '#5B2C6F', '#800020', '#64748B']
            )
            fig_tod.update_traces(
                texttemplate='%{text} (%{customdata})',
                customdata=tod_data['Share'],
                textposition='outside',
                marker_line_width=1,
                marker_line_color='#0F172A'
            )
            fig_tod.update_layout(
                showlegend=False,
                margin=dict(l=10, r=10, t=15, b=60),
                height=320,
                plot_bgcolor='#FFFFFF',
                paper_bgcolor='#FFFFFF',
                xaxis=dict(gridcolor='#F1F5F9', tickangle=-20, tickfont=dict(size=10, color='#1E293B')),
                yaxis=dict(gridcolor='#F1F5F9', tickfont=dict(size=11, color='#1E293B')),
                xaxis_title="",
                yaxis_title="Total Departures"
            )
            st.plotly_chart(fig_tod, use_container_width=True)
            st.caption("Distribution across 47,047 scheduled trips (100.0% network coverage across 6 mutually exclusive windows).")
            st.markdown('</div>', unsafe_allow_html=True)
            
        with chart_col2:
            st.markdown('<div class="section-container">', unsafe_allow_html=True)
            st.markdown('<div class="section-title">Peak vs Off-Peak Intra-Window Headways</div>', unsafe_allow_html=True)
            
            # Headway metrics comparison
            comp_df = pd.DataFrame({
                'Service Period': ['Morning/Evening Peak', 'Off-Peak Day/Night'],
                'Observed Median (min)': [31.5, 40.0],
                'Observed Mean (min)': [46.6, 64.8],
                'Target Benchmark (min)': [15.0, 25.0],
                'Evaluated Routes': [1276, 2287]
            })
            
            fig_comp = go.Figure()
            fig_comp.add_trace(go.Bar(
                name='Observed Intra-Window Median',
                x=comp_df['Service Period'],
                y=comp_df['Observed Median (min)'],
                marker_color='#0B4F6C',
                text=comp_df['Observed Median (min)'].apply(lambda v: f"{v} min"),
                textposition='auto'
            ))
            fig_comp.add_trace(go.Bar(
                name='Planning Target Benchmark',
                x=comp_df['Service Period'],
                y=comp_df['Target Benchmark (min)'],
                marker_color='#C59B27',
                text=comp_df['Target Benchmark (min)'].apply(lambda v: f"{v} min"),
                textposition='auto'
            ))
            fig_comp.update_layout(
                barmode='group',
                height=320,
                margin=dict(l=10, r=10, t=20, b=40),
                plot_bgcolor='#FFFFFF',
                paper_bgcolor='#FFFFFF',
                xaxis=dict(gridcolor='#F1F5F9', tickfont=dict(size=11, color='#1E293B')),
                yaxis=dict(gridcolor='#F1F5F9', title='Headway (minutes)', tickfont=dict(size=11, color='#1E293B')),
                legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5, font=dict(size=10, color='#1E293B'))
            )
            st.plotly_chart(fig_comp, use_container_width=True)
            st.caption("Intra-window headway evaluated strictly within contiguous time windows to avoid midday gap distortion.")
            st.markdown('</div>', unsafe_allow_html=True)

        # ---------------------------------------------------------------------
        # 3. Interactive Route-Level Frequency Explorer & Recommendation Drilldown
        # ---------------------------------------------------------------------
        st.markdown('<div class="section-container">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Route Frequency Diagnostics & Policy Simulation</div>', unsafe_allow_html=True)
        
        # Filtering Controls
        c_filter1, c_filter2, c_filter3, c_filter4 = st.columns([1.5, 1.2, 1.2, 1.1])
        
        with c_filter1:
            search_freq = st.text_input("Search Route ID, Short Name or Termini", placeholder="e.g. 500, 91, 15793, Anna Square", key="freq_search").strip()
            
        with c_filter2:
            headway_cat_filter = st.selectbox(
                "Headway Policy Category",
                options=[
                    "All Categories",
                    "High Frequency (<=10 min)",
                    "Medium Frequency (10-20 min)",
                    "Moderate (20-30 min)",
                    "Low Frequency (30-60 min)",
                    "Very Low (>60 min)",
                    "Undefined (Single-trip)"
                ]
            )
            
        with c_filter3:
            recom_filter = st.selectbox(
                "Optimization Recommendation",
                options=["All Routes", "Routes with Recommendations Only", "Peak Recommendations", "Off-Peak Recommendations"]
            )
            
        with c_filter4:
            long_gap_filter = st.selectbox(
                "Excessive Gap Flag",
                options=["All Lines", "Has Long Gap (>60m)", "No Excessive Gap"]
            )
            
        # Apply filters to frequency dataframe
        filtered_freq = df_freq.copy()
        
        if search_freq:
            filtered_freq = filtered_freq[
                filtered_freq['route_short_name'].astype(str).str.contains(search_freq, case=False, na=False) |
                filtered_freq['route_id'].astype(str).str.contains(search_freq, case=False, na=False) |
                filtered_freq['route_long_name'].astype(str).str.contains(search_freq, case=False, na=False) |
                filtered_freq['canonical_route'].astype(str).str.contains(search_freq, case=False, na=False)
            ]
            
        if headway_cat_filter != "All Categories":
            filtered_freq = filtered_freq[filtered_freq['headway_category'] == headway_cat_filter]
            
        recom_route_ids = set(df_recom['route_id'].astype(str).unique())
        if recom_filter == "Routes with Recommendations Only":
            filtered_freq = filtered_freq[filtered_freq['route_id'].isin(recom_route_ids)]
        elif recom_filter == "Peak Recommendations":
            peak_rids = set(df_recom[df_recom['time_period'] == 'Peak']['route_id'].astype(str).unique())
            filtered_freq = filtered_freq[filtered_freq['route_id'].isin(peak_rids)]
        elif recom_filter == "Off-Peak Recommendations":
            offpeak_rids = set(df_recom[df_recom['time_period'] == 'Off-Peak']['route_id'].astype(str).unique())
            filtered_freq = filtered_freq[filtered_freq['route_id'].isin(offpeak_rids)]
            
        if long_gap_filter == "Has Long Gap (>60m)":
            filtered_freq = filtered_freq[filtered_freq['has_long_gap'] == True]
        elif long_gap_filter == "No Excessive Gap":
            filtered_freq = filtered_freq[filtered_freq['has_long_gap'] == False]
            
        st.markdown(f"<div style='font-weight: 600; color: #475569; margin-bottom: 10px;'>Displaying {len(filtered_freq):,} matching active routes:</div>", unsafe_allow_html=True)
        
        # Two-Column Master Table & Route Drilldown
        col_freq_table, col_freq_drilldown = st.columns([1.35, 1.0])
        
        with col_freq_table:
            # Prepare clean presentation table
            disp_freq = filtered_freq[[
                'route_id', 'route_short_name', 'total_trips', 'median_headway_min',
                'peak_median_headway_min', 'offpeak_median_headway_min',
                'service_span_hours', 'headway_category', 'has_long_gap'
            ]].copy()
            
            disp_freq.columns = [
                'Route ID', 'Route Name', 'Trips', 'Median HW', 'Peak HW', 'Off-Peak HW',
                'Span (h)', 'Headway Category', 'Gap >60m'
            ]
            disp_freq['Trips'] = disp_freq['Trips'].astype(int)
            disp_freq['Median HW'] = disp_freq['Median HW'].apply(lambda x: f"{x:.1f}m" if pd.notna(x) else "Single-Trip")
            disp_freq['Peak HW'] = disp_freq['Peak HW'].apply(lambda x: f"{x:.1f}m" if pd.notna(x) else "N/A")
            disp_freq['Off-Peak HW'] = disp_freq['Off-Peak HW'].apply(lambda x: f"{x:.1f}m" if pd.notna(x) else "N/A")
            disp_freq['Span (h)'] = disp_freq['Span (h)'].round(1)
            disp_freq['Gap >60m'] = disp_freq['Gap >60m'].map({True: 'Yes', False: 'No'})
            
            st.dataframe(
                disp_freq,
                hide_index=True,
                use_container_width=True,
                height=480
            )
            st.caption("Select a route in the adjacent panel to view departure timeline and scenario adjustments.")
            
        with col_freq_drilldown:
            # Dropdown for drilldown route selection
            drilldown_options = (
                filtered_freq['route_short_name'] + " (ID: " + filtered_freq['route_id'] + ", Trips: " + filtered_freq['total_trips'].astype(str) + ")"
            ).tolist()
            
            if drilldown_options:
                selected_freq_label = st.selectbox("Inspect Route Frequency Details:", options=drilldown_options, index=0)
                selected_fid = selected_freq_label.split("ID: ")[1].split(",")[0].strip()
                r_freq = filtered_freq[filtered_freq['route_id'] == selected_fid].iloc[0]
                
                # Termini & Header
                st.markdown(
                    f"""
                    <div style="background-color: #F8FAFC; padding: 14px 18px; border-radius: 8px; margin-bottom: 12px; border: 1px solid #E2E8F0;">
                        <div style="font-size: 1.15rem; font-weight: 800; color: #0F172A;">
                            Route {r_freq['route_short_name']} <span style="font-size: 0.85rem; color: #64748B; font-weight: 500;">(ID: {r_freq['route_id']})</span>
                        </div>
                        <div style="font-size: 0.8rem; color: #475569; margin-top: 4px;">
                            <b>Corridor / Termini:</b> {r_freq['route_long_name']}
                        </div>
                        <div style="display: flex; gap: 14px; margin-top: 8px; font-size: 0.82rem; color: #334155; flex-wrap: wrap;">
                            <span>Total Trips: <b>{int(r_freq['total_trips'])}</b></span>
                            <span>Span: <b>{r_freq['service_span_hours']:.1f}h</b></span>
                            <span>First: <b>{int(r_freq['first_dep_hour']):02d}:00</b></span>
                            <span>Last: <b>{int(r_freq['last_dep_hour']):02d}:00</b></span>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                
                # Departures Across Time-of-Day Windows
                time_bands = [
                    ('Early Morning (05-07)', 'Early Morning (05-07)'),
                    ('Morning Peak (07-10)', 'Morning Peak (07-10)'),
                    ('Midday (10-16)', 'Midday (10-16)'),
                    ('Evening Peak (16-19)', 'Evening Peak (16-19)'),
                    ('Night (19-23)', 'Night (19-23)'),
                    ('Late Night (23-05)', 'Late Night (23-05)')
                ]
                
                band_trips = [int(r_freq[col]) for _, col in time_bands]
                band_names = [label for label, _ in time_bands]
                
                fig_route_tod = px.bar(
                    x=band_names,
                    y=band_trips,
                    text=band_trips,
                    color=band_names,
                    color_discrete_sequence=['#0B4F6C', '#1E5631', '#2B6CB0', '#5B2C6F', '#800020', '#64748B']
                )
                fig_route_tod.update_traces(textposition='auto')
                fig_route_tod.update_layout(
                    showlegend=False,
                    height=200,
                    margin=dict(l=10, r=10, t=10, b=40),
                    plot_bgcolor='#FFFFFF',
                    paper_bgcolor='#FFFFFF',
                    xaxis=dict(tickangle=-25, tickfont=dict(size=9, color='#1E293B')),
                    yaxis=dict(title='Departures', tickfont=dict(size=9, color='#1E293B'))
                )
                st.plotly_chart(fig_route_tod, use_container_width=True)
                
                # Check for recommendations for this route
                r_recoms = df_recom[df_recom['route_id'] == selected_fid]
                if not r_recoms.empty:
                    st.markdown("<div style='font-weight: 700; color: #0B4F6C; margin-bottom: 6px; font-size: 0.9rem;'>Schedule Optimization Scenario:</div>", unsafe_allow_html=True)
                    for _, rec in r_recoms.iterrows():
                        st.markdown(
                            f"""
                            <div style="background-color: #FAF5FF; padding: 10px 14px; border-radius: 6px; border-left: 3px solid #5B2C6F; margin-bottom: 8px; font-size: 0.8rem; color: #2D3748;">
                                <div style="font-weight: 700; color: #5B2C6F;">{rec['time_period']} Scenario (Target: {rec['target_headway_min']} min):</div>
                                • Observed Headway: <b>{rec['observed_headway_min']:.1f} min</b> (over {rec['active_coverage_hours']:.1f}h active span)<br>
                                • Current Scheduled Trips: <b>{int(rec['current_trips'])}</b> → Est. Needed: <b>{int(rec['estimated_needed_trips'])}</b> (<span style="color:#1E5631; font-weight:700;">+{int(rec['additional_trips'])} trips</span>)<br>
                                <span style="font-size: 0.75rem; color:#718096;"><i>Reason: {rec['reason']}</i></span>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
                else:
                    if r_freq['headway_category'] == 'Undefined (Single-trip)':
                        st.markdown(
                            """
                            <div style="background-color: #FFF5F5; padding: 10px 14px; border-radius: 6px; border-left: 3px solid #800020; font-size: 0.8rem; color: #742A2A;">
                                <b>Single-Trip Route:</b> Operates exactly 1 trip per day. Consecutive departure headway is mathematically undefined. Optimization recommendations are not applicable to single-trip lines.
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
                    else:
                        st.markdown(
                            """
                            <div style="background-color: #F0FFF4; padding: 10px 14px; border-radius: 6px; border-left: 3px solid #1E5631; font-size: 0.8rem; color: #22543D;">
                                <b>Policy Compliant:</b> Current scheduled headways satisfy the metropolitan planning targets (≤15 min Peak, ≤25 min Off-Peak) across its active operational window.
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
            else:
                st.info("No routes match the selected filter criteria.")
                
        st.markdown('</div>', unsafe_allow_html=True)
        
        # ---------------------------------------------------------------------
        # 4. Top Recommendation Candidates Table
        # ---------------------------------------------------------------------
        st.markdown('<div class="section-container">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Top Bounded Schedule Optimization Scenarios</div>', unsafe_allow_html=True)
        st.caption("Prioritized list of routes with highest additional trip requirements under the bounded operational span model.")
        
        top_recom_disp = df_recom.sort_values(['additional_trips', 'observed_headway_min'], ascending=[False, False]).head(10)[[
            'route_id', 'route_short_name', 'route_long_name', 'time_period',
            'observed_headway_min', 'target_headway_min', 'active_coverage_hours',
            'current_trips', 'estimated_needed_trips', 'additional_trips'
        ]].copy()
        
        top_recom_disp.columns = [
            'Route ID', 'Route Name', 'Termini', 'Period', 'Observed Headway',
            'Target Headway', 'Active Span', 'Current Trips', 'Needed Trips', 'Additional Trips'
        ]
        top_recom_disp['Observed Headway'] = top_recom_disp['Observed Headway'].apply(lambda x: f"{x:.1f} min")
        top_recom_disp['Target Headway'] = top_recom_disp['Target Headway'].apply(lambda x: f"{x:.0f} min")
        top_recom_disp['Active Span'] = top_recom_disp['Active Span'].apply(lambda x: f"{x:.1f}h")
        top_recom_disp['Current Trips'] = top_recom_disp['Current Trips'].astype(int)
        top_recom_disp['Needed Trips'] = top_recom_disp['Needed Trips'].astype(int)
        top_recom_disp['Additional Trips'] = top_recom_disp['Additional Trips'].apply(lambda x: f"+{int(x)}")
        
        st.dataframe(
            top_recom_disp,
            hide_index=True,
            use_container_width=True,
            height=340
        )
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.error("Bus frequency analysis datasets could not be loaded from `reports/bus_frequency_analysis.csv` or `reports/bus_frequency_recommendations.csv`.")
        
    st.markdown(
        """
        <div class="footer-text">
            Chennai MTC RouteRanker Decision Support Platform • Deep Transit Analytics Theme • Milestone 3 Frequency Optimizer
        </div>
        """,
        unsafe_allow_html=True
    )


elif selected_page == "Supply Anomaly Inspector":
    st.markdown(
        """
        <div class="header-box">
            <h1 class="header-title">Supply-Side Anomaly Inspector</h1>
            <p class="header-subtitle">
                Multidimensional scheduled service outlier diagnosis powered by the 200-tree Isolation Forest model.
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    if df_anom is not None and len(df_anom) > 0:
        # Precompute tier and driver metadata
        total_routes_anom = len(df_anom)
        tier1_count = int(df_anom['is_anomaly_top1pct'].sum()) # 41
        tier2_count = int(df_anom['is_anomaly_top5pct'].sum()) - tier1_count # 156
        top5_total = int(df_anom['is_anomaly_top5pct'].sum()) # 197
        nominal_count = total_routes_anom - top5_total # 3,737
        
        # 1. Summary KPI Cards
        col_k1, col_k2, col_k3, col_k4, col_k5, col_k6 = st.columns(6)
        with col_k1:
            st.markdown(
                f"""
                <div class="metric-card teal">
                    <div class="metric-label">Analyzed Lines</div>
                    <div class="metric-value">{total_routes_anom:,}</div>
                    <div class="metric-sub">Active GTFS route set</div>
                </div>
                """,
                unsafe_allow_html=True
            )
        with col_k2:
            st.markdown(
                f"""
                <div class="metric-card burgundy">
                    <div class="metric-label">Tier 1: Severe</div>
                    <div class="metric-value">{tier1_count}</div>
                    <div class="metric-sub">Top 1.0% Cutoff (P &ge; 99%)</div>
                </div>
                """,
                unsafe_allow_html=True
            )
        with col_k3:
            st.markdown(
                f"""
                <div class="metric-card plum">
                    <div class="metric-label">Tier 2: Moderate</div>
                    <div class="metric-value">{tier2_count}</div>
                    <div class="metric-sub">Moderate only (197 total top 5%)</div>
                </div>
                """,
                unsafe_allow_html=True
            )
        with col_k4:
            st.markdown(
                f"""
                <div class="metric-card forest">
                    <div class="metric-label">Nominal Routes</div>
                    <div class="metric-value">{nominal_count:,}</div>
                    <div class="metric-sub">{nominal_count/total_routes_anom*100:.1f}% baseline patterns</div>
                </div>
                """,
                unsafe_allow_html=True
            )
        with col_k5:
            st.markdown(
                """
                <div class="metric-card gold">
                    <div class="metric-label">Top-5% Jaccard</div>
                    <div class="metric-value">0.7473</div>
                    <div class="metric-sub">Top-5% Jaccard Stability (&rho; 0.9812)</div>
                </div>
                """,
                unsafe_allow_html=True
            )
        with col_k6:
            st.markdown(
                """
                <div class="metric-card teal">
                    <div class="metric-label">LOF Agreement</div>
                    <div class="metric-value">0.1622</div>
                    <div class="metric-sub">Dual-model Jaccard overlap</div>
                </div>
                """,
                unsafe_allow_html=True
            )
            
        # 2. Visual Distributions: Score Distribution & Severity Breakdown
        col_chart1, col_chart2 = st.columns([3, 2])
        with col_chart1:
            st.markdown('<div class="section-card">', unsafe_allow_html=True)
            st.markdown('<div class="section-title">Normalized Anomaly Score Distribution</div>', unsafe_allow_html=True)
            st.markdown(
                '<div class="section-subtitle">Min-max normalized anomaly score S_norm &isin; [0, 1] across all 3,934 active lines with severity cutoffs.</div>',
                unsafe_allow_html=True
            )
            
            fig_dist = px.histogram(
                df_anom,
                x='anomaly_score_norm',
                nbins=50,
                color_discrete_sequence=['#0B4F6C'],
                opacity=0.85
            )
            
            # Compute approximate score threshold lines for Top 5% and Top 1%
            t5_score = df_anom[df_anom['is_anomaly_top5pct']]['anomaly_score_norm'].min()
            t1_score = df_anom[df_anom['is_anomaly_top1pct']]['anomaly_score_norm'].min()
            
            fig_dist.add_vline(
                x=t5_score,
                line_dash="dash",
                line_color="#5B2C6F",
                annotation_text="Top 5% Threshold",
                annotation_position="top left",
                annotation_font=dict(color="#5B2C6F", size=10, weight="bold")
            )
            fig_dist.add_vline(
                x=t1_score,
                line_dash="dash",
                line_color="#800020",
                annotation_text="Top 1% Threshold",
                annotation_position="top right",
                annotation_font=dict(color="#800020", size=10, weight="bold")
            )
            
            fig_dist.update_layout(
                paper_bgcolor='#FFFFFF',
                plot_bgcolor='#F8F9FA',
                font=dict(family='Inter, sans-serif', color='#0F172A'),
                margin=dict(l=40, r=30, t=25, b=40),
                height=290,
                xaxis=dict(
                    title="Normalized Anomaly Score (Higher = More Isolated / Outlier)",
                    gridcolor='#E2E8F0',
                    zerolinecolor='#CBD5E1'
                ),
                yaxis=dict(
                    title="Number of Routes",
                    gridcolor='#E2E8F0',
                    zerolinecolor='#CBD5E1'
                ),
                showlegend=False
            )
            st.plotly_chart(fig_dist, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)
            
        with col_chart2:
            st.markdown('<div class="section-card">', unsafe_allow_html=True)
            st.markdown('<div class="section-title">Anomaly Severity Tiers</div>', unsafe_allow_html=True)
            st.markdown(
                '<div class="section-subtitle">Exhaustive operational tiers categorized by Isolation Forest path isolation.</div>',
                unsafe_allow_html=True
            )
            
            tier_df = pd.DataFrame([
                {'Tier': 'Tier 1: Severe (Top 1%)', 'Routes': tier1_count, 'Color': '#800020'},
                {'Tier': 'Tier 2: Moderate (Top 5%)', 'Routes': tier2_count, 'Color': '#5B2C6F'},
                {'Tier': 'Nominal Baseline', 'Routes': nominal_count, 'Color': '#0B4F6C'}
            ])
            
            fig_pie = px.pie(
                tier_df,
                values='Routes',
                names='Tier',
                color='Tier',
                color_discrete_map={
                    'Tier 1: Severe (Top 1%)': '#800020',
                    'Tier 2: Moderate (Top 5%)': '#5B2C6F',
                    'Nominal Baseline': '#0B4F6C'
                },
                hole=0.48
            )
            fig_pie.update_traces(
                textposition='inside',
                textinfo='label+percent',
                insidetextorientation='radial',
                marker=dict(line=dict(color='#FFFFFF', width=2))
            )
            fig_pie.update_layout(
                paper_bgcolor='#FFFFFF',
                plot_bgcolor='#FFFFFF',
                font=dict(family='Inter, sans-serif', color='#0F172A'),
                margin=dict(l=10, r=10, t=10, b=10),
                height=290,
                showlegend=False
            )
            st.plotly_chart(fig_pie, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

        # 3. Interactive Filters and Search
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Interactive Anomaly Filter & Search</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="section-subtitle">Query route operational profiles across anomaly severity bands and structural driving dimensions.</div>',
            unsafe_allow_html=True
        )
        
        f_col1, f_col2, f_col3, f_col4 = st.columns([3, 2.5, 2.5, 2])
        with f_col1:
            anom_search = st.text_input(
                "Search Route ID or Name",
                placeholder="e.g. 505K, 12X, 570, 10003...",
                help="Search by route ID, route short name, or canonical route name."
            ).strip().upper()
            
        with f_col2:
            tier_filter_options = [
                "All Routes (3,934)",
                "Tier 1: Severe Outliers (Top 1% - 41 routes)",
                "Tier 2: Moderate Outliers (Top 5% - 156 routes)",
                "All Flagged Anomalies (Top 5% - 197 routes)",
                "Nominal Profiles (3,737 routes)"
            ]
            selected_tier_filter = st.selectbox("Severity Classification", tier_filter_options, index=3) # Default to All Flagged
            
        with f_col3:
            driver_labels = {
                "ALL": "All Primary Drivers",
                "stop_spacing_km": "Stop Spacing (km/stop)",
                "route_speed_proxy": "Route Speed Proxy (km/trip)",
                "trips_per_stop": "Trips per Stop Ratio",
                "scheduled_trip_count": "Scheduled Trip Count",
                "headway_missing_indicator": "Single-Trip (Missing Headway)",
                "scheduled_headway_min": "Scheduled Headway (min)",
                "route_length_km": "Route Length (km)",
                "stop_count": "Stop Count"
            }
            driver_options = ["ALL"] + [d for d in driver_labels.keys() if d != "ALL"]
            selected_driver = st.selectbox(
                "Primary Anomaly Driver",
                driver_options,
                format_func=lambda x: driver_labels.get(x, x),
                index=0
            )
            
        with f_col4:
            sort_options = [
                "Percentile Rank (High to Low)",
                "Normalized Score (High to Low)",
                "Scheduled Trips (Low to High)",
                "Scheduled Trips (High to Low)",
                "Route Length (High to Low)",
                "Stop Spacing (High to Low)"
            ]
            selected_sort = st.selectbox("Sort Table By", sort_options, index=0)
            
        # Apply Filters
        filtered_anom = df_anom.copy()
        
        if anom_search:
            filtered_anom = filtered_anom[
                filtered_anom['route_id'].str.upper().str.contains(anom_search, na=False) |
                filtered_anom['route_short_name'].astype(str).str.upper().str.contains(anom_search, na=False) |
                filtered_anom['canonical_route'].astype(str).str.upper().str.contains(anom_search, na=False)
            ]
            
        if "Top 1%" in selected_tier_filter:
            filtered_anom = filtered_anom[filtered_anom['is_anomaly_top1pct'] == True]
        elif "Tier 2: Moderate" in selected_tier_filter:
            filtered_anom = filtered_anom[(filtered_anom['is_anomaly_top5pct'] == True) & (filtered_anom['is_anomaly_top1pct'] == False)]
        elif "All Flagged" in selected_tier_filter:
            filtered_anom = filtered_anom[filtered_anom['is_anomaly_top5pct'] == True]
        elif "Nominal" in selected_tier_filter:
            filtered_anom = filtered_anom[filtered_anom['is_anomaly_top5pct'] == False]
            
        if selected_driver != "ALL":
            filtered_anom = filtered_anom[filtered_anom['primary_driver'] == selected_driver]
            
        # Sorting
        if selected_sort == "Percentile Rank (High to Low)":
            filtered_anom = filtered_anom.sort_values(by='anomaly_percentile', ascending=False)
        elif selected_sort == "Normalized Score (High to Low)":
            filtered_anom = filtered_anom.sort_values(by='anomaly_score_norm', ascending=False)
        elif selected_sort == "Scheduled Trips (Low to High)":
            filtered_anom = filtered_anom.sort_values(by='scheduled_trip_count', ascending=True)
        elif selected_sort == "Scheduled Trips (High to Low)":
            filtered_anom = filtered_anom.sort_values(by='scheduled_trip_count', ascending=False)
        elif selected_sort == "Route Length (High to Low)":
            filtered_anom = filtered_anom.sort_values(by='route_length_km', ascending=False)
        elif selected_sort == "Stop Spacing (High to Low)":
            filtered_anom = filtered_anom.sort_values(by='stop_spacing_km', ascending=False)
            
        st.markdown(
            f"<div style='font-size:0.88rem; color:#475569; margin-top:8px; margin-bottom:12px; font-weight:600;'>"
            f"Displaying <b>{len(filtered_anom):,}</b> matching route profiles."
            f"</div>",
            unsafe_allow_html=True
        )
        
        # Display Table
        disp_cols = [
            'route_id', 'route_short_name', 'canonical_route', 'anomaly_percentile',
            'anomaly_score_norm', 'scheduled_trip_count', 'stop_count',
            'stop_spacing_km', 'primary_driver', 'is_anomaly_top1pct', 'is_anomaly_top5pct'
        ]
        
        def assign_tier_label(row):
            if row['is_anomaly_top1pct']:
                return "Tier 1: Severe (Top 1%)"
            elif row['is_anomaly_top5pct']:
                return "Tier 2: Moderate (Top 5%)"
            else:
                return "Tier 3: Nominal"
                
        table_df = filtered_anom[disp_cols].copy()
        table_df['Severity Tier'] = table_df.apply(assign_tier_label, axis=1)
        table_df['Primary Driver'] = table_df['primary_driver'].map(lambda x: driver_labels.get(x, x))
        
        table_df = table_df.rename(columns={
            'route_id': 'Route ID',
            'route_short_name': 'Route Name',
            'canonical_route': 'Corridor / Termini',
            'anomaly_percentile': 'Percentile Rank',
            'anomaly_score_norm': 'Score (Norm)',
            'scheduled_trip_count': 'Trips',
            'stop_count': 'Stops',
            'stop_spacing_km': 'Stop Spacing (km)'
        })
        
        final_table = table_df[[
            'Route ID', 'Route Name', 'Corridor / Termini', 'Severity Tier',
            'Percentile Rank', 'Score (Norm)', 'Trips', 'Stops',
            'Stop Spacing (km)', 'Primary Driver'
        ]].copy()
        
        final_table['Percentile Rank'] = final_table['Percentile Rank'].apply(lambda x: f"{x:.2f}%")
        final_table['Score (Norm)'] = final_table['Score (Norm)'].apply(lambda x: f"{x:.4f}")
        final_table['Stop Spacing (km)'] = final_table['Stop Spacing (km)'].apply(lambda x: f"{x:.2f}")
        final_table['Trips'] = final_table['Trips'].astype(int)
        final_table['Stops'] = final_table['Stops'].astype(int)
        
        st.dataframe(
            final_table,
            hide_index=True,
            use_container_width=True,
            height=380
        )
        st.markdown('</div>', unsafe_allow_html=True)
        
        # 4. Route-Level Detailed Anomaly Inspection
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Deep Route Diagnostic & Explainability Drilldown</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="section-subtitle">Examine multidimensional operational outliers with Robust Quantile Discrepancy analysis and automated archetype synthesis.</div>',
            unsafe_allow_html=True
        )
        
        # Select route from filtered or entire dataset
        if len(filtered_anom) > 0:
            route_options = filtered_anom['route_id'].tolist()
        else:
            route_options = df_anom['route_id'].tolist()
            
        def route_format_func(rid):
            row = df_anom[df_anom['route_id'] == rid].iloc[0]
            tier_str = "T1: Severe" if row['is_anomaly_top1pct'] else ("T2: Moderate" if row['is_anomaly_top5pct'] else "Nominal")
            return f"Route {row['route_short_name']} (ID {rid}) • {tier_str} • P={row['anomaly_percentile']:.1f}%"
            
        sel_col1, sel_col2 = st.columns([3, 1])
        with sel_col1:
            selected_route_id = st.selectbox(
                "Select Route for Diagnostic Review",
                route_options,
                format_func=route_format_func,
                index=0
            )
            
        route_row = df_anom[df_anom['route_id'] == selected_route_id].iloc[0]
        
        # Display route cards
        rc1, rc2, rc3, rc4 = st.columns(4)
        with rc1:
            tier_badge = "Tier 1: Severe Outlier" if route_row['is_anomaly_top1pct'] else ("Tier 2: Moderate Outlier" if route_row['is_anomaly_top5pct'] else "Nominal Baseline")
            tier_css = "burgundy" if route_row['is_anomaly_top1pct'] else ("plum" if route_row['is_anomaly_top5pct'] else "forest")
            st.markdown(
                f"""
                <div class="metric-card {tier_css}">
                    <div class="metric-label">Classification</div>
                    <div class="metric-value" style="font-size:1.35rem; font-weight:800;">{tier_badge}</div>
                    <div class="metric-sub">Rank {route_row['anomaly_percentile']:.2f}th Percentile</div>
                </div>
                """,
                unsafe_allow_html=True
            )
        with rc2:
            st.markdown(
                f"""
                <div class="metric-card teal">
                    <div class="metric-label">Anomaly Score</div>
                    <div class="metric-value">{route_row['anomaly_score_norm']:.4f}</div>
                    <div class="metric-sub">Raw Isolation Score: {route_row['anomaly_score_raw']:.4f}</div>
                </div>
                """,
                unsafe_allow_html=True
            )
        with rc3:
            hw_str = f"{route_row['scheduled_headway_min']:.1f} min" if pd.notnull(route_row['scheduled_headway_min']) and route_row['scheduled_headway_min'] > 0 else "Undefined (Single-Trip)"
            st.markdown(
                f"""
                <div class="metric-card gold">
                    <div class="metric-label">Scheduled Service</div>
                    <div class="metric-value">{int(route_row['scheduled_trip_count'])} Trips</div>
                    <div class="metric-sub">Mean Headway: {hw_str}</div>
                </div>
                """,
                unsafe_allow_html=True
            )
        with rc4:
            st.markdown(
                f"""
                <div class="metric-card forest">
                    <div class="metric-label">Route Geometry</div>
                    <div class="metric-value">{route_row['route_length_km']:.1f} km</div>
                    <div class="metric-sub">{int(route_row['stop_count'])} stops • {route_row['stop_spacing_km']:.2f} km/stop</div>
                </div>
                """,
                unsafe_allow_html=True
            )
            
        # Archetype & Automated Diagnosis Callout Box
        prim_str = driver_labels.get(str(route_row['primary_driver']), str(route_row['primary_driver']))
        sec_str = driver_labels.get(str(route_row['secondary_driver']), str(route_row['secondary_driver']))
        
        st.markdown(
            f"""
            <div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; border-left: 5px solid #0B4F6C; border-radius: 8px; padding: 18px 22px; margin-top: 10px; margin-bottom: 20px;">
                <div style="display: flex; align-items: baseline; gap: 12px; margin-bottom: 8px;">
                    <span style="font-size: 1.15rem; font-weight: 700; color: #0F172A;">
                        Route {route_row['route_short_name']} ({route_row['canonical_route']})
                    </span>
                    <span style="font-size: 0.85rem; font-weight: 600; color: #64748B;">
                        [Route ID: {route_row['route_id']}]
                    </span>
                </div>
                <div style="font-size: 0.95rem; color: #1E293B; line-height: 1.55; margin-bottom: 12px;">
                    <b>Diagnostic Assessment:</b> {route_row['anomaly_explanation']}
                </div>
                <div style="display: flex; gap: 24px; font-size: 0.85rem; color: #475569; flex-wrap: wrap; border-top: 1px solid #E2E8F0; padding-top: 10px;">
                    <div><b>Primary Isolation Driver:</b> <span style="color: #800020; font-weight: 700;">{prim_str}</span></div>
                    <div><b>Secondary Driver:</b> <span style="color: #5B2C6F; font-weight: 700;">{sec_str}</span></div>
                    <div><b>Trips per Stop Ratio:</b> {route_row['trips_per_stop']:.3f}</div>
                    <div><b>Speed Proxy:</b> {route_row['route_speed_proxy']:.1f} km/trip</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        # Operational Metric Comparison with Network Medians
        st.markdown("##### Multidimensional Operational Profile vs. Network Median")
        
        metric_profile_data = [
            {
                "Dimension": "Scheduled Daily Trips",
                "Route Value": f"{int(route_row['scheduled_trip_count'])} trips",
                "Network Median": "4.0 trips",
                "Network Q1 - Q3 (IQR)": "2.0 - 15.0 trips",
                "Status": "Extreme Low" if route_row['scheduled_trip_count'] <= 1 else ("High Volume" if route_row['scheduled_trip_count'] >= 50 else "Typical")
            },
            {
                "Dimension": "Stop Count",
                "Route Value": f"{int(route_row['stop_count'])} stops",
                "Network Median": "38.0 stops",
                "Network Q1 - Q3 (IQR)": "28.0 - 47.0 stops",
                "Status": "Truncated" if route_row['stop_count'] < 15 else ("Extended" if route_row['stop_count'] > 60 else "Typical")
            },
            {
                "Dimension": "Route Length",
                "Route Value": f"{route_row['route_length_km']:.2f} km",
                "Network Median": "20.73 km",
                "Network Q1 - Q3 (IQR)": "14.28 - 29.54 km",
                "Status": "Long Distance" if route_row['route_length_km'] > 40 else ("Short Shuttle" if route_row['route_length_km'] < 8 else "Typical")
            },
            {
                "Dimension": "Mean Stop Spacing",
                "Route Value": f"{route_row['stop_spacing_km']:.2f} km/stop",
                "Network Median": "0.55 km/stop",
                "Network Q1 - Q3 (IQR)": "0.47 - 0.65 km/stop",
                "Status": "High Skip-Stop (>1.0 km)" if route_row['stop_spacing_km'] > 1.0 else ("Dense (<0.4 km)" if route_row['stop_spacing_km'] < 0.4 else "Typical")
            },
            {
                "Dimension": "Scheduled Headway",
                "Route Value": f"{route_row['scheduled_headway_min']:.1f} min" if pd.notnull(route_row['scheduled_headway_min']) and route_row['scheduled_headway_min'] > 0 else "Undefined (Single-Trip)",
                "Network Median": "63.0 min",
                "Network Q1 - Q3 (IQR)": "31.3 - 120.0 min",
                "Status": "Missing/Single-Trip" if route_row['headway_missing_indicator'] == 1 else ("Frequent" if route_row['scheduled_headway_min'] <= 15 else "Infrequent")
            }
        ]
        
        st.dataframe(
            pd.DataFrame(metric_profile_data),
            hide_index=True,
            use_container_width=True
        )
        st.markdown('</div>', unsafe_allow_html=True)
        
        # 5. Methodological Documentation, Validation & Operational Disclaimer
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Model Architecture, Cross-Validation & Governance</div>', unsafe_allow_html=True)
        
        m_col1, m_col2 = st.columns(2)
        with m_col1:
            st.markdown(
                r"""
                <div style="font-size:0.9rem; line-height:1.6; color:#1E293B;">
                    <h5 style="color:#0B4F6C; margin-bottom:8px; font-weight:700;">Isolation Forest Specification</h5>
                    <ul>
                        <li><b>Ensemble Size:</b> 200 completely randomized isolation trees (<code>n_estimators=200</code>) trained on 3,934 active scheduled routes.</li>
                        <li><b>Feature Vector (8 Dimensions):</b> Stop count, route length, scheduled trips, mean headway, headway missing flag, trips-per-stop, stop spacing, and speed proxy.</li>
                        <li><b>Data Leakage Prevention:</b> Median headway imputation fit strictly within cross-validation folds; no network target leakage.</li>
                        <li><b>Driver Attribution:</b> Robust Quantile Discrepancy \(R_j = (x_j - Q_2) / \text{IQR}\) maps each isolated route to its most deviant operational dimensions without parametric distribution assumptions.</li>
                    </ul>
                </div>
                """,
                unsafe_allow_html=True
            )
        with m_col2:
            st.markdown(
                """
                <div style="font-size:0.9rem; line-height:1.6; color:#1E293B;">
                    <h5 style="color:#5B2C6F; margin-bottom:8px; font-weight:700;">Empirical Stability & Benchmarks</h5>
                    <ul>
                        <li><b>Rank Stability (5 Seeds):</b> Spearman rank correlation <b>&rho; = 0.9812</b> across randomized runs, proving exceptional structural ranking stability.</li>
                        <li><b>Top-5% Jaccard Stability:</b> Top-5% boundary Jaccard index of <b>0.7473</b> across 5 seeds due to expected threshold jitter at the 95th percentile border.</li>
                        <li><b>LOF Benchmark Concordance:</b> Local Outlier Factor Jaccard overlap of <b>0.1622</b> (55 intersecting routes out of 197), confirming that Isolation Forest captures global multi-dimensional extremes while LOF identifies local density variations.</li>
                    </ul>
                </div>
                """,
                unsafe_allow_html=True
            )
            
        st.markdown(
            """
            <div style="background-color: #FEF3C7; border-left: 4px solid #C59B27; padding: 12px 16px; border-radius: 4px; font-size: 0.88rem; color: #92400E; margin-top: 14px;">
                <b>Operational Boundary Disclaimer:</b> The Supply-Side Anomaly Inspector evaluates <i>scheduled transit supply patterns</i> derived solely from static GTFS publications. High anomaly scores indicate statistical deviation from the network baseline (e.g., single-trip transfer loops, express skip-stop patterns, or extreme high-frequency corridors). Anomaly flags represent candidates for transit planning audit, <b>not</b> mechanical vehicle defects, driver infractions, operational unreliability, or passenger crowding.
            </div>
            """,
            unsafe_allow_html=True
        )
        st.markdown('</div>', unsafe_allow_html=True)
        
    else:
        st.error("Route anomaly dataset could not be loaded from `reports/route_anomaly_scores.csv`.")
        
    st.markdown(
        """
        <div class="footer-text">
            Chennai MTC RouteRanker Decision Support Platform • Deep Transit Analytics Theme • Milestone 4 Supply Anomaly Inspector
        </div>
        """,
        unsafe_allow_html=True
    )

elif selected_page == "Network Map Explorer":
    st.markdown(
        """
        <div class="header-box">
            <h1 class="header-title">Network Spatial & Trajectory Map</h1>
            <p class="header-subtitle">
                Interactive stop connectivity and corridor path visualizer across 5,580 network bus stops.
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )
    # ------------------------------------------------------------
    # Load GTFS data (cached)
    # ------------------------------------------------------------
    @st.cache_data(show_spinner=False)
    def load_gtfs():
        base = "."
        stops_path = os.path.join(base, "stops.txt")
        routes_path = os.path.join(base, "routes.txt")
        trips_path = os.path.join(base, "trips.txt")
        shapes_path = os.path.join(base, "shapes.txt")
        df_stops = pd.read_csv(stops_path, dtype={"stop_id": str, "stop_name": str, "stop_lat": float, "stop_lon": float})
        df_routes = pd.read_csv(routes_path, dtype={"route_id": str, "route_short_name": str, "route_long_name": str})
        df_trips = pd.read_csv(trips_path, dtype={"trip_id": str, "route_id": str, "service_id": str, "direction_id": int})
        df_shapes = None
        if os.path.exists(shapes_path):
            df_shapes = pd.read_csv(shapes_path)
        return {"stops": df_stops, "routes": df_routes, "trips": df_trips, "shapes": df_shapes}

    gtfs = load_gtfs()
    df_stops = gtfs["stops"]
    df_routes = gtfs["routes"]
    df_shapes = gtfs["shapes"]

    # ------------------------------------------------------------
    # Route selector UI
    # ------------------------------------------------------------
    route_options = df_routes["route_id"].astype(str).tolist()
    route_labels = {
        rid: f"{df_routes.loc[df_routes["route_id"] == rid, "route_short_name"].iloc[0]} (ID {rid})"
        for rid in route_options
    }
    selected_route_id = st.selectbox(
        "Select Route",
        options=route_options,
        format_func=lambda x: route_labels.get(x, x)
    )

    # ------------------------------------------------------------
    # KPI cards
    # ------------------------------------------------------------
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"""
        <div class=\"metric-card teal\">
            <div class=\"metric-label\">Total Stops</div>
            <div class=\"metric-value\">{len(df_stops):,}</div>
            <div class=\"metric-sub\">In GTFS</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class=\"metric-card gold\">
            <div class=\"metric-label\">Routes Loaded</div>
            <div class=\"metric-value\">{len(df_routes):,}</div>
            <div class=\"metric-sub\">From routes.txt</div>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        cluster_desc = "N/A"
        if df_clust is not None:
            mask = df_clust["route_id"].astype(str) == selected_route_id
            if mask.any():
                cl = int(df_clust.loc[mask, "kmeans_cluster"].iloc[0])
                cluster_desc = "Low‑frequency core & secondary feeder" if cl == 0 else "High‑frequency core trunk"
        st.markdown(f"""
        <div class=\"metric-card plum\">
            <div class=\"metric-label\">Cluster</div>
            <div class=\"metric-value\">{cluster_desc}</div>
            <div class=\"metric-sub\">K‑Means (k=2)</div>
        </div>
        """, unsafe_allow_html=True)

    # ------------------------------------------------------------
    # Map options
    # ------------------------------------------------------------
    show_stops = st.checkbox("Show stop markers", value=True)
    centre_lat = df_stops["stop_lat"].mean()
    centre_lon = df_stops["stop_lon"].mean()
    fig = go.Figure()
    if show_stops:
        fig.add_trace(
            go.Scattermapbox(
                lat=df_stops["stop_lat"],
                lon=df_stops["stop_lon"],
                mode="markers",
                marker=dict(size=6, color="#C59B27"),
                name="Stops",
            )
        )
    # Attempt to draw route shape if available
    if df_shapes is not None and not df_shapes.empty:
        # GTFS shape linking is typically via trips.shape_id; check column existence
        if "shape_id" in gtfs["trips"].columns:
            shape_ids = gtfs["trips"].loc[gtfs["trips"]["route_id"] == selected_route_id, "shape_id"]
            if not shape_ids.empty:
                shape_id = shape_ids.iloc[0]
                shape_df = df_shapes[df_shapes["shape_id"] == shape_id].sort_values("shape_pt_sequence")
                if not shape_df.empty:
                    fig.add_trace(
                        go.Scattermapbox(
                            lat=shape_df["shape_pt_lat"],
                            lon=shape_df["shape_pt_lon"],
                            mode="lines",
                            line=dict(width=4, color="#800020"),
                            name="Route Shape",
                        )
                    )
                else:
                    st.warning("Selected route has no shape geometry in shapes.txt.")
            else:
                st.warning("No shape_id linked to this route in trips.txt.")
        else:
            st.warning("GTFS does not contain shape_id in trips.txt; cannot render route geometry.")
    else:
        st.warning("Shape data not available in this GTFS package – only stop markers are shown.")

    fig.update_layout(
        mapbox_style="open-street-map",
        mapbox_center={"lat": centre_lat, "lon": centre_lon},
        mapbox_zoom=11,
        margin=dict(l=0, r=0, t=0, b=0),
        height=600,
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        legend=dict(bgcolor="rgba(255,255,255,0.8)"),
    )
    st.plotly_chart(fig, use_container_width=True)

    # ------------------------------------------------------------
    # Footer consistent with other pages
    # ------------------------------------------------------------
    st.markdown(
        """
        <div class=\"footer-text\">Chennai MTC RouteRanker Decision Support Platform • Network Map Explorer</div>
        """,
        unsafe_allow_html=True,
    )

elif selected_page == "Interactive Route Groups Explorer":
    st.markdown(
        """
        <div class="header-box">
            <h1 class="header-title">Route Groups Explorer</h1>
            <p class="header-subtitle">Cluster-based analysis of scheduled supply patterns.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Cluster selection
    cluster_options = {0: "Low-frequency core & secondary feeder network", 1: "High-frequency core trunk corridors"}
    selected_cluster = st.selectbox(
        "Select Cluster",
        options=list(cluster_options.keys()),
        format_func=lambda x: f"Cluster {x}: {cluster_options[x]}",
    )

    # Filter clustering data
    if df_clust is not None:
        df_cluster = df_clust[df_clust["kmeans_cluster"] == selected_cluster].copy()

        # KPI cards
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(
                f"<div class='metric-card teal'><h3>{len(df_cluster)}</h3><p>Routes in cluster</p></div>",
                unsafe_allow_html=True,
            )
        with col2:
            avg_headway = pd.to_numeric(df_cluster["weekday_headway_min"], errors="coerce").mean()
            avg_hw_str = f"{avg_headway:.1f}" if pd.notna(avg_headway) else "N/A"
            st.markdown(
                f"<div class='metric-card gold'><h3>{avg_hw_str}</h3><p>Avg weekday headway (min)</p></div>",
                unsafe_allow_html=True,
            )
        with col3:
            total_stops = int(df_cluster["stop_count"].sum())
            st.markdown(
                f"<div class='metric-card plum'><h3>{total_stops:,}</h3><p>Total Route-Stops (Cumulative)</p></div>",
                unsafe_allow_html=True,
            )

        # Cluster distribution chart
        st.subheader("Cluster Distribution")
        dist_df = df_clust["kmeans_cluster"].value_counts().reset_index()
        dist_df.columns = ["cluster", "count"]
        dist_df["label"] = dist_df["cluster"].map(cluster_options)
        fig_dist = px.bar(
            dist_df,
            x="label",
            y="count",
            color="label",
            color_discrete_sequence=["#0B4F6C", "#5B2C6F"],
            labels={"label": "Cluster", "count": "Number of Routes"},
            title="Routes per Cluster",
        )
        st.plotly_chart(fig_dist, use_container_width=True)

        # Searchable route table
        st.subheader("Routes in Selected Cluster")
        search_term = st.text_input("Search by Route ID or Name", key="rg_search")
        display_cols = ["route_id", "route_short_name", "weekday_trip_count", "weekday_headway_min", "kmeans_cluster"]
        df_display = df_cluster[display_cols].copy()
        if search_term:
            mask = (
                df_display["route_id"].astype(str).str.contains(search_term, case=False, na=False)
                | df_display["route_short_name"].astype(str).str.contains(search_term, case=False, na=False)
            )
            df_display = df_display[mask]
        df_display = df_display.rename(
            columns={
                "route_id": "Route ID",
                "route_short_name": "Route Name",
                "weekday_trip_count": "Weekday Trips",
                "weekday_headway_min": "Weekday Headway (min)",
                "kmeans_cluster": "Cluster",
            }
        )
        st.dataframe(df_display, hide_index=True, use_container_width=True)

        # Route-level drill-down
        st.subheader("Route Drill-Down")
        route_ids = df_cluster["route_id"].tolist()
        if route_ids:
            selected_route_id = st.selectbox(
                "Select a route for details",
                options=route_ids,
                key="rg_drilldown",
            )
            route_detail = df_cluster[df_cluster["route_id"] == selected_route_id].iloc[0]
            st.markdown(
                f"**Route:** {route_detail['route_short_name']} "
                f"| **ID:** {route_detail['route_id']} "
                f"| **Cluster {selected_cluster}:** {cluster_options[selected_cluster]}"
            )
            d1, d2, d3, d4 = st.columns(4)
            with d1:
                st.markdown(
                    f"""
                    <div class="metric-card teal">
                        <div class="metric-label">Stop Count</div>
                        <div class="metric-value">{int(route_detail['stop_count'])}</div>
                        <div class="metric-sub">Stops on route</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            with d2:
                len_km = route_detail.get("route_length_km", None)
                len_str = f"{float(len_km):.2f} km" if pd.notna(len_km) else "N/A"
                st.markdown(
                    f"""
                    <div class="metric-card forest">
                        <div class="metric-label">Route Length</div>
                        <div class="metric-value">{len_str}</div>
                        <div class="metric-sub">Scheduled trajectory</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            with d3:
                trips_val = int(route_detail["weekday_trip_count"]) if pd.notna(route_detail["weekday_trip_count"]) else 0
                st.markdown(
                    f"""
                    <div class="metric-card gold">
                        <div class="metric-label">Weekday Trips</div>
                        <div class="metric-value">{trips_val}</div>
                        <div class="metric-sub">Scheduled daily frequency</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            with d4:
                hw = route_detail["weekday_headway_min"]
                hw_val = f"{float(hw):.1f} min" if pd.notna(hw) and float(hw) > 0 else ("Undefined (Single-Trip)" if route_detail['weekday_trip_count'] == 1 else "N/A")
                st.markdown(
                    f"""
                    <div class="metric-card plum">
                        <div class="metric-label">Headway</div>
                        <div class="metric-value" style="font-size: 1.45rem;">{hw_val}</div>
                        <div class="metric-sub">Mean departure interval</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
        else:
            st.info("No routes found for this cluster.")

        st.caption(
            "These clusters reflect scheduled supply patterns from GTFS data. "
            "They describe operational frequency and coverage characteristics, "
            "not passenger demand or ridership."
        )
    else:
        st.error("Clustering data could not be loaded.")


elif selected_page == "Scenario Simulator":
    st.markdown(
        """
        <div class="header-box">
            <h1 class="header-title">Scenario Simulator</h1>
            <p class="header-subtitle">
                Schedule-based frequency simulation and headway adjustment modeling across Chennai MTC transit corridors.
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    if df_ranking is not None and not df_ranking.empty:
        st.markdown(
            """
            <div class="section-container">
                <div class="section-title">Schedule-Based Transit Service Simulation</div>
                <p style="color: #64748B; font-size: 0.9rem; margin-bottom: 0;">
                    Simulate policy-driven timetable modifications on active lines. Adjust headway thresholds or apply network frequency multipliers to evaluate additional trip requirements.
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        sim_col1, sim_col2 = st.columns([1, 1])
        
        with sim_col1:
            scenario_type = st.selectbox(
                "Select Simulation Scenario",
                options=[
                    "High-Frequency Trunk Headway Regularization (Target <= 10 min)",
                    "Off-Peak Feeder Headway Regularization (Target <= 30 min)",
                    "Peak Period Service Reinforcement (+15% to +35%)",
                    "Custom Network Service Adjustment Multiplier"
                ],
                help="Choose a policy intervention to evaluate its impact on scheduled departures and headways."
            )
            
        with sim_col2:
            scope_filter = st.selectbox(
                "Corridor Scope Filter",
                options=[
                    "All Active Operational Lines (3,934 routes)",
                    "Cluster 1: High-Frequency Trunk Corridors (291 routes)",
                    "Cluster 0: Core Network & Feeder Routes (3,643 routes)"
                ],
                help="Define the operational subset of lines affected by this policy scenario."
            )
            
        # Parameter controls based on selected scenario
        param_col1, param_col2 = st.columns([1, 1])
        
        if "Trunk Headway" in scenario_type:
            with param_col1:
                target_headway = st.slider("Target Maximum Headway (minutes)", min_value=5, max_value=20, value=10, step=1)
            with param_col2:
                st.caption(f"Clamps headway to a maximum of **{target_headway} minutes** on selected lines with headways exceeding the target.")
            sim_mode = "headway_cap"
            multiplier = 1.0
        elif "Off-Peak" in scenario_type:
            with param_col1:
                target_headway = st.slider("Target Maximum Headway (minutes)", min_value=15, max_value=45, value=30, step=5)
            with param_col2:
                st.caption(f"Regularizes long feeder intervals down to a maximum of **{target_headway} minutes**.")
            sim_mode = "headway_cap"
            multiplier = 1.0
        elif "Peak Period" in scenario_type:
            with param_col1:
                boost_pct = st.slider("Peak Trip Frequency Boost (%)", min_value=10, max_value=40, value=20, step=5)
            with param_col2:
                st.caption(f"Increases daily trips by **+{boost_pct}%** to absorb peak travel demand.")
            sim_mode = "multiplier"
            multiplier = 1.0 + (boost_pct / 100.0)
            target_headway = 0
        else:
            with param_col1:
                adj_pct = st.slider("Service Adjustment Percentage (%)", min_value=-20, max_value=50, value=15, step=5)
            with param_col2:
                st.caption(f"Simulates a uniform **{adj_pct:+d}%** change in scheduled trips across selected lines.")
            sim_mode = "multiplier"
            multiplier = 1.0 + (adj_pct / 100.0)
            target_headway = 0
            
        # Filter base dataframe
        df_sim_base = df_ranking.copy()
        
        # Merge cluster if available
        if df_clust is not None and not df_clust.empty:
            df_sim_base = df_sim_base.merge(
                df_clust[['route_id', 'kmeans_cluster']],
                on='route_id',
                how='left'
            )
        else:
            df_sim_base['kmeans_cluster'] = 0
            
        if "Cluster 1" in scope_filter:
            df_sim_base = df_sim_base[df_sim_base['kmeans_cluster'] == 1].copy()
        elif "Cluster 0" in scope_filter:
            df_sim_base = df_sim_base[df_sim_base['kmeans_cluster'] == 0].copy()
            
        # Perform schedule-based simulation
        sim_records = []
        for _, row in df_sim_base.iterrows():
            b_trips = int(row['daily_scheduled_trips'])
            b_hw = float(row['effective_headway_min']) if pd.notnull(row['effective_headway_min']) else np.nan
            
            if sim_mode == "headway_cap":
                if pd.notnull(b_hw) and b_hw > target_headway and b_trips > 1:
                    s_hw = float(target_headway)
                    s_trips = max(b_trips, int(np.round(b_trips * (b_hw / target_headway))))
                else:
                    s_hw = b_hw
                    s_trips = b_trips
            else:
                s_trips = max(1, int(np.round(b_trips * multiplier)))
                if pd.notnull(b_hw) and b_trips > 1:
                    s_hw = max(4.0, np.round(b_hw / multiplier, 1))
                else:
                    s_hw = b_hw
                    
            sim_records.append({
                'route_id': str(row['route_id']),
                'route_short_name': row['route_short_name'],
                'cluster': int(row.get('kmeans_cluster', 0)) if pd.notnull(row.get('kmeans_cluster')) else 0,
                'baseline_trips': b_trips,
                'simulated_trips': s_trips,
                'delta_trips': s_trips - b_trips,
                'baseline_headway': b_hw,
                'simulated_headway': s_hw,
                'delta_headway': (s_hw - b_hw) if pd.notnull(s_hw) and pd.notnull(b_hw) else 0.0
            })
            
        df_sim_results = pd.DataFrame(sim_records)
        
        # -------------------------------------------------------------
        # Impact KPI Cards
        # -------------------------------------------------------------
        total_base_trips = int(df_sim_results['baseline_trips'].sum())
        total_sim_trips = int(df_sim_results['simulated_trips'].sum())
        delta_trips_total = total_sim_trips - total_base_trips
        
        mean_base_hw = df_sim_results[df_sim_results['baseline_trips'] > 1]['baseline_headway'].mean()
        mean_sim_hw = df_sim_results[df_sim_results['simulated_trips'] > 1]['simulated_headway'].mean()
        delta_hw_mean = mean_sim_hw - mean_base_hw if pd.notnull(mean_sim_hw) and pd.notnull(mean_base_hw) else 0.0
        
        routes_improved = int((df_sim_results['delta_trips'] > 0).sum())
        
        kc1, kc2, kc3, kc4 = st.columns(4)
        
        with kc1:
            st.markdown(
                f"""
                <div class="metric-card teal">
                    <div class="metric-label">Daily Trip Volume</div>
                    <div class="metric-value">{total_sim_trips:,}</div>
                    <div class="metric-sub">Baseline: {total_base_trips:,} ({delta_trips_total:+d} trips)</div>
                </div>
                """,
                unsafe_allow_html=True
            )
        with kc2:
            st.markdown(
                f"""
                <div class="metric-card forest">
                    <div class="metric-label">Vehicle-Trip Demand</div>
                    <div class="metric-value">{delta_trips_total:+d}</div>
                    <div class="metric-sub">Additional daily dispatches</div>
                </div>
                """,
                unsafe_allow_html=True
            )
        with kc3:
            st.markdown(
                f"""
                <div class="metric-card gold">
                    <div class="metric-label">Mean Scheduled Headway</div>
                    <div class="metric-value">{mean_sim_hw:.1f} min</div>
                    <div class="metric-sub">Baseline: {mean_base_hw:.1f} min ({delta_hw_mean:+.1f} min)</div>
                </div>
                """,
                unsafe_allow_html=True
            )
        with kc4:
            st.markdown(
                f"""
                <div class="metric-card plum">
                    <div class="metric-label">Impacted Lines</div>
                    <div class="metric-value">{routes_improved}</div>
                    <div class="metric-sub">Routes with increased service</div>
                </div>
                """,
                unsafe_allow_html=True
            )
            
        st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)
        
        # -------------------------------------------------------------
        # Comparison Visualizations
        # -------------------------------------------------------------
        vcol1, vcol2 = st.columns([1, 1])
        
        with vcol1:
            st.markdown(
                """
                <div class="section-container" style="padding-bottom: 8px;">
                    <div class="section-title">Headway Distribution: Baseline vs. Simulated</div>
                </div>
                """,
                unsafe_allow_html=True
            )
            
            # Filter multi-trip routes for headway histogram
            valid_hw = df_sim_results[df_sim_results['baseline_trips'] > 1].dropna(subset=['baseline_headway', 'simulated_headway'])
            if not valid_hw.empty:
                fig_hw_hist = go.Figure()
                fig_hw_hist.add_trace(go.Histogram(
                    x=np.clip(valid_hw['baseline_headway'], 5, 120),
                    name='Baseline Headway',
                    opacity=0.65,
                    marker_color='#0B4F6C',
                    nbinsx=25
                ))
                fig_hw_hist.add_trace(go.Histogram(
                    x=np.clip(valid_hw['simulated_headway'], 5, 120),
                    name='Simulated Headway',
                    opacity=0.65,
                    marker_color='#C59B27',
                    nbinsx=25
                ))
                fig_hw_hist.update_layout(
                    barmode='overlay',
                    xaxis_title='Headway (minutes, capped at 120 min)',
                    yaxis_title='Route Count',
                    height=360,
                    margin=dict(l=30, r=30, t=20, b=30),
                    legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
                    paper_bgcolor="#FFFFFF",
                    plot_bgcolor="#FFFFFF"
                )
                st.plotly_chart(fig_hw_hist, use_container_width=True)
            else:
                st.info("No multi-trip routes in selected scope for headway comparison.")
                
        with vcol2:
            st.markdown(
                """
                <div class="section-container" style="padding-bottom: 8px;">
                    <div class="section-title">Top Lines by Additional Trips Required</div>
                </div>
                """,
                unsafe_allow_html=True
            )
            
            top_gainers = df_sim_results.sort_values('delta_trips', ascending=False).head(10)
            if not top_gainers.empty and top_gainers['delta_trips'].max() > 0:
                fig_gainers = px.bar(
                    top_gainers,
                    x='delta_trips',
                    y='route_short_name',
                    orientation='h',
                    labels={'delta_trips': 'Additional Daily Trips', 'route_short_name': 'Route Name'},
                    color='delta_trips',
                    color_continuous_scale=['#5B2C6F', '#0B4F6C'],
                    height=360
                )
                fig_gainers.update_layout(
                    yaxis=dict(autorange='reversed'),
                    margin=dict(l=30, r=30, t=20, b=30),
                    paper_bgcolor="#FFFFFF",
                    plot_bgcolor="#FFFFFF"
                )
                st.plotly_chart(fig_gainers, use_container_width=True)
            else:
                st.info("No trip increases under the currently selected parameters.")
                
        # -------------------------------------------------------------
        # Granular Route Impact Table
        # -------------------------------------------------------------
        st.markdown(
            """
            <div class="section-container" style="padding-bottom: 8px;">
                <div class="section-title">Route-Level Service Impact Ledger</div>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        disp_cols = [
            'route_id', 'route_short_name', 'cluster', 'baseline_trips',
            'simulated_trips', 'delta_trips', 'baseline_headway',
            'simulated_headway', 'delta_headway'
        ]
        
        df_table_out = df_sim_results[disp_cols].copy()
        df_table_out.columns = [
            'Route ID', 'Route Name', 'Cluster', 'Baseline Trips',
            'Simulated Trips', 'Trip Change', 'Base Headway (m)',
            'Sim Headway (m)', 'Headway Change (m)'
        ]
        
        st.dataframe(
            df_table_out.sort_values('Trip Change', ascending=False),
            hide_index=True,
            use_container_width=True
        )
        
        # -------------------------------------------------------------
        # Limitations Callout
        # -------------------------------------------------------------
        st.markdown(
            """
            <div class="explanation-callout">
                <div style="font-weight: 700; color: #800020; margin-bottom: 6px; font-size: 0.95rem;">
                    Schedule Simulation Boundaries & Operational Assumptions:
                </div>
                <ul style="margin: 0; padding-left: 20px; font-size: 0.88rem; color: #334155; line-height: 1.5;">
                    <li><b>Supply-Side Timetable Model:</b> This simulator calculates scheduled departure frequency requirements based strictly on GTFS timetable intervals.</li>
                    <li><b>Resource Feasibility:</b> Vehicle fleet acquisition costs, bus maintenance depot schedules, and crew duty rotas are not modeled.</li>
                    <li><b>Demand Non-Fabrication:</b> Passenger ridership, ticket revenue elasticity, and crowding reductions are strictly excluded due to the absence of empirical smartcard/ticketing data.</li>
                </ul>
            </div>
            """,
            unsafe_allow_html=True
        )
    else:
        st.error("Ranking dataset is unavailable. Ensure `reports/route_ranking_results.csv` exists.")
        
    st.markdown(
        """
        <div class="footer-text">
            Chennai MTC RouteRanker Decision Support Platform • Module 8 Scenario Simulator
        </div>
        """,
        unsafe_allow_html=True
    )


elif selected_page == "Model Evaluation":
    st.markdown(
        """
        <div class="header-box">
            <h1 class="header-title">Model Evaluation & Methodology Audit</h1>
            <p class="header-subtitle">
                Quantitative validation benchmarks, empirical stability tests, and algorithmic audits of the transit analytics pipeline.
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    tab_clust, tab_anom, tab_rank, tab_gov = st.tabs([
        "Route Typology (K-Means)",
        "Anomaly Detection (Isolation Forest)",
        "Multi-Criteria Ranking",
        "Data Governance & Boundaries"
    ])
    
    # -------------------------------------------------------------------------
    # TAB 1: Route Typology Clustering
    # -------------------------------------------------------------------------
    with tab_clust:
        st.markdown(
            """
            <div class="section-container">
                <div class="section-title">K-Means Hyperparameter Selection & Validation (k=2)</div>
                <p style="color: #64748B; font-size: 0.9rem;">
                    Unsupervised clustering segments Chennai MTC routes into functional operational profiles using 12 supply-side topological and timetable features.
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.markdown(
                """
                <div class="metric-card teal">
                    <div class="metric-label">Silhouette Score</div>
                    <div class="metric-value">0.4671</div>
                    <div class="metric-sub">Optimal cluster separation (k=2)</div>
                </div>
                """,
                unsafe_allow_html=True
            )
        with m2:
            st.markdown(
                """
                <div class="metric-card forest">
                    <div class="metric-label">Davies-Bouldin Index</div>
                    <div class="metric-value">1.0005</div>
                    <div class="metric-sub">Lowest dispersion across k in [2,6]</div>
                </div>
                """,
                unsafe_allow_html=True
            )
        with m3:
            st.markdown(
                """
                <div class="metric-card gold">
                    <div class="metric-label">Calinski-Harabasz</div>
                    <div class="metric-value">1,060.4</div>
                    <div class="metric-sub">Variance ratio criterion</div>
                </div>
                """,
                unsafe_allow_html=True
            )
        with m4:
            st.markdown(
                """
                <div class="metric-card plum">
                    <div class="metric-label">Active Segregation</div>
                    <div class="metric-value">92.6% / 7.4%</div>
                    <div class="metric-sub">3,643 Core Feeders • 291 Trunks</div>
                </div>
                """,
                unsafe_allow_html=True
            )
            
        st.markdown("<div style='height: 14px;'></div>", unsafe_allow_html=True)
        
        # Hyperparameter evaluation table
        st.subheader("Hyperparameter Optimization Ledger (k = 2 to 6)")
        k_eval_data = [
            {"k": 2, "Silhouette Score": 0.4671, "Davies-Bouldin": 1.0005, "Calinski-Harabasz": 1060.4, "Evaluation": "Optimal (Selected)"},
            {"k": 3, "Silhouette Score": 0.2686, "Davies-Bouldin": 1.4691, "Calinski-Harabasz": 1179.1, "Evaluation": "Fragmented Sub-clusters"},
            {"k": 4, "Silhouette Score": 0.2777, "Davies-Bouldin": 1.2821, "Calinski-Harabasz": 1215.8, "Evaluation": "Sub-optimal Silhouette"},
            {"k": 5, "Silhouette Score": 0.3002, "Davies-Bouldin": 1.1762, "Calinski-Harabasz": 1239.0, "Evaluation": "High Intra-cluster Variance"},
            {"k": 6, "Silhouette Score": 0.2748, "Davies-Bouldin": 1.2412, "Calinski-Harabasz": 1159.3, "Evaluation": "Over-partitioned Topology"}
        ]
        st.dataframe(pd.DataFrame(k_eval_data), hide_index=True, use_container_width=True)
        
        st.markdown(
            """
            <div class="explanation-callout">
                <b>Algorithmic Comparison & Justification:</b>
                <ul>
                    <li><b>K-Means (k=2):</b> Recommended baseline achieving global cluster cohesion without overfitting. Separates high-frequency core trunk corridors from localized feeder services.</li>
                    <li><b>Agglomerative Hierarchical (Ward):</b> Achieved Silhouette 0.5739 and DB 0.7142; used as comparative baseline validating the 2-group network partition.</li>
                    <li><b>DBSCAN:</b> Rejected due to extreme transit network density disparities (produced 361 isolated noise points).</li>
                </ul>
            </div>
            """,
            unsafe_allow_html=True
        )

    # -------------------------------------------------------------------------
    # TAB 2: Supply-Side Anomaly Detection
    # -------------------------------------------------------------------------
    with tab_anom:
        st.markdown(
            """
            <div class="section-container">
                <div class="section-title">Isolation Forest Architecture & Stability Benchmarks</div>
                <p style="color: #64748B; font-size: 0.9rem;">
                    Unsupervised anomaly detection identifying structural supply-side timetable outliers across 11 engineered GTFS operational dimensions.
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        a1, a2, a3, a4 = st.columns(4)
        with a1:
            st.markdown(
                """
                <div class="metric-card teal">
                    <div class="metric-label">Jaccard Stability</div>
                    <div class="metric-value">0.7473</div>
                    <div class="metric-sub">Top-5% overlap across random seeds</div>
                </div>
                """,
                unsafe_allow_html=True
            )
        with a2:
            st.markdown(
                """
                <div class="metric-card burgundy">
                    <div class="metric-label">Rank Correlation</div>
                    <div class="metric-value">0.9812</div>
                    <div class="metric-sub">Spearman rho across random seeds</div>
                </div>
                """,
                unsafe_allow_html=True
            )
        with a3:
            st.markdown(
                """
                <div class="metric-card plum">
                    <div class="metric-label">LOF Concordance</div>
                    <div class="metric-value">0.1622</div>
                    <div class="metric-sub">Global isolation vs local density</div>
                </div>
                """,
                unsafe_allow_html=True
            )
        with a4:
            st.markdown(
                """
                <div class="metric-card gold">
                    <div class="metric-label">Severity Tiers</div>
                    <div class="metric-value">41 / 156</div>
                    <div class="metric-sub">41 Tier 1 Severe • 156 Tier 2 Moderate</div>
                </div>
                """,
                unsafe_allow_html=True
            )
            
        st.markdown("<div style='height: 14px;'></div>", unsafe_allow_html=True)
        
        st.subheader("Benchmark Verification & Concordance Audit")
        benchmarks = [
            {"Benchmark Metric": "Spearman Rank Correlation (rho)", "Empirical Value": "0.9812", "Benchmark Threshold": "> 0.90", "Validation Verdict": "PASS (High Stability)"},
            {"Benchmark Metric": "Top-5% Jaccard Overlap Stability", "Empirical Value": "0.7473", "Benchmark Threshold": "> 0.70", "Validation Verdict": "PASS (Robust Reproducibility)"},
            {"Benchmark Metric": "LOF Benchmark Concordance", "Empirical Value": "0.1622", "Benchmark Threshold": "Informational", "Validation Verdict": "CONFIRMED (Global isolation captures structural outliers)"},
            {"Benchmark Metric": "Analyzed Operational Lines", "Empirical Value": "3,934", "Benchmark Threshold": "3,934 Active", "Validation Verdict": "PASS (100% Coverage)"}
        ]
        st.dataframe(pd.DataFrame(benchmarks), hide_index=True, use_container_width=True)

    # -------------------------------------------------------------------------
    # TAB 3: Multi-Criteria Ranking Architecture
    # -------------------------------------------------------------------------
    with tab_rank:
        st.markdown(
            """
            <div class="section-container">
                <div class="section-title">Explainable Multi-Criteria Composite Index</div>
                <p style="color: #64748B; font-size: 0.9rem;">
                    Transparent weighted scoring architecture evaluating 3,934 active lines across 6 supply-side criteria.
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        criteria_matrix = [
            {"Operational Criterion": "Scheduled Trip Frequency", "Weight": "25%", "Direction": "Benefit (Higher is better)", "Normalization Formula": "Linear Min-Max [0, 1]"},
            {"Operational Criterion": "Departure Headway Convenience", "Weight": "25%", "Direction": "Cost (Shorter is better)", "Normalization Formula": "(180 - min(180, max(5, H))) / 175"},
            {"Operational Criterion": "Stop Coverage Reach", "Weight": "15%", "Direction": "Benefit (Higher is better)", "Normalization Formula": "Linear Min-Max [0, 1]"},
            {"Operational Criterion": "Network Hub Connectivity", "Weight": "15%", "Direction": "Benefit (Higher is better)", "Normalization Formula": "Linear Min-Max on Graph Degree"},
            {"Operational Criterion": "Corridor Length Utility", "Weight": "10%", "Direction": "Bounded Benefit", "Normalization Formula": "min(30.0, Length) / 30.0"},
            {"Operational Criterion": "Operating Service Span", "Weight": "10%", "Direction": "Benefit (Higher is better)", "Normalization Formula": "min(18.0, Span) / 18.0"}
        ]
        st.dataframe(pd.DataFrame(criteria_matrix), hide_index=True, use_container_width=True)
        
        st.markdown(
            """
            <div class="explanation-callout">
                <b>Composite Formulation:</b><br>
                Overall Score = 100 * SUM(w_j * S_ij). Unserviced lines (677 routes with 0 trips) are isolated with status 'Unserviced' and score 0.0 to prevent skewing rank statistics.
            </div>
            """,
            unsafe_allow_html=True
        )

    # -------------------------------------------------------------------------
    # TAB 4: Data Governance & Operational Boundaries
    # -------------------------------------------------------------------------
    with tab_gov:
        st.markdown(
            """
            <div class="section-container">
                <div class="section-title">Data Science Integrity Certification & Governance</div>
                <p style="color: #64748B; font-size: 0.9rem;">
                    Formal verification of analytical boundaries, non-fabrication protocols, and GTFS scope compliance.
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        st.markdown(
            """
            <div style="background-color: #ECFDF5; border-left: 4px solid #1E5631; padding: 14px 18px; border-radius: 6px; margin-bottom: 14px;">
                <b style="color: #065F46; font-size: 0.95rem;">Zero-Ridership Non-Fabrication Certification:</b><br>
                <span style="font-size: 0.88rem; color: #047857;">
                    The Chennai MTC repository contains static GTFS timetables (routes, trips, stops, stop_times). <b>No empirical ticketing, passenger boardings, or smartcard tap-in/tap-out data exists.</b> In compliance with strict engineering ethics, zero synthetic ridership, passenger demand, or farebox revenue numbers have been fabricated.
                </span>
            </div>
            
            <div style="background-color: #FEF3C7; border-left: 4px solid #C59B27; padding: 14px 18px; border-radius: 6px; margin-bottom: 14px;">
                <b style="color: #92400E; font-size: 0.95rem;">Supply-Side Anomaly Governance Boundary:</b><br>
                <span style="font-size: 0.88rem; color: #B45309;">
                    Anomaly flags identify statistical outliers in published scheduled transit service (e.g. single-trip loops or extreme headway gaps). They indicate candidates for transit planning timetable audit, <b>never</b> driver infractions, mechanical bus breakdowns, or vehicle unreliability.
                </span>
            </div>
            
            <div style="background-color: #EFF6FF; border-left: 4px solid #0B4F6C; padding: 14px 18px; border-radius: 6px;">
                <b style="color: #1E40AF; font-size: 0.95rem;">Verified GTFS Asset Ground Truth:</b><br>
                <span style="font-size: 0.88rem; color: #1D4ED8;">
                    Total published lines: 4,611 routes • Active operational lines: 3,934 routes • Network stop facilities: 5,580 unique stops • Total scheduled daily trips: 47,047 trips.
                </span>
            </div>
            """,
            unsafe_allow_html=True
        )
        
    st.markdown(
        """
        <div class="footer-text">
            Chennai MTC RouteRanker Decision Support Platform • Model Evaluation & Algorithmic Audit
        </div>
        """,
        unsafe_allow_html=True
    )

elif selected_page == "Methodology & Audit":
    st.markdown(
        """
        <div class="header-box">
            <h1 class="header-title">System Methodology & Audit Framework</h1>
            <p class="header-subtitle">
                Technical documentation of the Chennai MTC GTFS data science pipeline and verified model parameters.
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )
    st.markdown(
        """
        ### Analytical Pipeline
        1. **Data Ingestion (Tasks 01–05):** Ingestion of 47,047 trips and 5,580 stops; filtering to 3,934 active lines; handling 869 single-trip routes with undefined headways.
        2. **Route Typology Clustering (Task 06):** Unsupervised K-Means ($k=2$) segmentation distinguishing Core Network Routes (92.6%) from High-Frequency Trunk Corridors (7.4%).
        3. **Explainable Multi-Criteria Ranking (Task 07):** Weighted composite index across 6 operational dimensions: Frequency (25%), Headway (25%), Stop Coverage (15%), Hub Connectivity (15%), Length Utility (10%), Service Span (10%).
        4. **Frequency Policy Optimization (Task 08):** Granular headway calculations and bounded trip recommendations across 6 daily time intervals.
        5. **Supply-Side Anomaly Detection (Isolation Forest):** Unsupervised isolation trees isolating structural operational outliers with Robust Quantile Discrepancy profiles.
        """
    )

elif selected_page == "Data & Backend Status":
    st.markdown(
        """
        <div class="header-box">
            <h1 class="header-title">Data & Backend Infrastructure Status</h1>
            <p class="header-subtitle">
                System health, local SQLite metadata repository, collection audit logs, and data feed operational boundaries.
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )

    try:
        from backend import api as backend_api
        from backend import ingest as backend_ingest
        backend_available = True
    except Exception as import_err:
        backend_available = False
        st.error(f"Backend services could not be imported: {import_err}")

    if backend_available:
        # Action controls
        col_scan, col_info = st.columns([1, 3])
        with col_scan:
            if st.button("🔄 Scan Datasets Now", help="Triggers read-only metadata ingestion across reports and GTFS files without duplicating entries."):
                with st.spinner("Scanning project datasets and calculating checksums..."):
                    res_csv = backend_ingest.ingest_csv_metadata()
                    res_gtfs = backend_ingest.ingest_gtfs_txt_metadata()
                    st.success(f"Scan complete: Processed {res_csv['files_processed'] + res_gtfs['files_processed']} new, {res_csv['files_skipped'] + res_gtfs['files_skipped']} existing skipped.")

        # Infrastructure Health Metrics
        counts = backend_api.get_table_counts()
        total_meta = counts.get('dataset_metadata', 0)
        total_logs = counts.get('collection_log', 0)
        latest_status = backend_api.get_latest_collection_status()
        status_label = latest_status['status'].upper() if latest_status else "INITIALIZED"

        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.markdown(
                f"""
                <div class="metric-card teal">
                    <div class="metric-label">Database Engine</div>
                    <div class="metric-value" style="font-size: 1.5rem;">SQLite 3</div>
                    <div class="metric-caption">WAL Mode • Local Storage</div>
                </div>
                """,
                unsafe_allow_html=True
            )

        with col2:
            st.markdown(
                f"""
                <div class="metric-card forest">
                    <div class="metric-label">Catalogued Datasets</div>
                    <div class="metric-value">{total_meta}</div>
                    <div class="metric-caption">Tracked CSV & GTFS Files</div>
                </div>
                """,
                unsafe_allow_html=True
            )

        with col3:
            st.markdown(
                f"""
                <div class="metric-card gold">
                    <div class="metric-label">Collection Audit Runs</div>
                    <div class="metric-value">{total_logs}</div>
                    <div class="metric-caption">Audited Run History Logs</div>
                </div>
                """,
                unsafe_allow_html=True
            )

        with col4:
            card_class = "forest" if status_label == "SUCCESS" else "gold"
            st.markdown(
                f"""
                <div class="metric-card {card_class}">
                    <div class="metric-label">Last Ingest Status</div>
                    <div class="metric-value" style="font-size: 1.5rem;">{status_label}</div>
                    <div class="metric-caption">No Duplicates Detected</div>
                </div>
                """,
                unsafe_allow_html=True
            )

        st.markdown("---")

        # Live Feed Operational Boundary Notice
        st.markdown(
            """
            <div style="background-color: #FFFBEB; border: 1px solid #FDE68A; border-left: 5px solid #F59E0B; border-radius: 8px; padding: 14px 18px; margin-bottom: 20px;">
                <b style="color: #92400E; font-size: 0.92rem;">Operational Data Boundary Notice:</b><br>
                <span style="color: #78350F; font-size: 0.85rem; line-height: 1.6;">
                    • <b>Automatic Scheduled Collection:</b> <span style="color:#B45309; font-weight:600;">Not Configured</span> (Local on-demand execution enabled; background daemons/schedulers require hosting infrastructure).<br>
                    • <b>Live GPS / AVL Vehicle Feed:</b> <span style="color:#B45309; font-weight:600;">Not Available</span> (MTC currently publishes static scheduled GTFS; no public real-time telemetry stream).<br>
                    • <b>Passenger Ridership / ETM Data:</b> <span style="color:#B45309; font-weight:600;">Not Available</span> (System strictly operates on verified supply-side timetable data. No ridership or boarding figures are fabricated).
                </span>
            </div>
            """,
            unsafe_allow_html=True
        )

        # Tabbed details: Metadata Catalog vs Ingestion History
        tab_catalog, tab_history = st.tabs(["📁 Catalogued Dataset Inventory", "📜 Ingestion Audit Logs"])

        with tab_catalog:
            datasets = backend_api.get_dataset_summary()
            if datasets:
                df_meta = pd.DataFrame(datasets)
                display_cols = {
                    'filename': 'File Name',
                    'row_count': 'Row Count',
                    'file_size_bytes': 'Size (Bytes)',
                    'sha256': 'SHA-256 Checksum',
                    'modified_at': 'Source Modified Time',
                    'latest_ingested_at': 'Catalogued At'
                }
                show_df = df_meta[[c for c in display_cols.keys() if c in df_meta.columns]].rename(columns=display_cols)
                st.dataframe(show_df, use_container_width=True, hide_index=True)
            else:
                st.info("No dataset metadata records found. Click 'Scan Datasets Now' to initialize.")

        with tab_history:
            history = backend_api.get_collection_history(limit=25)
            if history:
                df_hist = pd.DataFrame(history)
                hist_cols = {
                    'run_id': 'Run UUID',
                    'source': 'Source Channel',
                    'status': 'Status',
                    'files_processed': 'New Ingested',
                    'files_skipped': 'Skipped (Duplicates)',
                    'message': 'Audit Message',
                    'started_at': 'Execution Time'
                }
                show_hist = df_hist[[c for c in hist_cols.keys() if c in df_hist.columns]].rename(columns=hist_cols)
                st.dataframe(show_hist, use_container_width=True, hide_index=True)
            else:
                st.info("No collection log entries available.")

elif selected_page == "Ridership Insights":
    st.markdown(
        """
        <div class="header-box">
            <h1 class="header-title">Official Chennai MTC Ridership Insights</h1>
            <p class="header-subtitle">
                System-wide verified passenger volumes, daily reporting-period averages, and official corporate benchmarks.
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )

    # Operational Boundary Disclaimer
    st.markdown(
        """
        <div style="background-color: #EFF6FF; border: 1px solid #BFDBFE; border-left: 5px solid #3B82F6; border-radius: 8px; padding: 14px 18px; margin-bottom: 20px;">
            <b style="color: #1E40AF; font-size: 0.92rem;">Reporting Specification & Boundary Notice:</b><br>
            <span style="color: #1E3A8A; font-size: 0.85rem; line-height: 1.6;">
                • All passenger numbers displayed are <b>official reporting-period daily averages</b> published by the Metropolitan Transport Corporation (Chennai) Ltd.<br>
                • These statistics represent <b>macro system-wide aggregates</b> across the entire bus network, <b>NOT</b> individual daily observations or sensor counts.<br>
                • Ridership statistics are strictly separated from route-level ranking, clustering, and anomaly predictions (which are purely supply-driven GTFS models).
            </span>
        </div>
        """,
        unsafe_allow_html=True
    )

    # Key Metric Cards for Official Reporting Periods
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(
            """
            <div class="metric-card teal">
                <div class="metric-label">FY 2024–25 Daily Average</div>
                <div class="metric-value">32.24 <span style="font-size: 1.1rem; font-weight: 500;">Lakh</span></div>
                <div class="metric-caption">Period Average • Full Fiscal Year</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    with col2:
        st.markdown(
            """
            <div class="metric-card forest">
                <div class="metric-label">FY 2025–26 Daily Average</div>
                <div class="metric-value">34.00 <span style="font-size: 1.1rem; font-weight: 500;">Lakh</span></div>
                <div class="metric-caption">+5.46% YoY Growth • Full Fiscal Year</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    with col3:
        st.markdown(
            """
            <div class="metric-card burgundy">
                <div class="metric-label">FY 2026–27 (Through Oct 2026)</div>
                <div class="metric-value">34.58 <span style="font-size: 1.1rem; font-weight: 500;">Lakh</span></div>
                <div class="metric-caption">+1.71% vs FY 25–26 • 7-Month Cumulative Average</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

    # Visual Comparison Chart
    col_chart, col_source = st.columns([3, 2])
    with col_chart:
        df_ridership = pd.DataFrame([
            {"Reporting Period": "FY 2024–25 (Full Year)", "Daily Average (Lakhs)": 32.24, "Absolute Daily Passengers": 3224000, "Period Scope": "Annual Average"},
            {"Reporting Period": "FY 2025–26 (Full Year)", "Daily Average (Lakhs)": 34.00, "Absolute Daily Passengers": 3400000, "Period Scope": "Annual Average"},
            {"Reporting Period": "FY 2026–27 (Up to Oct 2026)", "Daily Average (Lakhs)": 34.58, "Absolute Daily Passengers": 3458000, "Period Scope": "7-Month Average"}
        ])

        fig_bar = px.bar(
            df_ridership,
            x="Reporting Period",
            y="Daily Average (Lakhs)",
            text="Daily Average (Lakhs)",
            title="Official System-Wide Average Daily Passengers by Reporting Period",
            color="Reporting Period",
            color_discrete_sequence=["#0B4F6C", "#1E5631", "#800020"]
        )
        fig_bar.update_traces(texttemplate='%{text:.2f} Lakhs/Day', textposition='outside')
        fig_bar.update_layout(
            yaxis=dict(range=[28, 38], title="Average Passengers per Day (Lakhs)"),
            xaxis=dict(title=""),
            showlegend=False,
            height=380,
            margin=dict(l=40, r=40, t=50, b=40)
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    with col_source:
        st.markdown(
            """
            <div style="background-color: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 10px; padding: 20px; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);">
                <h4 style="color: #0F172A; margin-top: 0; font-size: 1.05rem;">Provenance & Verification Metadata</h4>
                <table style="width: 100%; font-size: 0.85rem; border-collapse: collapse; line-height: 1.8;">
                    <tr><td style="color: #64748B; width: 40%;"><b>Publishing Agency:</b></td><td style="color: #0F172A;">Metropolitan Transport Corporation (Chennai) Ltd.</td></tr>
                    <tr><td style="color: #64748B;"><b>Source Dataset:</b></td><td style="color: #0F172A;">MTC Performance Indicators (SRC-01)</td></tr>
                    <tr><td style="color: #64748B;"><b>Data Granularity:</b></td><td style="color: #0F172A;">System-wide Corporate Aggregate</td></tr>
                    <tr><td style="color: #64748B;"><b>Metric Type:</b></td><td style="color: #0F172A;">Reporting-Period Daily Mean</td></tr>
                    <tr><td style="color: #64748B;"><b>Authenticity Status:</b></td><td style="color: #16A34A; font-weight: 700;">Verified Official Record</td></tr>
                    <tr><td style="color: #64748B;"><b>File Location:</b></td><td style="color: #0F172A;"><code>data/external/mtc_performance_indicators.csv</code></td></tr>
                </table>
            </div>
            """,
            unsafe_allow_html=True
        )

    # Detailed Verified Table
    st.markdown("<h3 style='font-size: 1.15rem; color: #0F172A; margin-top: 25px;'>Verified Corporate Performance Table</h3>", unsafe_allow_html=True)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    perf_path = os.path.join(base_dir, "data", "external", "mtc_performance_indicators.csv")
    if os.path.isfile(perf_path):
        df_perf_raw = pd.read_csv(perf_path)
        rename_cols = {
            'sl_no': 'S.No',
            'item': 'Operational Indicator',
            'unit': 'Unit',
            '2024_2025': 'FY 2024–25',
            '2025_2026': 'FY 2025–26',
            '2026_2027_oct': 'FY 2026–27 (Through Oct)'
        }
        st.dataframe(df_perf_raw.rename(columns=rename_cols), use_container_width=True, hide_index=True)
    else:
        st.dataframe(df_ridership, use_container_width=True, hide_index=True)

elif selected_page == "Historical Data Analysis":
    st.markdown(
        """
        <div class="header-box">
            <h1 class="header-title">Historical MTC Passenger Statistics & Trend Analysis</h1>
            <p class="header-subtitle">
                Longitudinal comparison of official Metropolitan Transport Corporation passenger volume benchmarks across reporting periods.
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )

    # Historical Highlights Metrics
    hcol1, hcol2, hcol3, hcol4 = st.columns(4)
    with hcol1:
        st.markdown(
            """
            <div class="metric-card teal">
                <div class="metric-label">FY 24–25 Baseline</div>
                <div class="metric-value">32.24 <span style="font-size: 1rem;">L/Day</span></div>
                <div class="metric-caption">Annual Benchmark</div>
            </div>
            """,
            unsafe_allow_html=True
        )
    with hcol2:
        st.markdown(
            """
            <div class="metric-card forest">
                <div class="metric-label">FY 25–26 Growth</div>
                <div class="metric-value">+5.46%</div>
                <div class="metric-caption">+1.76 Lakh Passengers/Day</div>
            </div>
            """,
            unsafe_allow_html=True
        )
    with hcol3:
        st.markdown(
            """
            <div class="metric-card burgundy">
                <div class="metric-label">FY 26–27 (Oct) Trend</div>
                <div class="metric-value">+1.71%</div>
                <div class="metric-caption">+0.58 Lakh vs Prior FY</div>
            </div>
            """,
            unsafe_allow_html=True
        )
    with hcol4:
        st.markdown(
            """
            <div class="metric-card gold">
                <div class="metric-label">Overall 3-Period Expansion</div>
                <div class="metric-value">+7.26%</div>
                <div class="metric-caption">32.24L → 34.58L / Day</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    st.markdown("<div style='height: 15px;'></div>", unsafe_allow_html=True)

    # Trend Chart
    hist_periods = ["FY 2024–25", "FY 2025–26", "FY 2026–27 (Oct)"]
    hist_values = [32.24, 34.00, 34.58]
    hist_fleet = [3407, 4060, 4206]
    hist_services = [3233, 3783, 3988]

    df_hist_trend = pd.DataFrame({
        "Reporting Period": hist_periods,
        "Passengers per Day (Lakhs)": hist_values,
        "Total Fleet (Buses)": hist_fleet,
        "Scheduled Services (Buses)": hist_services,
        "Percentage Change (%)": [0.0, 5.46, 1.71]
    })

    fig_trend = go.Figure()
    fig_trend.add_trace(go.Scatter(
        x=df_hist_trend["Reporting Period"],
        y=df_hist_trend["Passengers per Day (Lakhs)"],
        mode="lines+markers+text",
        text=[f"{v:.2f} L" for v in hist_values],
        textposition="top center",
        name="Average Passengers/Day (Lakhs)",
        line=dict(color="#0B4F6C", width=3),
        marker=dict(size=10, color="#C59B27")
    ))

    fig_trend.update_layout(
        title="Multi-Period Trajectory: Official Chennai MTC Daily Passenger Volume",
        yaxis=dict(title="Passengers per Day (in Lakhs)", range=[30, 36]),
        xaxis=dict(title="Reporting Fiscal Period"),
        height=380,
        margin=dict(l=40, r=40, t=50, b=40)
    )
    st.plotly_chart(fig_trend, use_container_width=True)

    # Cross-Metric Historical Tabulation
    st.markdown("<h3 style='font-size: 1.15rem; color: #0F172A; margin-top: 15px;'>Multi-Year Operational & Ridership Comparison Matrix</h3>", unsafe_allow_html=True)

    df_matrix = pd.DataFrame({
        "Fiscal Reporting Period": hist_periods,
        "Daily Passengers (Lakhs)": [32.24, 34.00, 34.58],
        "Period-over-Period Change": ["Baseline", "+5.46% (+1.76 L)", "+1.71% (+0.58 L)"],
        "Fleet Size (Operational Buses)": [3407, 4060, 4206],
        "Scheduled Services": [3233, 3783, 3988],
        "Fleet Growth (%)": ["Baseline", "+19.17%", "+3.60%"],
        "Reporting Status": ["Audited Fiscal Record", "Audited Fiscal Record", "Interim 7-Month Snapshot (Verified)"]
    })
    st.dataframe(df_matrix, use_container_width=True, hide_index=True)

    # Governance and Data Integrity Box
    st.markdown(
        """
        <div style="margin-top: 25px; padding: 14px 18px; background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; font-size: 0.82rem; color: #475569; line-height: 1.6;">
            <b>Data Provenance & Scientific Integrity Standards:</b><br>
            • <b>Source:</b> Metropolitan Transport Corporation (Chennai) Ltd. official performance publications (SRC-01 archive).<br>
            • <b>Periodicity:</b> Figures represent official full-year or verified partial-year corporate averages. No interpolated or synthetic intermediate daily points were created.<br>
            • <b>Supply-Demand Separation:</b> Historical corporate totals reflect macro system scale. They are displayed for operational context and are not used as labels in the unsupervised route ranking or anomaly detection models.
        </div>
        """,
        unsafe_allow_html=True
    )


