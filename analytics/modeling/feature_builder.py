"""
AI_RouteRanker - Feature Matrix Builder Module
Builds strictly causal, leakage-free feature matrices for Tier 1 and Tier 2 models.
Implements:
- Explicit target exclusion list (target_rides, rides_per_scheduled_trip).
- Preserves raw source Parquet NULLs and genuine zeros.
- Derives GTFS status indicators: gtfs_is_matched, gtfs_is_zero_service, gtfs_is_unmatched.
- Computes lagged demand-service interaction via approved Definition B (rides_lag_7 / scheduled_trips_count).
- Employs documented downstream matrix placeholders (-1.0) strictly where required by estimators.
"""

from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple, Any
import logging
import numpy as np
import pandas as pd

from analytics.modeling.encoders import RouteEncoder, DaytypeEncoder

logger = logging.getLogger(__name__)


@dataclass
class ModelingDataset:
    """Container for processed modeling dataset with separated target and metadata."""
    X: pd.DataFrame
    y: pd.Series
    metadata: pd.DataFrame
    feature_names: List[str]
    tier: int
    partition_name: str

    def summary(self) -> Dict[str, Any]:
        return {
            "tier": self.tier,
            "partition": self.partition_name,
            "row_count": len(self.X),
            "feature_count": self.X.shape[1],
            "feature_names": self.feature_names,
            "metadata_columns": list(self.metadata.columns),
            "target_name": self.y.name,
        }


class FeatureMatrixBuilder:
    """Transforms raw partitioned DataFrames into model-ready predictor matrices."""

    # Explicit Target & Leakage Exclusion List
    TARGET_EXCLUSIONS: List[str] = [
        "target_rides",              # Target variable (ground truth y)
        "rides_per_scheduled_trip",  # Contemporaneous demand KPI (y_t / scheduled_trips) -> LEAKAGE
    ]

    # Non-predictor metadata columns
    METADATA_COLUMNS: List[str] = [
        "route",
        "date",
        "daytype",
        "snapshot_id",
        "schedule_coverage_status",
    ]

    # Tier 1 Predictor Groups (30 core dense predictors)
    T1_TEMPORAL_FEATURES: List[str] = [
        "year",
        "month",
        "quarter",
        "day",
        "day_of_week_int",
        "day_of_year",
        "week_of_year",
        "is_weekend",
        "is_month_start",
        "is_month_end",
    ]

    T1_HISTORICAL_FEATURES: List[str] = [
        "historical_mean_rides",
        "historical_std_rides",
        "historical_max_rides",
        "historical_min_rides",
        "route_observation_count",
    ]

    T1_LAG_FEATURES: List[str] = [
        "rides_lag_1",
        "rides_lag_7",
        "rides_lag_14",
        "rides_lag_28",
    ]

    T1_ROLLING_FEATURES: List[str] = [
        "rolling_mean_7",
        "rolling_std_7",
        "rolling_mean_14",
        "rolling_std_14",
        "rolling_mean_28",
        "rolling_std_28",
    ]

    T1_DYNAMIC_DEMAND_FEATURES: List[str] = [
        "ridership_daytype_average",
        "route_relative_demand",
    ]

    # Tier 2 GTFS Supply Features (8 numeric / boolean)
    T2_GTFS_SUPPLY_FEATURES: List[str] = [
        "scheduled_trips_count",
        "scheduled_stop_visits",
        "service_span_seconds",
        "service_span_hours",
        "first_departure_seconds",
        "last_departure_seconds",
        "service_active",
        "scheduled_trips_per_service_hour",
    ]

    # Downstream matrix placeholder for undefined ratios and unobserved GTFS metrics
    PLACEHOLDER_UNDEFINED: float = -1.0

    def __init__(
        self,
        route_encoder: Optional[RouteEncoder] = None,
        daytype_encoder: Optional[DaytypeEncoder] = None,
    ):
        self.route_encoder = route_encoder or RouteEncoder()
        self.daytype_encoder = daytype_encoder or DaytypeEncoder()
        self.is_fitted = False

    def fit_encoders(self, train_df: pd.DataFrame) -> "FeatureMatrixBuilder":
        """Fits Route and Daytype encoders strictly on the training partition."""
        logger.info("Fitting RouteEncoder on %d training rows...", len(train_df))
        self.route_encoder.fit(train_df["route"])
        logger.info("Fitted Route vocabulary: %d distinct routes", len(self.route_encoder.vocabulary_))

        logger.info("Fitting DaytypeEncoder on training daytypes...")
        self.daytype_encoder.fit(train_df["daytype"])
        self.is_fitted = True
        return self

    def _extract_tier1_core(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extracts the 30 core dense predictors for Tier 1."""
        core_cols = (
            self.T1_TEMPORAL_FEATURES
            + self.T1_HISTORICAL_FEATURES
            + self.T1_LAG_FEATURES
            + self.T1_ROLLING_FEATURES
            + self.T1_DYNAMIC_DEMAND_FEATURES
        )
        core_df = df[core_cols].copy()

        # Cast boolean columns to float32
        for col in ["is_weekend", "is_month_start", "is_month_end"]:
            if col in core_df.columns:
                core_df[col] = core_df[col].astype(np.float32)

        # Impute rare debut-row NaNs (e.g. brand new route row 0) with 0.0 placeholder in matrix
        core_df = core_df.fillna(0.0)

        # One-hot encode daytype (3 columns: daytype_W, daytype_A, daytype_U)
        daytype_ohe = self.daytype_encoder.transform(df["daytype"])
        core_df = pd.concat([core_df, daytype_ohe], axis=1)

        return core_df

    def build_tier1_dataset(
        self,
        df: pd.DataFrame,
        partition_name: str = "train",
        include_route_ohe: bool = True,
    ) -> ModelingDataset:
        """
        Builds the Tier 1 predictor matrix (Post-Pandemic Macro Model).
        Features: 30 core dense predictors + optional route one-hot indicators.
        Excludes: target_rides, rides_per_scheduled_trip, and all GTFS features.
        """
        if not self.is_fitted:
            raise RuntimeError("FeatureMatrixBuilder must be fitted on training data before building datasets!")

        # 1. Target and Metadata
        y = df["target_rides"].copy().astype(np.float32)
        meta_cols = [c for c in self.METADATA_COLUMNS if c in df.columns]
        metadata = df[meta_cols].copy()

        # 2. Extract 30 core dense predictors
        X_core = self._extract_tier1_core(df)

        # 3. Route One-Hot Encoding
        if include_route_ohe:
            X_routes = self.route_encoder.transform(df["route"])
            X = pd.concat([X_core, X_routes], axis=1)
        else:
            X = X_core

        # Verify no target leakage in X
        for leak in self.TARGET_EXCLUSIONS:
            assert leak not in X.columns, f"Target leakage detected in Tier 1 feature matrix: {leak}"

        return ModelingDataset(
            X=X,
            y=y,
            metadata=metadata,
            feature_names=list(X.columns),
            tier=1,
            partition_name=partition_name,
        )

    def build_tier2_dataset(
        self,
        df: pd.DataFrame,
        partition_name: str = "train",
        include_route_ohe: bool = True,
    ) -> ModelingDataset:
        """
        Builds the Tier 2 predictor matrix (Contemporary Supply-Informed Model).
        Features: 30 core Tier 1 predictors + 8 GTFS supply features + 3 status indicators
                  + 1 lagged demand-service interaction + optional route one-hot indicators.
        Preserves original Parquet NULLs on disk while applying documented -1.0 matrix placeholders.
        """
        if not self.is_fitted:
            raise RuntimeError("FeatureMatrixBuilder must be fitted on training data before building datasets!")

        # 1. Target and Metadata
        y = df["target_rides"].copy().astype(np.float32)
        meta_cols = [c for c in self.METADATA_COLUMNS if c in df.columns]
        metadata = df[meta_cols].copy()

        # 2. Extract 30 core Tier 1 predictors
        X_core = self._extract_tier1_core(df)

        # 3. Derive GTFS Operational Status Indicators
        # Distinctly partitions:
        # - Condition 1: Matched positive service (gtfs_is_matched=1, gtfs_is_zero_service=0, gtfs_is_unmatched=0)
        # - Condition 2: Matched zero scheduled trips (gtfs_is_matched=1, gtfs_is_zero_service=1, gtfs_is_unmatched=0)
        # - Condition 3: Unmatched route (gtfs_is_matched=0, gtfs_is_zero_service=0, gtfs_is_unmatched=1)
        coverage_status = df["schedule_coverage_status"].astype(str)

        gtfs_is_matched = (
            coverage_status.isin(["matched", "zero_scheduled_trips"])
        ).astype(np.float32)

        gtfs_is_zero_service = (
            coverage_status == "zero_scheduled_trips"
        ).astype(np.float32)

        gtfs_is_unmatched = (
            coverage_status == "unmatched_route"
        ).astype(np.float32)

        gtfs_indicators = pd.DataFrame(
            {
                "gtfs_is_matched": gtfs_is_matched,
                "gtfs_is_zero_service": gtfs_is_zero_service,
                "gtfs_is_unmatched": gtfs_is_unmatched,
            },
            index=df.index,
        )

        # 4. Lagged Demand-Service Interaction (Definition B: rides_lag_7 / scheduled_trips_count)
        # Combines historical demand (7 previous observation rows) with current scheduled supply.
        # Zero target-date ridership is used.
        # Condition 1: genuine positive ratio
        # Condition 2 & 3: documented matrix placeholder (-1.0), distinct from valid ratios (0.01 to 142.0).
        trips = df["scheduled_trips_count"].fillna(0)
        lags_7 = df["rides_lag_7"].fillna(0)

        is_positive_matched = (coverage_status == "matched") & (trips > 0)
        ratio_values = np.where(
            is_positive_matched,
            lags_7 / trips,
            self.PLACEHOLDER_UNDEFINED,  # Documented placeholder -1.0
        )
        interaction_df = pd.DataFrame(
            {"ridership_per_trip_lag7": ratio_values.astype(np.float32)},
            index=df.index,
        )

        # 5. GTFS Supply Features (8 predictors) with Downstream Placeholder Handling
        gtfs_supply = df[self.T2_GTFS_SUPPLY_FEATURES].copy()

        # Genuine zero columns: scheduled_trips_count, scheduled_stop_visits, service_active
        # For zero_scheduled_trips, genuine zero is strictly preserved.
        # For unmatched routes, filled with placeholder -1.0 in matrix.
        is_unmatched_mask = (coverage_status == "unmatched_route")

        gtfs_supply["service_active"] = gtfs_supply["service_active"].astype(float).fillna(0.0)
        gtfs_supply.loc[is_unmatched_mask, "service_active"] = self.PLACEHOLDER_UNDEFINED

        gtfs_supply["scheduled_trips_count"] = gtfs_supply["scheduled_trips_count"].astype(float)
        gtfs_supply.loc[is_unmatched_mask, "scheduled_trips_count"] = self.PLACEHOLDER_UNDEFINED

        gtfs_supply["scheduled_stop_visits"] = gtfs_supply["scheduled_stop_visits"].astype(float)
        gtfs_supply.loc[is_unmatched_mask, "scheduled_stop_visits"] = self.PLACEHOLDER_UNDEFINED

        # Columns that are naturally NULL for both zero-service and unmatched routes
        # (service_span_seconds, service_span_hours, departure times, frequency)
        # Filled with documented -1.0 placeholder in downstream matrix only.
        for col in [
            "service_span_seconds",
            "service_span_hours",
            "first_departure_seconds",
            "last_departure_seconds",
            "scheduled_trips_per_service_hour",
        ]:
            gtfs_supply[col] = gtfs_supply[col].fillna(self.PLACEHOLDER_UNDEFINED).astype(np.float32)

        # 6. Combine Core (30) + GTFS Supply (8) + Status Indicators (3) + Interaction (1) = 42 Predictors
        X_tier2_dense = pd.concat([X_core, gtfs_supply, gtfs_indicators, interaction_df], axis=1)

        # 7. Route One-Hot Encoding
        if include_route_ohe:
            X_routes = self.route_encoder.transform(df["route"])
            X = pd.concat([X_tier2_dense, X_routes], axis=1)
        else:
            X = X_tier2_dense

        # Verify no target leakage in X
        for leak in self.TARGET_EXCLUSIONS:
            assert leak not in X.columns, f"Target leakage detected in Tier 2 feature matrix: {leak}"

        return ModelingDataset(
            X=X,
            y=y,
            metadata=metadata,
            feature_names=list(X.columns),
            tier=2,
            partition_name=partition_name,
        )
