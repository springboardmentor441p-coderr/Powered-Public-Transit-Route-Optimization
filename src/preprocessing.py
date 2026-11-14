"""
Module 4: Data Preprocessing
Normalize, scale, encode, and split data for model training.
"""
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.model_selection import train_test_split
import joblib
import os


# Features used for ML models
FEATURE_COLS = [
    'trip_count', 'unique_stops', 'avg_stops_per_trip', 'route_length_km',
    'operating_hours', 'peak_hour_trips', 'off_peak_trips', 'peak_ratio',
    'avg_trip_duration_min', 'stop_frequency', 'direction_count',
    'weekday_service', 'weekend_service'
]


def create_performance_labels(profiles: pd.DataFrame) -> pd.DataFrame:
    """
    Create performance labels for classification:
    - 'underutilized': Low trip count, low stop frequency
    - 'balanced': Normal operation
    - 'overcrowded': High trip count, high peak ratio

    Uses percentile-based thresholds.
    """
    df = profiles.copy()

    # Compute a composite efficiency score
    # Higher score = more potential for overcrowding / imbalance
    df['efficiency_score'] = (
        df['trip_count'].rank(pct=True) * 0.3 +
        df['stop_frequency'].rank(pct=True) * 0.2 +
        df['peak_ratio'].rank(pct=True) * 0.3 +
        (1 - df['route_length_km'].rank(pct=True)) * 0.1 +
        (1 - df['unique_stops'].rank(pct=True)) * 0.1
    )

    # Assign labels based on percentiles
    q_low = df['efficiency_score'].quantile(0.33)
    q_high = df['efficiency_score'].quantile(0.66)

    conditions = [
        df['efficiency_score'] <= q_low,
        (df['efficiency_score'] > q_low) & (df['efficiency_score'] <= q_high),
        df['efficiency_score'] > q_high
    ]
    labels = ['underutilized', 'balanced', 'overcrowded']
    df['performance_label'] = np.select(conditions, labels, default='balanced')

    print(f"✅ Performance labels created:")
    print(f"   {df['performance_label'].value_counts().to_dict()}")

    return df


def preprocess_for_clustering(profiles: pd.DataFrame, model_dir: str) -> tuple:
    """
    Prepare data for clustering: scale numeric features.

    Returns
    -------
    tuple: (scaled_features ndarray, scaler object, feature DataFrame)
    """
    df = profiles[FEATURE_COLS].copy()

    # Fill any remaining NaNs with 0
    df = df.fillna(0)

    # Replace infinities
    df = df.replace([np.inf, -np.inf], 0)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(df)

    # Save scaler
    os.makedirs(model_dir, exist_ok=True)
    joblib.dump(scaler, os.path.join(model_dir, 'scaler.pkl'))
    print(f"✅ Scaler saved. Feature matrix shape: {X_scaled.shape}")

    return X_scaled, scaler, df


def preprocess_for_classification(profiles: pd.DataFrame, model_dir: str) -> tuple:
    """
    Prepare data for classification: encode labels, scale features, split train/test.

    Returns
    -------
    tuple: (X_train, X_test, y_train, y_test, label_encoder, feature_names)
    """
    df = profiles.copy()

    # Features
    X = df[FEATURE_COLS].fillna(0).replace([np.inf, -np.inf], 0)

    # Target
    le = LabelEncoder()
    y = le.fit_transform(df['performance_label'])

    # Scale
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Split
    X_train, X_test, y_train, y_test = train_test_split(
        X_scaled, y, test_size=0.2, random_state=42, stratify=y
    )

    # Save
    os.makedirs(model_dir, exist_ok=True)
    joblib.dump(le, os.path.join(model_dir, 'label_encoder.pkl'))
    joblib.dump(scaler, os.path.join(model_dir, 'classifier_scaler.pkl'))

    print(f"✅ Classification data prepared:")
    print(f"   Train: {X_train.shape}, Test: {X_test.shape}")
    print(f"   Classes: {dict(zip(le.classes_, range(len(le.classes_))))}")

    return X_train, X_test, y_train, y_test, le, FEATURE_COLS


if __name__ == "__main__":
    from data_collection import load_gtfs_data
    from feature_engineering import clean_data, build_route_profiles

    GTFS_DIR = os.path.join(os.path.dirname(__file__), '..', 'gtfs')
    MODEL_DIR = os.path.join(os.path.dirname(__file__), '..', 'models')

    data = load_gtfs_data(GTFS_DIR)
    data = clean_data(data)
    profiles = build_route_profiles(data)
    profiles = create_performance_labels(profiles)

    X_scaled, scaler, feat_df = preprocess_for_clustering(profiles, MODEL_DIR)
    X_train, X_test, y_train, y_test, le, fnames = preprocess_for_classification(profiles, MODEL_DIR)
