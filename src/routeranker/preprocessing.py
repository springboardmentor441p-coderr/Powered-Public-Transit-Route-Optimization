"""Module 4 - Data Preprocessing.

* chronological train / validation split (no look-ahead leakage)
* categorical encoding: route-id label + target (historical-profile) encoding,
  one-hot encoding of route type and borough
* scaling (StandardScaler / RobustScaler) for distance-based models
* model-ready matrices for the clustering, classification and forecasting models
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.preprocessing import LabelEncoder, RobustScaler, StandardScaler

from . import config as C

CALENDAR_FEATURES = ["hour", "dow", "month", "is_weekend", "is_holiday", "is_peak", "is_am_peak",
                     "is_pm_peak", "is_night", "is_summer", "hour_sin", "hour_cos", "dow_sin", "dow_cos"]
SERVICE_FEATURES = ["trips", "speed_mph", "length_mi", "n_stops", "stop_density", "reliability",
                    "capacity", "trip_minutes"]
ENCODED_FEATURES = ["te_route_dow_hour", "te_route_daytype_hour", "te_route_hour", "te_route",
                    "te_occ_route_hour", "route_code"]
ROUTE_TYPES = ["Local", "Limited", "Select Bus Service", "Express"]
BOROUGHS = ["Bronx", "Brooklyn", "Manhattan", "Queens", "Staten Island", "Express",
            "Bronx (Express)", "Brooklyn (Express)", "Queens (Express)", "Staten Island (Express)"]
ONEHOT_FEATURES = [f"rt_{t}" for t in ROUTE_TYPES] + [f"boro_{b}" for b in BOROUGHS]
MODEL_FEATURES = CALENDAR_FEATURES + SERVICE_FEATURES + ENCODED_FEATURES + ONEHOT_FEATURES

CLUSTER_FEATURES = ["avg_daily_ridership", "am_peak_share", "pm_peak_share", "night_share", "weekend_ratio",
                    "mean_occupancy", "p90_occupancy", "productivity", "mean_speed_mph", "length_mi",
                    "stop_density", "reliability", "daily_trips", "riders_per_mile", "cv_hourly"]


def time_split(df: pd.DataFrame, valid_days: int = C.VALIDATION_DAYS, date_col: str = "date"):
    """Chronological split: the last ``valid_days`` days form the validation set."""
    cutoff = df[date_col].max() - pd.Timedelta(days=valid_days - 1)
    return df[df[date_col] < cutoff].copy(), df[df[date_col] >= cutoff].copy(), cutoff


@dataclass
class ProfileEncoder:
    """Target (mean) encoder learned on the TRAINING period only.

    Encodes the route id through its historical ridership profile so that the
    forecaster can predict any future date without lag features.
    """
    tables: dict = field(default_factory=dict)
    route_le: LabelEncoder = field(default_factory=LabelEncoder)
    global_mean: float = 0.0
    global_occ: float = 0.0

    def fit(self, train: pd.DataFrame) -> "ProfileEncoder":
        """Learn the profile (mean) encodings from the training period."""
        t = train
        self.global_mean = float(t["log_ridership"].mean())
        self.global_occ = float(t["occupancy"].mean())
        self.tables = {
            "te_route_dow_hour": t[t["is_holiday"] == 0].groupby(["route_id", "dow", "hour"])["log_ridership"].mean(),
            "te_route_daytype_hour": t.groupby(["route_id", "day_type", "hour"])["log_ridership"].mean(),
            "te_route_hour": t.groupby(["route_id", "hour"])["log_ridership"].mean(),
            "te_route": t.groupby("route_id")["log_ridership"].mean(),
            "te_occ_route_hour": t.groupby(["route_id", "day_type", "hour"])["occupancy"].mean(),
        }
        self.route_le.fit(sorted(t["route_id"].unique()))
        return self

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Attach the learned encodings to any frame, with hierarchical fallbacks for unseen keys."""
        df = df.copy()
        keys = {"te_route_dow_hour": ["route_id", "dow", "hour"],
                "te_route_daytype_hour": ["route_id", "day_type", "hour"],
                "te_route_hour": ["route_id", "hour"], "te_route": ["route_id"],
                "te_occ_route_hour": ["route_id", "day_type", "hour"]}
        for name, k in keys.items():
            df = df.drop(columns=[name], errors="ignore").merge(
                self.tables[name].rename(name).reset_index(), on=k, how="left")
        # hierarchical fallback for unseen combinations
        df["te_route_hour"] = df["te_route_hour"].fillna(df["te_route"]).fillna(self.global_mean)
        df["te_route_daytype_hour"] = df["te_route_daytype_hour"].fillna(df["te_route_hour"])
        df["te_route_dow_hour"] = df["te_route_dow_hour"].fillna(df["te_route_daytype_hour"])
        df["te_route"] = df["te_route"].fillna(self.global_mean)
        df["te_occ_route_hour"] = df["te_occ_route_hour"].fillna(self.global_occ)
        known = set(self.route_le.classes_)
        df["route_code"] = [self.route_le.transform([r])[0] if r in known else -1 for r in df["route_id"]] \
            if len(df) < 5000 else _fast_codes(df["route_id"], self.route_le)
        return df


def _fast_codes(s: pd.Series, le: LabelEncoder) -> np.ndarray:
    """Vectorised label-encoding of route ids (unknown -> -1)."""
    mapping = {c: i for i, c in enumerate(le.classes_)}
    return s.map(mapping).fillna(-1).astype(int).to_numpy()


def one_hot(df: pd.DataFrame) -> pd.DataFrame:
    """Fixed-vocabulary one-hot encoding of route type and borough."""
    for t in ROUTE_TYPES:
        df[f"rt_{t}"] = (df["route_type"] == t).astype("int8")
    for b in BOROUGHS:
        df[f"boro_{b}"] = (df["borough"] == b).astype("int8")
    return df


def model_matrix(df: pd.DataFrame, encoder: ProfileEncoder) -> pd.DataFrame:
    """Encode + one-hot; return (encoded frame, numeric feature matrix with fixed column order)."""
    enc = one_hot(encoder.transform(df))
    return enc, enc[MODEL_FEATURES].astype("float32")


def scale_for_clustering(profiles: pd.DataFrame, robust: bool = False):
    """Log-transform skewed volume features, then standardise (z-score)."""
    X = profiles[CLUSTER_FEATURES].copy()
    for c in ("avg_daily_ridership", "productivity", "riders_per_mile", "daily_trips"):
        X[c] = np.log1p(X[c].clip(lower=0))
    scaler = RobustScaler() if robust else StandardScaler()
    Xs = scaler.fit_transform(X.fillna(X.median()))
    return Xs, scaler
