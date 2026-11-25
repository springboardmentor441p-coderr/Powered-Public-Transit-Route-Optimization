"""
AI_RouteRanker - Random Forest Hyperparameter Tuner Module
Milestone 5.2 Phase 3.2: Bounded Hyperparameter Optimization with
Exact Key-Level Alignment, Win32 Memory Safeguards, and Conservative Selection.
"""

from dataclasses import dataclass, asdict, field
from typing import List, Dict, Any, Optional, Tuple
import ctypes
import os
import gc
import time
import json
import logging
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from .config import RandomForestConfig
from .trainer import TrainedRFModel
from analytics.modeling.feature_builder import ModelingDataset

logger = logging.getLogger(__name__)


class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def check_memory_safety(min_avail_mb: float = 600.0, max_load_pct: int = 95) -> Tuple[bool, float, int]:
    """
    Queries Windows GlobalMemoryStatusEx with return code verification.
    Returns (is_safe, avail_mb, load_pct).
    """
    stat = MEMORYSTATUSEX()
    stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    success = ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
    if not success:
        raise RuntimeError("Windows GlobalMemoryStatusEx API call failed to return memory status.")

    avail_mb = round(stat.ullAvailPhys / (1024 * 1024), 2)
    load_pct = int(stat.dwMemoryLoad)
    is_safe = (avail_mb >= min_avail_mb) and (load_pct <= max_load_pct)
    return is_safe, avail_mb, load_pct


@dataclass
class TuningCandidate:
    """Hyperparameter candidate specification."""
    candidate_id: int
    name: str
    n_estimators: int = 100
    max_depth: int = 12
    min_samples_split: int = 2
    min_samples_leaf: int = 5
    max_features: float = 1.0
    bootstrap: bool = True
    random_state: int = 42
    n_jobs: int = 2

    def to_config_dict(self) -> Dict[str, Any]:
        return {
            "n_estimators": self.n_estimators,
            "max_depth": self.max_depth,
            "min_samples_split": self.min_samples_split,
            "min_samples_leaf": self.min_samples_leaf,
            "max_features": self.max_features,
            "bootstrap": self.bootstrap,
            "random_state": self.random_state,
            "n_jobs": self.n_jobs,
            "criterion": "squared_error",
        }


@dataclass
class CandidateResult:
    """Evaluation result and comparative metrics for a single candidate."""
    tier: int
    candidate_id: int
    name: str
    params: Dict[str, Any]
    retrained: bool
    status: str
    training_duration_seconds: float
    pre_fit_avail_ram_mb: float
    pre_fit_ram_load_pct: int
    # Common-row metrics (37,785 for T1; 4,116 for T2)
    common_rows: int
    wape: float
    mae: float
    rmse: float
    r2: float
    # Deltas against Candidate 0
    delta_wape: float
    delta_mae: float
    delta_rmse: float
    delta_r2: float
    # Deterioration flags
    deterioration_mae: bool
    deterioration_rmse: bool
    deterioration_r2: bool
    has_any_secondary_deterioration: bool
    # Additional row metrics (1 row)
    additional_row_key: Optional[str]
    additional_row_actual: Optional[float]
    additional_row_pred: Optional[float]
    additional_row_abs_error: Optional[float]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class RandomForestTuner:
    """
    Executes controlled, bounded hyperparameter optimization for Random Forest.
    Enforces exact key matching, Win32 memory safety, and conservative champion selection.
    """

    CANDIDATES: List[TuningCandidate] = [
        TuningCandidate(
            candidate_id=0,
            name="Candidate 0 (Phase 3.1 Benchmark Anchor)",
            n_estimators=100, max_depth=12, min_samples_split=2, min_samples_leaf=5, max_features=1.0,
        ),
        TuningCandidate(
            candidate_id=1,
            name="Candidate 1 (Feature Decorrelation via 70% Subsampling)",
            n_estimators=100, max_depth=12, min_samples_split=2, min_samples_leaf=5, max_features=0.70,
        ),
        TuningCandidate(
            candidate_id=2,
            name="Candidate 2 (Moderate Subsampling & Split Regularization)",
            n_estimators=100, max_depth=12, min_samples_split=4, min_samples_leaf=5, max_features=0.85,
        ),
        TuningCandidate(
            candidate_id=3,
            name="Candidate 3 (Deeper Trees with Feature Subsampling)",
            n_estimators=100, max_depth=14, min_samples_split=4, min_samples_leaf=5, max_features=0.70,
        ),
        TuningCandidate(
            candidate_id=4,
            name="Candidate 4 (Deeper Trees with Leaf Regularization)",
            n_estimators=100, max_depth=14, min_samples_split=10, min_samples_leaf=8, max_features=0.85,
        ),
        TuningCandidate(
            candidate_id=5,
            name="Candidate 5 (Conservative Tree Depth & Split Smoothing)",
            n_estimators=100, max_depth=10, min_samples_split=10, min_samples_leaf=8, max_features=0.70,
        ),
        TuningCandidate(
            candidate_id=6,
            name="Candidate 6 (Ensemble Expansion - 150 Trees)",
            n_estimators=150, max_depth=12, min_samples_split=4, min_samples_leaf=5, max_features=0.70,
        ),
        TuningCandidate(
            candidate_id=7,
            name="Candidate 7 (Granular Tail Fitting with Feature Subsampling)",
            n_estimators=100, max_depth=12, min_samples_split=4, min_samples_leaf=3, max_features=0.85,
        ),
    ]

    def __init__(
        self,
        tier: int,
        artifacts_dir: str = "artifacts/random_forest",
        baseline_artifacts_dir: str = "artifacts/baselines",
    ):
        self.tier = tier
        self.artifacts_dir = artifacts_dir
        self.baseline_artifacts_dir = baseline_artifacts_dir
        self.additional_key = ("N5", "2025-01-01") if tier == 1 else ("10", "2026-05-20")

    def _load_baseline_valid_keys(self) -> pd.DataFrame:
        """Loads baseline predictions to determine exact common route/date keys."""
        baseline_filename = "tier1_val_predictions.parquet" if self.tier == 1 else "tier2_val_predictions.parquet"
        baseline_path = os.path.join(self.baseline_artifacts_dir, baseline_filename)
        if not os.path.exists(baseline_path):
            raise FileNotFoundError(f"Baseline validation artifact not found at {baseline_path}")

        df_base = pd.read_parquet(baseline_path)
        # Verify no duplicate keys in baseline
        if df_base.duplicated(subset=["route", "date"]).any():
            raise ValueError(f"Baseline artifact contains duplicate (route, date) keys!")

        # Valid Seasonal Naive subset
        df_valid = df_base[~df_base["pred_baseline_b_seasonal_naive"].isna()].copy()
        df_valid["date_str"] = pd.to_datetime(df_valid["date"]).dt.strftime("%Y-%m-%d")
        df_valid["key"] = df_valid["route"].astype(str) + "_" + df_valid["date_str"]
        return df_valid

    def evaluate_predictions(
        self,
        val_df: pd.DataFrame,
        predictions: np.ndarray,
        candidate: TuningCandidate,
        duration: float,
        pre_ram: float,
        pre_load: int,
        c0_result: Optional[CandidateResult] = None,
        retrained: bool = True,
        expected_common_rows: Optional[int] = None,
    ) -> Tuple[CandidateResult, pd.DataFrame]:
        """
        Evaluates predictions strictly on common keys against Baseline B,
        separates additional debut row, and computes metric deltas against Candidate 0.
        """
        eval_table = val_df[["route", "date", "daytype", "target_rides"]].copy()
        eval_table["date_str"] = pd.to_datetime(eval_table["date"]).dt.strftime("%Y-%m-%d")
        eval_table["key"] = eval_table["route"].astype(str) + "_" + eval_table["date_str"]
        eval_table["pred_random_forest"] = np.round(predictions, 2)
        eval_table["residual"] = np.round(eval_table["target_rides"] - eval_table["pred_random_forest"], 2)

        # Check key uniqueness
        if eval_table["key"].duplicated().any():
            raise ValueError("Evaluation table contains duplicate (route, date) keys!")

        # Identify additional row
        add_route, add_date = self.additional_key
        add_mask = (eval_table["route"] == add_route) & (eval_table["date_str"] == add_date)
        add_row = eval_table[add_mask]
        common_table = eval_table[~add_mask].copy()

        # Validate common row count
        expected_common = expected_common_rows if expected_common_rows is not None else (37785 if self.tier == 1 else 4116)
        if len(common_table) != expected_common:
            raise ValueError(f"Expected {expected_common} common keys, found {len(common_table)}!")

        # Calculate common metrics
        y_true = common_table["target_rides"].to_numpy(dtype=np.float64)
        y_pred = common_table["pred_random_forest"].to_numpy(dtype=np.float64)

        mae = round(float(mean_absolute_error(y_true, y_pred)), 4)
        rmse = round(float(np.sqrt(mean_squared_error(y_true, y_pred))), 4)
        r2 = round(float(r2_score(y_true, y_pred)), 4)
        wape = round(float(np.sum(np.abs(y_true - y_pred)) / np.sum(y_true) * 100.0), 4)

        # Additional row extraction
        if len(add_row) == 1:
            add_key_str = f"{add_route}_{add_date}"
            add_actual = float(add_row["target_rides"].values[0])
            add_pred = float(add_row["pred_random_forest"].values[0])
            add_err = round(abs(add_actual - add_pred), 2)
        else:
            add_key_str, add_actual, add_pred, add_err = None, None, None, None

        # Calculate deltas against Candidate 0
        if c0_result is not None:
            delta_wape = round(wape - c0_result.wape, 4)
            delta_mae = round(mae - c0_result.mae, 4)
            delta_rmse = round(rmse - c0_result.rmse, 4)
            delta_r2 = round(r2 - c0_result.r2, 4)
            det_mae = delta_mae > 0.0
            det_rmse = delta_rmse > 0.0
            det_r2 = delta_r2 < 0.0
            has_secondary_det = det_mae or det_rmse or det_r2
        else:
            delta_wape, delta_mae, delta_rmse, delta_r2 = 0.0, 0.0, 0.0, 0.0
            det_mae, det_rmse, det_r2 = False, False, False
            has_secondary_det = False

        res = CandidateResult(
            tier=self.tier,
            candidate_id=candidate.candidate_id,
            name=candidate.name,
            params=candidate.to_config_dict(),
            retrained=retrained,
            status="SUCCESS",
            training_duration_seconds=round(duration, 2),
            pre_fit_avail_ram_mb=pre_ram,
            pre_fit_ram_load_pct=pre_load,
            common_rows=len(common_table),
            wape=wape,
            mae=mae,
            rmse=rmse,
            r2=r2,
            delta_wape=delta_wape,
            delta_mae=delta_mae,
            delta_rmse=delta_rmse,
            delta_r2=delta_r2,
            deterioration_mae=det_mae,
            deterioration_rmse=det_rmse,
            deterioration_r2=det_r2,
            has_any_secondary_deterioration=has_secondary_det,
            additional_row_key=add_key_str,
            additional_row_actual=add_actual,
            additional_row_pred=add_pred,
            additional_row_abs_error=add_err,
        )
        return res, eval_table

    def run_tuning(
        self,
        ds_train: ModelingDataset,
        ds_val: ModelingDataset,
    ) -> Dict[str, Any]:
        """
        Executes bounded tuning across Candidates 0 through 7 for this tier.
        Reuses Candidate 0 from Phase 3.1 without retraining.
        Trains Candidates 1 through 7 sequentially with memory monitoring and abort guards.
        """
        logger.info("--- Starting Tier %d Hyperparameter Tuning (Phase 3.2) ---", self.tier)
        results: List[CandidateResult] = []
        predictions_map: Dict[int, pd.DataFrame] = {}
        fitted_models: Dict[int, RandomForestRegressor] = {}

        # ---------------------------------------------------------------------
        # 1. Candidate 0: Reused from Phase 3.1
        # ---------------------------------------------------------------------
        c0 = self.CANDIDATES[0]
        c0_model_path = os.path.join(self.artifacts_dir, f"tier{self.tier}_random_forest.joblib")
        c0_preds_path = os.path.join(self.artifacts_dir, f"tier{self.tier}_val_predictions.parquet")

        if not os.path.exists(c0_model_path) or not os.path.exists(c0_preds_path):
            raise FileNotFoundError(f"Phase 3.1 artifacts missing for Tier {self.tier}!")

        logger.info("Loading existing Phase 3.1 benchmark as Candidate 0 (Zero retraining)...")
        c0_loaded = TrainedRFModel.load(c0_model_path)
        c0_preds_df = pd.read_parquet(c0_preds_path)
        y_pred_c0 = c0_preds_df["pred_random_forest"].values

        _, pre_ram, pre_load = check_memory_safety(min_avail_mb=0, max_load_pct=100)
        c0_result, c0_eval_table = self.evaluate_predictions(
            val_df=ds_val.metadata.assign(target_rides=ds_val.y.values),
            predictions=y_pred_c0,
            candidate=c0,
            duration=c0_loaded.training_duration_seconds,
            pre_ram=pre_ram,
            pre_load=pre_load,
            c0_result=None,
            retrained=False,
        )
        results.append(c0_result)
        predictions_map[0] = c0_eval_table
        fitted_models[0] = c0_loaded.model

        logger.info(
            "Candidate 0 Benchmark Loaded: WAPE=%.4f%%, MAE=%.2f, RMSE=%.2f, R2=%.4f (Common rows: %d)",
            c0_result.wape, c0_result.mae, c0_result.rmse, c0_result.r2, c0_result.common_rows,
        )

        # ---------------------------------------------------------------------
        # 2. Candidates 1 through 7: Sequential Training
        # ---------------------------------------------------------------------
        X_train_mat = ds_train.X.to_numpy(dtype=np.float32)
        y_train_mat = ds_train.y.to_numpy(dtype=np.float32)
        X_val_mat = ds_val.X.to_numpy(dtype=np.float32)

        aborted = False
        abort_reason = ""

        for candidate in self.CANDIDATES[1:]:
            # Check Win32 Memory Safety
            is_safe, avail_mb, load_pct = check_memory_safety(min_avail_mb=600.0, max_load_pct=95)
            logger.info(
                "Pre-Candidate %d Memory Check: Available=%.1f MB, Load=%d%% (Safe=%s)",
                candidate.candidate_id, avail_mb, load_pct, is_safe,
            )

            if not is_safe:
                abort_reason = (
                    f"Memory abort threshold breached before Candidate {candidate.candidate_id}: "
                    f"Available RAM {avail_mb:.1f} MB (< 600 MB) or Load {load_pct}% (> 95%)."
                )
                logger.warning("ABORT TRIGGERED: %s", abort_reason)
                aborted = True
                break

            logger.info("Training Candidate %d: %s...", candidate.candidate_id, candidate.name)
            cfg = candidate.to_config_dict()
            rf = RandomForestRegressor(
                n_estimators=cfg["n_estimators"],
                max_depth=cfg["max_depth"],
                min_samples_split=cfg["min_samples_split"],
                min_samples_leaf=cfg["min_samples_leaf"],
                max_features=cfg["max_features"],
                bootstrap=cfg["bootstrap"],
                random_state=cfg["random_state"],
                n_jobs=cfg["n_jobs"],
                criterion=cfg["criterion"],
            )

            start_t = time.perf_counter()
            rf.fit(X_train_mat, y_train_mat)
            duration = time.perf_counter() - start_t

            y_pred_cand = rf.predict(X_val_mat)
            cand_result, cand_eval_table = self.evaluate_predictions(
                val_df=ds_val.metadata.assign(target_rides=ds_val.y.values),
                predictions=y_pred_cand,
                candidate=candidate,
                duration=duration,
                pre_ram=avail_mb,
                pre_load=load_pct,
                c0_result=c0_result,
                retrained=True,
            )
            results.append(cand_result)
            predictions_map[candidate.candidate_id] = cand_eval_table
            fitted_models[candidate.candidate_id] = rf

            logger.info(
                "Candidate %d Complete (%.1fs): WAPE=%.4f%% (dWAPE=%+.4f%%), MAE=%.2f, RMSE=%.2f, R2=%.4f | DetMAE=%s, DetRMSE=%s, DetR2=%s",
                candidate.candidate_id, duration, cand_result.wape, cand_result.delta_wape,
                cand_result.mae, cand_result.rmse, cand_result.r2,
                cand_result.deterioration_mae, cand_result.deterioration_rmse, cand_result.deterioration_r2,
            )

            # Clean up memory
            gc.collect()

        del X_train_mat, y_train_mat, X_val_mat
        gc.collect()

        # ---------------------------------------------------------------------
        # 3. Champion Selection Logic
        # ---------------------------------------------------------------------
        # Find candidate with lowest common-row WAPE
        best_wape_candidate = min(results, key=lambda r: r.wape)
        logger.info(
            "Lowest Common-Row WAPE Candidate: Candidate %d (%s) with WAPE=%.4f%%",
            best_wape_candidate.candidate_id, best_wape_candidate.name, best_wape_candidate.wape,
        )

        champion_candidate_id: int
        selection_rationale: str
        has_material_tradeoff: bool = False

        if best_wape_candidate.candidate_id == 0:
            champion_candidate_id = 0
            selection_rationale = "Candidate 0 retained as champion: No tuned candidate achieved a lower common-row WAPE."
        elif not best_wape_candidate.has_any_secondary_deterioration:
            # Strict superiority: lower WAPE with zero secondary deterioration
            champion_candidate_id = best_wape_candidate.candidate_id
            selection_rationale = (
                f"Candidate {best_wape_candidate.candidate_id} selected as champion: "
                f"Achieved lower WAPE ({best_wape_candidate.wape:.4f}% vs {c0_result.wape:.4f}%) "
                f"with zero secondary metric deterioration (dMAE={best_wape_candidate.delta_mae:+.2f}, "
                f"dRMSE={best_wape_candidate.delta_rmse:+.2f}, dR2={best_wape_candidate.delta_r2:+.4f})."
            )
        else:
            # Material trade-off: lower WAPE but at least one secondary metric deteriorated!
            # Safeguard: Retain Candidate 0 as default champion pending explicit user approval!
            has_material_tradeoff = True
            champion_candidate_id = 0
            selection_rationale = (
                f"Candidate 0 retained as default champion pending explicit user review: "
                f"Candidate {best_wape_candidate.candidate_id} achieved lower WAPE ({best_wape_candidate.wape:.4f}% vs {c0_result.wape:.4f}%), "
                f"but has secondary metric deterioration: "
                f"dMAE={best_wape_candidate.delta_mae:+.2f} ({best_wape_candidate.deterioration_mae}), "
                f"dRMSE={best_wape_candidate.delta_rmse:+.2f} ({best_wape_candidate.deterioration_rmse}), "
                f"dR2={best_wape_candidate.delta_r2:+.4f} ({best_wape_candidate.deterioration_r2})."
            )

        logger.info("Champion Decision: %s", selection_rationale)

        # ---------------------------------------------------------------------
        # 4. Save Champion Artifacts
        # ---------------------------------------------------------------------
        champion_model = fitted_models[champion_candidate_id]
        champion_result = next(r for r in results if r.candidate_id == champion_candidate_id)
        champion_preds = predictions_map[champion_candidate_id]

        # Save Tuned Champion Model (.joblib)
        tuned_model_path = os.path.join(self.artifacts_dir, f"tier{self.tier}_random_forest_tuned.joblib")
        joblib.dump(
            {
                "model": champion_model,
                "tier": self.tier,
                "champion_candidate_id": champion_candidate_id,
                "feature_names": ds_train.feature_names,
                "config": champion_result.params,
                "training_rows": len(ds_train.X),
                "feature_count": ds_train.X.shape[1],
                "selection_rationale": selection_rationale,
                "has_material_tradeoff": has_material_tradeoff,
                "metrics": champion_result.to_dict(),
            },
            tuned_model_path,
            compress=3,
        )
        logger.info("Saved Tier %d tuned champion model artifact to %s", self.tier, tuned_model_path)

        # Save Tuned Champion Predictions (.parquet)
        tuned_preds_path = os.path.join(self.artifacts_dir, f"tier{self.tier}_val_predictions_tuned.parquet")
        champion_preds.drop(columns=["key", "date_str"], errors="ignore").to_parquet(
            tuned_preds_path, index=False, compression="zstd"
        )
        logger.info("Saved Tier %d tuned validation predictions to %s", self.tier, tuned_preds_path)

        return {
            "tier": self.tier,
            "aborted": aborted,
            "abort_reason": abort_reason,
            "candidate_results": [r.to_dict() for r in results],
            "champion_candidate_id": champion_candidate_id,
            "champion_result": champion_result.to_dict(),
            "selection_rationale": selection_rationale,
            "has_material_tradeoff": has_material_tradeoff,
            "best_wape_candidate_id": best_wape_candidate.candidate_id,
            "best_wape_result": best_wape_candidate.to_dict(),
        }
