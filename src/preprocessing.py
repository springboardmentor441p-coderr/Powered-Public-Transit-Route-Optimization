"""Module 4 - Preprocessing: scaling, encoding, train/validation splits."""
import numpy as np, pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import StandardScaler, OneHotEncoder, LabelEncoder
from sklearn.model_selection import train_test_split
from .config import CLASSES, RANDOM_STATE

# Structural + supply-demand features. NO observed ridership/load-factor columns -> no label leakage,
# so the classifier can score routes of unseen cities that have no ridership data.
STRUCT_FEATURES = ["route_length_km", "n_stops", "avg_stop_spacing_km", "trips_per_day", "weekend_ratio",
                   "headway_peak_min", "headway_offpeak_min", "headway_cv", "service_span_hr", "avg_speed_kmph",
                   "trip_duration_min", "frac_stops_shared", "n_hub_stops", "max_overlap", "mean_stop_attr",
                   "sum_attr", "mean_dist_center_km", "demand_potential_day", "proxy_pax_per_trip", "proxy_lf", "proxy_peak_lf", "proxy_avg_lf"]
CAT_FEATURES = ["city_tier"]
# Usage-profile features for clustering (observed/estimated demand behaviour)
USAGE_FEATURES = ["daily_boardings", "avg_lf", "peak_lf", "peak_ratio", "am_share", "pm_share", "midday_share",
                  "trips_per_day", "route_length_km", "frac_stops_shared", "headway_peak_min", "boardings_per_km"]
LOG_COLS = {"daily_boardings", "trips_per_day", "boardings_per_km", "demand_potential_day", "proxy_pax_per_trip"}

def add_encodings(routes):
    """Label-encode categorical identifiers (route id, city, class). IDs are for bookkeeping, not predictors."""
    r = routes.copy()
    r["route_idx"] = LabelEncoder().fit_transform(r.route_uid)
    r["city_idx"] = LabelEncoder().fit_transform(r.city)
    if "label" in r: r["label_idx"] = r.label.map({c: i for i, c in enumerate(CLASSES)})
    return r

def _log(X):
    X = X.copy()
    for c in X.columns:
        if c in LOG_COLS: X[c] = np.log1p(X[c].clip(lower=0))
    return X

def clean_matrix(df, cols):
    X = _log(df[cols].astype(float)); return X.replace([np.inf, -np.inf], np.nan).fillna(X.median())

def make_preprocessor(num, cat=()):
    t = [("num", StandardScaler(), list(num))]
    if cat: t.append(("cat", OneHotEncoder(handle_unknown="ignore"), list(cat)))
    return ColumnTransformer(t)

def class_features(df):
    X = df[STRUCT_FEATURES + CAT_FEATURES].copy()
    num = _log(X[STRUCT_FEATURES].astype(float)).replace([np.inf, -np.inf], np.nan)
    X[STRUCT_FEATURES] = num.fillna(num.median().fillna(0)); return X

def split_train_val(routes, val_size=0.2):
    return train_test_split(routes.index, test_size=val_size, stratify=routes.label, random_state=RANDOM_STATE)
