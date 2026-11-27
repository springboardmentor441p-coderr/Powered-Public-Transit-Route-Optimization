import pandas as pd
import plotly.express as px
import streamlit as st

from common import ROOT, require_service, setup_page

setup_page("Pipeline & Architecture", "How RouteRanker is built - from raw open data to the dashboard and API.", "🧭")
svc = require_service()
figs = svc.metrics["figures"]

st.subheader("System architecture")
st.image(str(ROOT / figs["architecture"]), width="stretch")
st.markdown("""
**Architecture style:** layered *modular monolith* with a shared service layer and two presentation channels.

| Layer | Component | Responsibility |
|---|---|---|
| Data | `data_collection.py` | SODA/SoQL pulls, server-side aggregation, monthly parquet cache, incremental refresh |
| Processing | `cleaning.py`, `feature_engineering.py`, `eda.py`, `preprocessing.py` | cleaning, KPIs, EDA, encoding, scaling, time split |
| ML | `clustering.py`, `supervised.py` | KMeans, DBSCAN, Random Forest, XGBoost (classifier + regressor) |
| Service | `inference.py`, `optimization.py`, `gtfs.py` | prediction, ranking, explanation, validation, optimisation, simulation, GTFS analysis |
| Presentation | `streamlit_app.py` + `app/views/*` · `api/main.py` | Streamlit dashboard · FastAPI REST API |
""")
st.subheader("ML pipeline")
st.image(str(ROOT / figs["pipeline"]), width="stretch")
st.subheader("Last pipeline run")
t = pd.Series(svc.manifest["stage_seconds"]).reset_index()
t.columns = ["stage", "seconds"]
st.plotly_chart(px.bar(t, x="seconds", y="stage", orientation="h", title=f"Stage timings "
                       f"(total {svc.manifest['total_seconds'] / 60:.1f} min, built {svc.manifest['built_at_ist']})")
                .update_layout(yaxis=dict(autorange="reversed")), width="stretch")
st.subheader("Model figures")
for k in ("k_selection", "clusters_pca", "confusion", "importance"):
    if k in figs:
        st.image(str(ROOT / figs[k]), width="stretch")
