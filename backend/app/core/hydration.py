"""Secure startup hydration of private runtime data from a Hugging Face Dataset."""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from huggingface_hub import hf_hub_download

from app.core.config import Settings

logger = logging.getLogger("ai_routeranker.hydration")


@dataclass(frozen=True)
class RuntimeArtifactSpec:
    """Expected remote dataset entry with size and SHA-256 integrity digest."""

    repo_rel_path: str
    size_bytes: int
    sha256: str
    target_resolver: Callable[[Settings], Path]


def _resolve_duckdb(s: Settings) -> Path:
    return s.DUCKDB_PATH


def _resolve_artifact(subpath: str) -> Callable[[Settings], Path]:
    return lambda s: s.ARTIFACTS_DIR / subpath


# Verified manifest for the 20 external runtime files (derived DuckDB + 19 artifacts).
# The 2 files under reports/modeling/random_forest/ are tracked in Git.
REMOTE_RUNTIME_MANIFEST: Tuple[RuntimeArtifactSpec, ...] = (
    RuntimeArtifactSpec(
        "data/processed/ai_routeranker.duckdb",
        5255168,
        "23ad4d8fdff52eb52293b52c3edbce19b8a344f0e18a2b588867f71d5d624ee9",
        _resolve_duckdb,
    ),
    RuntimeArtifactSpec(
        "artifacts/ranking_features/route_ranker_feature_master.parquet",
        62921,
        "c26aa49a408b1d07c6a0e09f2b11879cf623a54da1c3625f1342b51d8937df85",
        _resolve_artifact("ranking_features/route_ranker_feature_master.parquet"),
    ),
    RuntimeArtifactSpec(
        "artifacts/ranking_results/route_rankings_master.parquet",
        103565,
        "c440671d0b3888683969cb5fc11ccf7b581128a7296069019f76202b64f0093b",
        _resolve_artifact("ranking_results/route_rankings_master.parquet"),
    ),
    RuntimeArtifactSpec(
        "artifacts/ranking_results/route_ranking_explanations.json",
        797352,
        "56c29ef9c77b7517e8cb621a207600aa576148aef015a35a364da029a74a24b2",
        _resolve_artifact("ranking_results/route_ranking_explanations.json"),
    ),
    RuntimeArtifactSpec(
        "artifacts/ranking_results/ranking_sensitivity_analysis.parquet",
        7522,
        "fb41bcdf1e18da7978ae1666535d5868a92467143bd3d08b7ee5d71ef5d6790c",
        _resolve_artifact("ranking_results/ranking_sensitivity_analysis.parquet"),
    ),
    RuntimeArtifactSpec(
        "artifacts/clustering/transit_hub_rankings.parquet",
        508646,
        "20e116891376696370c38c2dd919d8d59c95b981fb493270b29763adb2260aa7",
        _resolve_artifact("clustering/transit_hub_rankings.parquet"),
    ),
    RuntimeArtifactSpec(
        "artifacts/clustering/spatial_dbscan_assignments.parquet",
        571207,
        "3c7d40bcca545e142a69afd8b084166a372069a3f645360f76812fcdf9bab674",
        _resolve_artifact("clustering/spatial_dbscan_assignments.parquet"),
    ),
    RuntimeArtifactSpec(
        "artifacts/clustering/phase6_1_stage2_metadata.json",
        2786,
        "4b4cd002a309538c0fe03eb7bd5e924cba5f00632198b57f15878085eb42f67f",
        _resolve_artifact("clustering/phase6_1_stage2_metadata.json"),
    ),
    RuntimeArtifactSpec(
        "artifacts/clustering/top100_hubs_config_a.csv",
        9447,
        "201682c6587678e2ef05fb6635e7ac7f16c1a2ed8c0f7d08aaf17671a9d1bc03",
        _resolve_artifact("clustering/top100_hubs_config_a.csv"),
    ),
    RuntimeArtifactSpec(
        "artifacts/route_clustering/corridor_cluster_assignments.parquet",
        21471,
        "7cd435ab1a6bd3e81cc0ebc2f3214723a8602b8240faa9a5ae882edd9d8625af",
        _resolve_artifact("route_clustering/corridor_cluster_assignments.parquet"),
    ),
    RuntimeArtifactSpec(
        "artifacts/route_clustering/buffer_overlap_similarity_matrix.parquet",
        317540,
        "bbf8a4371a5cca857f3a511b5aade91a4ac0792d1e27874c46f4d6ad09a190e4",
        _resolve_artifact("route_clustering/buffer_overlap_similarity_matrix.parquet"),
    ),
    RuntimeArtifactSpec(
        "artifacts/route_clustering/route_direction_jaccard_matrix.parquet",
        191412,
        "35a15c483a8e0e16f6c70aef698d9793b07b3aea8d12fdcdf283c7c3cc0d1b3e",
        _resolve_artifact("route_clustering/route_direction_jaccard_matrix.parquet"),
    ),
    RuntimeArtifactSpec(
        "artifacts/route_clustering/shared_consecutive_stop_sequences.parquet",
        41983,
        "dd7c031a0d4f1705065ec2226f79224083a60c4667b2aa38d4508fe7aba4e57f",
        _resolve_artifact("route_clustering/shared_consecutive_stop_sequences.parquet"),
    ),
    RuntimeArtifactSpec(
        "artifacts/route_clustering/route_direction_geometries_metadata.parquet",
        19105,
        "e1089cc02e26045016b10bb7f9c3d16ba98a9c7a908275eee0aea8d5d4411d0c",
        _resolve_artifact("route_clustering/route_direction_geometries_metadata.parquet"),
    ),
    RuntimeArtifactSpec(
        "artifacts/ranking_features/route_direction_connectivity_matrix.parquet",
        6957,
        "a13f84ea65404bb1fcd3ea856755a037f16f85a2c27498393d1f3adeb4d5b1cc",
        _resolve_artifact("ranking_features/route_direction_connectivity_matrix.parquet"),
    ),
    RuntimeArtifactSpec(
        "artifacts/random_forest/tier1_val_predictions_tuned.parquet",
        560317,
        "4214b9140711c2f1901acb2252b0d90ee25fe095bd240acc65ab4af2a5879f3e",
        _resolve_artifact("random_forest/tier1_val_predictions_tuned.parquet"),
    ),
    RuntimeArtifactSpec(
        "artifacts/random_forest/tier1_test_predictions_tuned.parquet",
        492573,
        "3d1a70b6d447544eb4d3f862a1fd9bcb490f28b2a8725e93ab1e76187402c9a2",
        _resolve_artifact("random_forest/tier1_test_predictions_tuned.parquet"),
    ),
    RuntimeArtifactSpec(
        "artifacts/random_forest/tier1_august_predictions_tuned.parquet",
        75841,
        "33c59e2e4438475dea175fbd39ede81e930eb953451fa35683a7c1fad5281e06",
        _resolve_artifact("random_forest/tier1_august_predictions_tuned.parquet"),
    ),
    RuntimeArtifactSpec(
        "artifacts/random_forest/tier2_val_predictions_tuned.parquet",
        64124,
        "f0f0bb8f4c86892b998e5cf30f9bb3feeaaaf7dd4873800133e3fd3cd5c2981e",
        _resolve_artifact("random_forest/tier2_val_predictions_tuned.parquet"),
    ),
    RuntimeArtifactSpec(
        "artifacts/random_forest/tier2_test_predictions_tuned.parquet",
        144215,
        "4b6825dedc8d601c831e4483e64ee896dc952fca71ff798dd007bc31427e72fb",
        _resolve_artifact("random_forest/tier2_test_predictions_tuned.parquet"),
    ),
)


def compute_sha256(path: Path) -> str:
    """Compute hex SHA-256 digest of a file using 64 KB chunks."""
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sanitize_error(message: str, token: Optional[str]) -> str:
    """Ensure secret tokens never appear in logs or health responses."""
    cleaned = message
    if token:
        cleaned = cleaned.replace(token, "[REDACTED]")
    return cleaned


@dataclass
class HydrationSnapshot:
    """Thread-safe snapshot of runtime data hydration state."""

    status: str = "disabled"  # disabled | idle | hydrating | ready | failed
    total_files: int = len(REMOTE_RUNTIME_MANIFEST)
    verified_files: int = 0
    downloaded_files: int = 0
    skipped_files: int = 0
    attempts: int = 0
    last_error: Optional[str] = None


class RuntimeDataHydrator:
    """Downloads, SHA-256-verifies, and atomically installs private HF Dataset artifacts."""

    def __init__(
        self,
        settings_obj: Settings,
        manifest: Tuple[RuntimeArtifactSpec, ...] = REMOTE_RUNTIME_MANIFEST,
        download_fn: Callable[..., str] = hf_hub_download,
    ) -> None:
        self._settings = settings_obj
        self._manifest = manifest
        self._download_fn = download_fn
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        initial_status = "idle" if settings_obj.HF_HYDRATION_ENABLED else "disabled"
        self._state = HydrationSnapshot(status=initial_status, total_files=len(manifest))

    def snapshot(self) -> HydrationSnapshot:
        """Return a consistent copy of the current hydration state."""
        with self._lock:
            return HydrationSnapshot(**self._state.__dict__)

    def is_data_ready(self) -> bool:
        """True only when all required paths exist and hydration (if enabled) succeeded."""
        missing = sum(1 for p in self._settings.runtime_required_paths if not p.exists())
        if missing > 0:
            return False
        if self._settings.HF_HYDRATION_ENABLED:
            return self.snapshot().status == "ready"
        return True

    def is_blocking_requests(self) -> bool:
        """Prevent API endpoints from reading partial or unverified runtime files."""
        if not self._settings.HF_HYDRATION_ENABLED:
            return False
        return self.snapshot().status != "ready"

    def start_background(self) -> None:
        """Start hydration in a daemon thread if enabled and not already running."""
        if not self._settings.HF_HYDRATION_ENABLED:
            return
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._state.status = "hydrating"
            self._state.last_error = None
            self._thread = threading.Thread(
                target=self.hydrate_sync,
                name="hf-runtime-hydration",
                daemon=True,
            )
            self._thread.start()

    def wait(self, timeout: Optional[float] = None) -> None:
        """Wait for an active background hydration thread to finish."""
        t = self._thread
        if t is not None:
            t.join(timeout=timeout)

    def hydrate_sync(self) -> bool:
        """Execute manifest download + SHA-256 verification with bounded retries."""
        if not self._settings.HF_HYDRATION_ENABLED:
            with self._lock:
                self._state.status = "disabled"
            return True

        token = (self._settings.HF_TOKEN or os.environ.get("HF_TOKEN") or "").strip()
        repo_id = (self._settings.HF_DATASET_REPO_ID or "").strip()

        if not repo_id:
            self._mark_failed("HF_DATASET_REPO_ID is required when HF_HYDRATION_ENABLED=True.")
            return False
        if not token:
            self._mark_failed("HF_TOKEN environment variable is missing for private dataset hydration.")
            return False

        max_attempts = max(1, int(self._settings.HYDRATION_MAX_RETRIES))
        retry_delay = max(0.0, float(self._settings.HYDRATION_RETRY_DELAY_SECONDS))

        for attempt in range(1, max_attempts + 1):
            with self._lock:
                self._state.status = "hydrating"
                self._state.attempts = attempt
                self._state.verified_files = 0
                self._state.downloaded_files = 0
                self._state.skipped_files = 0
                self._state.last_error = None

            try:
                self._hydrate_once(repo_id=repo_id, token=token)
                # Verify Git-tracked report artifacts are also present
                missing_git = [
                    p for p in (
                        self._settings.RF_FINAL_METRICS_CSV_PATH,
                        self._settings.RF_CHAMPION_CONFIG_PATH,
                    )
                    if not p.exists()
                ]
                if missing_git:
                    raise FileNotFoundError(
                        f"Missing {len(missing_git)} repository modeling metadata file(s)."
                    )
                with self._lock:
                    self._state.status = "ready"
                logger.info(
                    "Runtime hydration ready (%d/%d files verified, %d downloaded, %d skipped).",
                    self._state.verified_files,
                    self._state.total_files,
                    self._state.downloaded_files,
                    self._state.skipped_files,
                )
                return True
            except Exception as exc:
                safe_msg = _sanitize_error(f"{type(exc).__name__}: {exc}", token)
                logger.warning("Hydration attempt %d/%d failed: %s", attempt, max_attempts, safe_msg)
                if attempt < max_attempts and retry_delay > 0:
                    time.sleep(retry_delay)
                elif attempt == max_attempts:
                    self._mark_failed(safe_msg)
        return False

    def _hydrate_once(self, repo_id: str, token: str) -> None:
        cache_dir = self._settings.HF_CACHE_DIR or (Path(tempfile.gettempdir()) / "ai_routeranker_hf_cache")
        cache_dir.mkdir(parents=True, exist_ok=True)
        staging_root = Path(tempfile.mkdtemp(prefix="ai_routeranker_stage_"))
        try:
            for spec in self._manifest:
                dest_path = spec.target_resolver(self._settings)
                dest_path.parent.mkdir(parents=True, exist_ok=True)

                if dest_path.exists() and dest_path.stat().st_size == spec.size_bytes:
                    if compute_sha256(dest_path) == spec.sha256:
                        with self._lock:
                            self._state.verified_files += 1
                            self._state.skipped_files += 1
                        continue

                downloaded_str = self._download_fn(
                    repo_id=repo_id,
                    filename=spec.repo_rel_path,
                    repo_type="dataset",
                    revision=self._settings.HF_DATASET_REVISION,
                    token=token,
                    cache_dir=str(cache_dir),
                    local_dir=str(staging_root),
                )
                staged_file = Path(downloaded_str)
                if not staged_file.exists():
                    raise FileNotFoundError(f"Downloaded file missing from staging: {spec.repo_rel_path}")

                actual_size = staged_file.stat().st_size
                if actual_size != spec.size_bytes:
                    raise ValueError(
                        f"Size mismatch for {spec.repo_rel_path}: expected {spec.size_bytes}, got {actual_size}"
                    )
                actual_hash = compute_sha256(staged_file)
                if actual_hash != spec.sha256:
                    raise ValueError(
                        f"SHA-256 mismatch for {spec.repo_rel_path}: expected {spec.sha256[:12]}..., got {actual_hash[:12]}..."
                    )

                # Atomic promotion within target directory so readers never see partial files
                part_path = dest_path.with_name(f".{dest_path.name}.part")
                shutil.copyfile(staged_file, part_path)
                os.replace(part_path, dest_path)

                with self._lock:
                    self._state.verified_files += 1
                    self._state.downloaded_files += 1
        finally:
            shutil.rmtree(staging_root, ignore_errors=True)

    def _mark_failed(self, message: str) -> None:
        with self._lock:
            self._state.status = "failed"
            self._state.last_error = message
        logger.error("Runtime hydration failed: %s", message)
