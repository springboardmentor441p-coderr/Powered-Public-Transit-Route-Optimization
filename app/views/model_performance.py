import pandas as pd
import plotly.express as px
import streamlit as st

from common import ROOT, require_service, setup_page
from routeranker import config as C

setup_page("Model Performance", "Clustering (KMeans, DBSCAN), classification (Random Forest vs XGBoost) and "
                                "forecasting (XGBoost vs Random Forest vs baseline).", "🤖")
svc = require_service()
M = svc.metrics
ri = svc.route_info

t1, t2, t3 = st.tabs(["🧩 Clustering", "🏷️ Classification", "📉 Forecasting"])
with t1:
    km, db = M["clustering"]["kmeans"], M["clustering"]["dbscan"]
    k = st.columns(5)
    k[0].metric("KMeans k", km["k"]); k[1].metric("Silhouette", f"{km['silhouette']:.3f}")
    k[2].metric("Davies-Bouldin", f"{km['davies_bouldin']:.3f}")
    k[3].metric("DBSCAN clusters", db["n_clusters"]); k[4].metric("DBSCAN outlier routes", db["n_outliers"])
    ks = pd.DataFrame(M["clustering"]["k_selection"])
    c1, c2 = st.columns(2)
    c1.plotly_chart(px.line(ks, x="k", y=["silhouette"], markers=True, title="Silhouette vs k"), width="stretch")
    c2.plotly_chart(px.line(ks, x="k", y="inertia", markers=True, title="Elbow - inertia vs k"), width="stretch")
    st.plotly_chart(px.scatter(ri, x="pc1", y="pc2", color="cluster_name", symbol=ri["dbscan_outlier"].map({0: "core", 1: "DBSCAN outlier"}),
                               hover_name="route_id", size="avg_daily_ridership", height=520,
                               title="Route segments in PCA space (symbol = DBSCAN outlier)"), width="stretch")
    prof = ri.groupby("cluster_name")[["avg_daily_ridership", "productivity", "mean_occupancy", "mean_speed_mph",
                                       "am_peak_share", "weekend_ratio", "length_mi", "reliability"]].median()
    st.dataframe(prof.style.background_gradient(axis=0, cmap="Blues"), width="stretch")
    st.markdown("**DBSCAN outliers (atypical routes)**: " + ", ".join(ri.loc[ri["dbscan_outlier"] == 1, "route_id"]))
with t2:
    cl = M["classification"]
    st.success(f"Selected model: **{cl['best']}** (highest macro-F1 on the {C.VALIDATION_DAYS}-day hold-out).")
    rows = [{"model": m, "accuracy": cl[m]["accuracy"], "balanced_accuracy": cl[m]["balanced_accuracy"],
             "f1_macro": cl[m]["f1_macro"], "f1_weighted": cl[m]["f1_weighted"], "train_rows": cl[m]["train_rows"],
             "train_seconds": cl[m]["train_seconds"]} for m in ("RandomForest", "XGBoost")]
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    c1, c2 = st.columns(2)
    for c, m in zip((c1, c2), ("RandomForest", "XGBoost")):
        cm = pd.DataFrame(cl[m]["confusion_matrix"], index=C.CLASS_LABELS, columns=C.CLASS_LABELS)
        c.plotly_chart(px.imshow(cm.div(cm.sum(axis=1), axis=0), text_auto=".2f", color_continuous_scale="Blues",
                                 title=f"{m} - normalised confusion matrix", labels=dict(x="Predicted", y="Actual")),
                       width="stretch")
        c.dataframe(pd.DataFrame(cl[m]["report"]).T.round(3), width="stretch")
    imp = pd.Series(cl["feature_importance"][cl["best"]]).head(20).reset_index()
    imp.columns = ["feature", "importance"]
    st.plotly_chart(px.bar(imp, x="importance", y="feature", orientation="h", title="Feature importance")
                    .update_layout(yaxis=dict(autorange="reversed"), height=520), width="stretch")
with t3:
    fc = M["forecasting"]
    st.success(f"Selected model: **{fc['best']}** (lowest MAE on the hold-out).")
    rows = [{"model": m, **{k: fc[m][k] for k in ("mae", "rmse", "r2", "wape")}}
            for m in ("SeasonalProfileBaseline", "RandomForest", "XGBoost")]
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    vp = pd.read_parquet(C.PROCESSED_DIR / "validation_predictions.parquet")
    rid = st.selectbox("Route", sorted(vp["route_id"].unique()), format_func=svc.route_label)
    r = vp[vp["route_id"] == rid]
    st.plotly_chart(px.line(r, x="ts", y=["ridership", "pred"], title=f"{rid}: validation actual vs forecast"),
                    width="stretch")
    net = vp.groupby("ts")[["ridership", "pred"]].sum().reset_index()
    st.plotly_chart(px.line(net, x="ts", y=["ridership", "pred"], title="Network: validation actual vs forecast"),
                    width="stretch")
    imp = pd.Series(fc["feature_importance"][fc["best"]]).head(20).reset_index()
    imp.columns = ["feature", "importance"]
    st.plotly_chart(px.bar(imp, x="importance", y="feature", orientation="h", title="Forecaster feature importance")
                    .update_layout(yaxis=dict(autorange="reversed"), height=520), width="stretch")
    for f in ("forecast_fit", "forecast_comparison"):
        if f in M["figures"]:
            st.image(str(ROOT / M["figures"][f]), width="stretch")
