"""Run with: python -m streamlit run streamlit_app.py"""
import streamlit as st

from dashboard.data import DataUnavailable, table
from dashboard.views import PAGES
from dashboard.planning_views import EXTRA_PAGES

PAGES = {**PAGES, **EXTRA_PAGES}

st.set_page_config(page_title="RouteRanker · Network planning", page_icon="🚍", layout="wide",
                   initial_sidebar_state="expanded")
st.markdown("""<style>
.block-container {max-width: 1400px; padding-top: 2rem; padding-bottom: 3rem;}
h1, h2, h3 {letter-spacing: -.025em;}
[data-testid="stSidebar"] {border-right: 1px solid #dce5ee;}
.brand {font-size: 1.75rem; font-weight: 750; color: #183b56; letter-spacing: -.06em;}
.brand span {color: #087f8c;}
.eyebrow {font-size: .72rem; font-weight: 700; letter-spacing: .15em; color: #92d8d9;}
.hero {background: #183b56; border-radius: 14px; padding: 30px 34px; margin-bottom: 15px;}
.hero h1 {color: #fff; font-size: 2.3rem; line-height: 1.2; margin: .6rem 0;}
.hero p {color: #d3e4ef; margin: 0; max-width: 680px;}
[data-testid="stMetric"] {background: #fff;}
@media (max-width: 700px) {.hero {padding: 22px;} .hero h1 {font-size: 1.8rem;}}
</style>""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown('<div class="brand">Route<span>Ranker</span></div>', unsafe_allow_html=True)
    st.caption("Bus network planning workspace")
    st.divider()
    page = st.radio("Workspace", list(PAGES), label_visibility="collapsed", key="workspace")

try:
    if page in ['GTFS import', 'Observed-load classification']:
        PAGES[page](None)
    else:
        routes = table("review")
        with st.sidebar:
            st.divider()
            options = sorted(routes.bus_route)
            route = st.selectbox("Selected route", options, index=options.index("M34+"), key="selected_route")
            st.caption(routes.set_index("bus_route").loc[route, "route_long_name"])
            st.caption("Route selection applies to exploration, forecasts, review detail, and scenarios. Overview and coverage show the study network.")
            st.divider()
            st.markdown("**Manhattan study**")
            st.caption("Historical observations · experimental forecasts · explicit scenario assumptions")
        PAGES[page](route)
except DataUnavailable as exc:
    st.title("Data setup required")
    st.error(str(exc))
    st.info("This workspace requires the validated local analysis products. Restore the original bundle or reproduce the pipeline described in documentation/DASHBOARD.md. No sample data is substituted.")
st.divider()
st.caption("RouteRanker · Planning evidence, not automated service instructions · New York local observation dates")
