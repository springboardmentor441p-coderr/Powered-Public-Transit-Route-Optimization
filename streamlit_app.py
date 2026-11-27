"""RouteRanker - Streamlit entry point.

    streamlit run streamlit_app.py
"""
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "app"))

st.set_page_config(page_title="RouteRanker · AI Transit Route Optimisation", page_icon="🚌", layout="wide",
                   initial_sidebar_state="expanded")

from common import ist_clock_sidebar  # noqa: E402

V = "app/views"
pages = {
    "Overview": [
        st.Page(f"{V}/network_overview.py", title="Network Overview", icon=":material/map:", default=True),
        st.Page(f"{V}/best_route.py", title="Best Route Today (Live)", icon=":material/emoji_events:"),
    ],
    "Analysis": [
        st.Page(f"{V}/productivity_ranking.py", title="Productivity Ranking", icon=":material/leaderboard:"),
        st.Page(f"{V}/route_comparison.py", title="Route Comparison", icon=":material/compare_arrows:"),
        st.Page(f"{V}/historical_replay.py", title="Historical Replay", icon=":material/history:"),
        st.Page(f"{V}/eda_insights.py", title="EDA Insights", icon=":material/insights:"),
    ],
    "Optimisation": [
        st.Page(f"{V}/scenario_simulator.py", title="Scenario Simulator", icon=":material/science:"),
        st.Page(f"{V}/recommendations.py", title="Optimisation Actions", icon=":material/tune:"),
    ],
    "Models & Data": [
        st.Page(f"{V}/model_performance.py", title="Model Performance", icon=":material/model_training:"),
        st.Page(f"{V}/data_coverage.py", title="Data & Coverage", icon=":material/database:"),
        st.Page(f"{V}/pipeline_architecture.py", title="Pipeline & Architecture", icon=":material/account_tree:"),
    ],
}
nav = st.navigation(pages)
st.sidebar.markdown("### 🚌 RouteRanker")
st.sidebar.caption("AI-powered public transit route optimisation")
ist_clock_sidebar()
nav.run()
