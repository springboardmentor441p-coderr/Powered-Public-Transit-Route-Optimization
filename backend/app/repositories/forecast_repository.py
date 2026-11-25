"""Read-only repository for canonical Random Forest historical evaluation predictions."""

import copy
import json
import logging
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from app.core.config import settings
from app.core.exceptions import ArtifactUnavailableError

logger = logging.getLogger("ai_routeranker.repositories.forecast")


class ForecastRepository:
    """
    Read-only repository for historical Random Forest validation, test, and August holdout
    prediction artifacts and aggregate evaluation metrics.

    Never loads .joblib model binaries or runs training/inference.
    """

    SUPPORTED_COMBINATIONS = {
        ("tier1", "validation"),
        ("tier1", "test"),
        ("tier1", "august_holdout"),
        ("tier2", "validation"),
        ("tier2", "test"),
    }

    VAL_REQUIRED_COLUMNS = ["route", "date", "daytype", "target_rides", "pred_random_forest"]
    TEST_REQUIRED_COLUMNS = [
        "route",
        "date",
        "daytype",
        "target_rides",
        "rf_tuned_prediction",
        "pred_baseline_b_seasonal_naive",
        "fallback_baseline_b",
    ]
    METRICS_CSV_REQUIRED_COLUMNS = [
        "tier",
        "partition",
        "date_range",
        "rows_evaluated",
        "rf_wape",
        "rf_mae",
        "rf_rmse",
        "rf_r2",
        "baseline_b_wape",
        "baseline_b_mae",
        "baseline_b_rmse",
        "baseline_b_r2",
    ]

    def __init__(
        self,
        tier1_val_path: Optional[Path] = None,
        tier1_test_path: Optional[Path] = None,
        tier1_aug_path: Optional[Path] = None,
        tier2_val_path: Optional[Path] = None,
        tier2_test_path: Optional[Path] = None,
        final_metrics_csv_path: Optional[Path] = None,
        champion_config_path: Optional[Path] = None,
    ) -> None:
        self._paths: Dict[Tuple[str, str], Path] = {
            ("tier1", "validation"): Path(tier1_val_path or settings.RF_TIER1_VAL_PRED_PATH),
            ("tier1", "test"): Path(tier1_test_path or settings.RF_TIER1_TEST_PRED_PATH),
            ("tier1", "august_holdout"): Path(tier1_aug_path or settings.RF_TIER1_AUG_PRED_PATH),
            ("tier2", "validation"): Path(tier2_val_path or settings.RF_TIER2_VAL_PRED_PATH),
            ("tier2", "test"): Path(tier2_test_path or settings.RF_TIER2_TEST_PRED_PATH),
        }
        self._metrics_csv_path = Path(final_metrics_csv_path or settings.RF_FINAL_METRICS_CSV_PATH)
        self._champion_config_path = Path(champion_config_path or settings.RF_CHAMPION_CONFIG_PATH)

        self._lock = threading.Lock()
        self._pred_cache: Dict[Tuple[str, str], pd.DataFrame] = {}
        self._metrics_df: Optional[pd.DataFrame] = None
        self._champion_cfg: Optional[Dict[str, Any]] = None

    def clear_cache(self) -> None:
        """Clear in-memory cached forecast artifacts."""
        with self._lock:
            self._pred_cache.clear()
            self._metrics_df = None
            self._champion_cfg = None

    @staticmethod
    def _freeze_dataframe(df: pd.DataFrame) -> pd.DataFrame:
        for arr in df._mgr.arrays:
            target = arr._ndarray if hasattr(arr, "_ndarray") else arr
            if hasattr(target, "flags"):
                try:
                    target.flags.writeable = False
                except ValueError:
                    pass
        return df

    def get_predictions(self, tier: str, period: str) -> pd.DataFrame:
        """Return cached, deterministically sorted predictions DataFrame for (tier, period)."""
        key = (tier, period)
        if key in self._pred_cache:
            return self._pred_cache[key]

        with self._lock:
            if key in self._pred_cache:
                return self._pred_cache[key]

            path = self._paths[key]
            label = f"{tier}_{period}_predictions"
            required_cols = (
                self.VAL_REQUIRED_COLUMNS if period == "validation" else self.TEST_REQUIRED_COLUMNS
            )

            if not path.exists() or not path.is_file():
                logger.error("Required forecast artifact '%s' is missing.", label)
                raise ArtifactUnavailableError(
                    code="ARTIFACT_MISSING",
                    message=f"Required historical prediction artifact '{label}' is unavailable.",
                )

            try:
                df = pd.read_parquet(path, columns=required_cols)
            except KeyError as exc:
                raise ArtifactUnavailableError(
                    code="ARTIFACT_SCHEMA_INVALID",
                    message=f"Historical prediction artifact '{label}' does not match expected schema.",
                ) from exc
            except Exception as exc:
                logger.error("Failed to read forecast artifact '%s': %s", label, type(exc).__name__)
                raise ArtifactUnavailableError(
                    code="ARTIFACT_CORRUPT",
                    message=f"Historical prediction artifact '{label}' could not be read.",
                ) from exc

            missing = [c for c in required_cols if c not in df.columns]
            if missing:
                raise ArtifactUnavailableError(
                    code="ARTIFACT_SCHEMA_INVALID",
                    message=f"Historical prediction artifact '{label}' is missing required fields.",
                )

            df["route"] = df["route"].astype(str).str.strip()
            df["date"] = pd.to_datetime(df["date"]).dt.date
            df = df.sort_values(by=["date", "route"], ascending=[True, True], kind="mergesort").reset_index(
                drop=True
            )
            self._pred_cache[key] = self._freeze_dataframe(df)
            return self._pred_cache[key]

    def get_final_evaluation_metrics(self) -> pd.DataFrame:
        """Return cached final_model_evaluation_metrics.csv DataFrame."""
        if self._metrics_df is not None:
            return self._metrics_df
        with self._lock:
            if self._metrics_df is not None:
                return self._metrics_df
            if not self._metrics_csv_path.exists() or not self._metrics_csv_path.is_file():
                raise ArtifactUnavailableError(
                    code="ARTIFACT_MISSING",
                    message="Required evaluation metrics artifact 'final_model_evaluation_metrics' is unavailable.",
                )
            try:
                df = pd.read_csv(self._metrics_csv_path, usecols=self.METRICS_CSV_REQUIRED_COLUMNS)
            except Exception as exc:
                logger.error("Failed to read final_model_evaluation_metrics.csv: %s", type(exc).__name__)
                raise ArtifactUnavailableError(
                    code="ARTIFACT_CORRUPT",
                    message="Evaluation metrics artifact 'final_model_evaluation_metrics' could not be read.",
                ) from exc
            self._metrics_df = self._freeze_dataframe(df)
            return self._metrics_df

    def get_champion_config(self) -> Dict[str, Any]:
        """Return deep copy of random_forest_champion_config.json."""
        if self._champion_cfg is not None:
            return copy.deepcopy(self._champion_cfg)
        with self._lock:
            if self._champion_cfg is not None:
                return copy.deepcopy(self._champion_cfg)
            if not self._champion_config_path.exists() or not self._champion_config_path.is_file():
                raise ArtifactUnavailableError(
                    code="ARTIFACT_MISSING",
                    message="Required champion config artifact 'random_forest_champion_config' is unavailable.",
                )
            try:
                with self._champion_config_path.open("r", encoding="utf-8") as f:
                    raw = json.load(f)
            except Exception as exc:
                logger.error("Failed to read champion config JSON: %s", type(exc).__name__)
                raise ArtifactUnavailableError(
                    code="ARTIFACT_CORRUPT",
                    message="Champion config artifact 'random_forest_champion_config' could not be parsed.",
                ) from exc
            if not isinstance(raw, dict) or "tier1_champion" not in raw or "tier2_champion" not in raw:
                raise ArtifactUnavailableError(
                    code="ARTIFACT_SCHEMA_INVALID",
                    message="Champion config artifact 'random_forest_champion_config' has invalid structure.",
                )
            self._champion_cfg = raw
            return copy.deepcopy(self._champion_cfg)
