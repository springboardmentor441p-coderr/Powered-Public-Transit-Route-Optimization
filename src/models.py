"""Module 5/6 - Model selection, training and inference: KMeans, DBSCAN, Random Forest, XGBoost."""
import numpy as np, pandas as pd
from sklearn.cluster import KMeans, DBSCAN
from sklearn.decomposition import PCA
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import silhouette_score, accuracy_score, f1_score, confusion_matrix, classification_report, davies_bouldin_score
from sklearn.model_selection import GroupKFold
from sklearn.neighbors import NearestNeighbors
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.utils.class_weight import compute_sample_weight
from xgboost import XGBClassifier
from .config import *
from .preprocessing import *

# ----------------------------------------------------------------------------- clustering
def fit_clustering(routes, k_range=range(3, 9)):
    X = clean_matrix(routes, USAGE_FEATURES); sc = StandardScaler().fit(X); Z = sc.transform(X)
    scores = {k: silhouette_score(Z, KMeans(k, n_init=10, random_state=RANDOM_STATE).fit_predict(Z)) for k in k_range}
    k = max(scores, key=scores.get)
    km = KMeans(k, n_init=20, random_state=RANDOM_STATE).fit(Z)
    nn = NearestNeighbors(n_neighbors=6).fit(Z); kd = np.sort(nn.kneighbors(Z)[0][:, -1])
    eps = float(np.percentile(kd, 90))
    db = DBSCAN(eps=eps, min_samples=5).fit(Z)
    pca = PCA(2, random_state=RANDOM_STATE).fit(Z)
    d = db.labels_; mask = d != -1
    metrics = dict(k=k, silhouette_by_k={int(a): float(b) for a, b in scores.items()}, kmeans_silhouette=float(scores[k]),
                   kmeans_davies_bouldin=float(davies_bouldin_score(Z, km.labels_)), dbscan_eps=eps,
                   dbscan_clusters=int(len(set(d)) - (1 if -1 in d else 0)), dbscan_noise_frac=float((~mask).mean()),
                   dbscan_silhouette=float(silhouette_score(Z[mask], d[mask])) if len(set(d[mask])) > 1 else None,
                   pca_explained=pca.explained_variance_ratio_.tolist())
    names = name_clusters(routes, km.labels_)
    return dict(scaler=sc, kmeans=km, dbscan=db, pca=pca, names=names, metrics=metrics)

def name_clusters(routes, labels):
    g = routes.assign(_c=labels).groupby("_c")[["avg_lf", "peak_lf", "peak_ratio", "daily_boardings"]].mean()
    med_pr, med_db = routes.peak_ratio.median(), routes.daily_boardings.median(); out = {}
    for c, r in g.iterrows():
        if r.peak_lf >= OVER_PEAK_LF - 0.1: n = "Overcrowded corridor"
        elif r.avg_lf < UNDER_AVG_LF + 0.05: n = "Under-used / low demand"
        elif r.peak_ratio > med_pr * 1.15: n = "Peak-hour commuter"
        elif r.daily_boardings > med_db: n = "High-volume balanced"
        else: n = "Steady local"
        out[int(c)] = f"C{c}: {n}"
    return out

def dbscan_predict(db, Z):
    """Assign new points to the nearest DBSCAN core sample if within eps, else noise (-1)."""
    core = db.components_; lab = db.labels_[db.core_sample_indices_]
    if len(core) == 0: return np.full(len(Z), -1)
    d = ((Z[:, None, :] - core[None]) ** 2).sum(-1) ** 0.5
    return np.where(d.min(1) <= db.eps, lab[d.argmin(1)], -1)

def assign_clusters(art, routes):
    Z = art["scaler"].transform(clean_matrix(routes, USAGE_FEATURES)); P = art["pca"].transform(Z)
    out = routes.copy(); k = art["kmeans"].predict(Z)
    out["kmeans_cluster"] = [art["names"].get(int(c), str(c)) for c in k]
    out["dbscan_cluster"] = dbscan_predict(art["dbscan"], Z); out["is_outlier"] = out.dbscan_cluster == -1
    out["pca1"], out["pca2"] = P[:, 0], P[:, 1]; return out

# --------------------------------------------------------------------------- classification
def _pipe(kind):
    num = STRUCT_FEATURES
    clf = (RandomForestClassifier(400, min_samples_leaf=2, n_jobs=-1, random_state=RANDOM_STATE) if kind == "random_forest"
           else XGBClassifier(n_estimators=300, max_depth=4, learning_rate=0.06, subsample=0.85, colsample_bytree=0.85,
                              objective="multi:softprob", eval_metric="mlogloss", n_jobs=1, random_state=RANDOM_STATE))
    return Pipeline([("prep", make_preprocessor(num, CAT_FEATURES)), ("clf", clf)])

def _fit(pipe, X, y):
    pipe.fit(X, y, clf__sample_weight=compute_sample_weight("balanced", y)); return pipe

def _scores(y, p):
    return dict(accuracy=float(accuracy_score(y, p)), macro_f1=float(f1_score(y, p, average="macro", labels=[0, 1, 2])),
                confusion=confusion_matrix(y, p, labels=[0, 1, 2]).tolist())

def train_classifiers(routes, holdout_cities=()):
    """Compare RF vs XGBoost with (a) city-grouped CV, (b) stratified train/val, (c) unseen-city holdout."""
    r = routes.reset_index(drop=True); X = class_features(r); y = r.label.map({c: i for i, c in enumerate(CLASSES)}).values
    if len(set(y)) < 3: raise ValueError("Need all three classes present to train.")
    res, oof = {}, {}
    folds = min(5, r.city.nunique()); gkf = GroupKFold(folds)
    tr, va = split_train_val(r)
    for kind in ("random_forest", "xgboost"):
        o = np.zeros(len(r), int)
        for a, b in gkf.split(X, y, r.city):
            o[b] = _fit(_pipe(kind), X.iloc[a], y[a]).predict(X.iloc[b])
        oof[kind] = o; m = {"grouped_cv": _scores(y, o)}
        p = _fit(_pipe(kind), X.loc[tr], y[tr]); m["stratified_val"] = _scores(y[va], p.predict(X.loc[va]))
        if len(holdout_cities):
            h = r.city.isin(holdout_cities).values
            m["unseen_cities"] = _scores(y[h], _fit(_pipe(kind), X[~h], y[~h]).predict(X[h]))
            m["unseen_cities"]["cities"] = list(holdout_cities)
        res[kind] = m
    best = max(res, key=lambda k: res[k]["grouped_cv"]["macro_f1"])
    final = _fit(_pipe(best), X, y)
    names = final.named_steps["prep"].get_feature_names_out()
    imp = pd.Series(final.named_steps["clf"].feature_importances_, index=[n.split("__")[-1] for n in names]).sort_values(ascending=False)
    rep = classification_report(y, oof[best], target_names=CLASSES, output_dict=True, zero_division=0)
    return dict(model=final, best=best, metrics=res, importance=imp, oof_pred=pd.Series([CLASSES[i] for i in oof[best]], index=routes.index),
                report=rep)

def predict_routes(art, routes):
    X = class_features(routes); P = art["model"].predict_proba(X)
    out = routes.copy(); out["pred_class"] = [CLASSES[i] for i in P.argmax(1)]
    for i, c in enumerate(CLASSES): out[f"p_{c}"] = P[:, i]
    out["confidence"] = P.max(1); return out
