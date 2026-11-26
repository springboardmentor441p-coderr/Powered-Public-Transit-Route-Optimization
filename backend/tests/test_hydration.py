"""Tests for private Hugging Face Dataset runtime data hydration."""

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Optional
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core import config as cfg_mod
from app.core.config import Settings
from app.core.hydration import REMOTE_RUNTIME_MANIFEST, RuntimeDataHydrator
from app.main import app


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _get_derived_audit_db() -> Optional[Path]:
    raw = os.environ.get("DERIVED_AUDIT_DB", "").strip()
    if not raw:
        return None
    p = Path(raw)
    return p if p.exists() else None


def _source_for_repo_path(repo_rel_path: str) -> Path:
    if repo_rel_path == "data/processed/ai_routeranker.duckdb":
        derived = _get_derived_audit_db()
        if derived is not None:
            return derived
    return PROJECT_ROOT / repo_rel_path


def _local_dataset_downloader(expected_token: str):
    """Simulate hf_hub_download from a private dataset repo using local verified files."""

    def _download(*, repo_id, filename, repo_type, revision, token, cache_dir, local_dir):
        if repo_type != "dataset":
            raise ValueError(f"Unexpected repo_type: {repo_type}")
        if repo_id != "private-org/ai-routeranker-runtime":
            raise ValueError(f"Unexpected repo_id: {repo_id}")
        if token != expected_token:
            raise PermissionError(f"401 Unauthorized for private repo with token {token}")
        src = _source_for_repo_path(filename)
        dest = Path(local_dir) / filename
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
        return str(dest)

    return _download


class TestRuntimeHydration(unittest.TestCase):
    """Test missing/invalid tokens, downloads, retries, hash checks, and rehydration."""

    def _make_settings(self, tmp_path: Path, **overrides) -> Settings:
        kwargs = {
            "DATA_DIR": tmp_path / "data" / "processed",
            "ARTIFACTS_DIR": tmp_path / "artifacts",
            "HF_CACHE_DIR": tmp_path / "hf_cache",
            "HF_HYDRATION_ENABLED": True,
            "HF_DATASET_REPO_ID": "private-org/ai-routeranker-runtime",
            "HYDRATION_MAX_RETRIES": 2,
            "HYDRATION_RETRY_DELAY_SECONDS": 0.0,
        }
        kwargs.update(overrides)
        return Settings(**kwargs)

    def test_missing_token_fails_safely(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("HF_TOKEN", None)
                s = self._make_settings(Path(tmp), HF_TOKEN="")
                hydrator = RuntimeDataHydrator(s, download_fn=_local_dataset_downloader("hf_valid_secret"))

                self.assertFalse(hydrator.hydrate_sync())
                snap = hydrator.snapshot()
                self.assertEqual(snap.status, "failed")
                self.assertIn("HF_TOKEN", snap.last_error or "")
                self.assertFalse(hydrator.is_data_ready())
                self.assertTrue(hydrator.is_blocking_requests())

    def test_invalid_token_redacts_secret_and_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad_token = "hf_super_secret_invalid_token_12345"
            s = self._make_settings(Path(tmp), HF_TOKEN=bad_token)
            hydrator = RuntimeDataHydrator(s, download_fn=_local_dataset_downloader("hf_valid_secret"))

            self.assertFalse(hydrator.hydrate_sync())
            snap = hydrator.snapshot()
            self.assertEqual(snap.status, "failed")
            self.assertNotIn(bad_token, snap.last_error or "")
            self.assertIn("[REDACTED]", snap.last_error or "")
            self.assertFalse(hydrator.is_data_ready())

    def test_successful_private_download_and_health_and_guard(self):
        if _get_derived_audit_db() is None:
            self.skipTest("Optional DERIVED_AUDIT_DB env var is not set or file is unavailable.")
        with tempfile.TemporaryDirectory() as tmp:
            token = "hf_valid_secret"
            s = self._make_settings(Path(tmp), HF_TOKEN=token)
            hydrator = RuntimeDataHydrator(s, download_fn=_local_dataset_downloader(token))

            orig_hydrator = app.state.hydrator
            orig_enabled = cfg_mod.settings.HF_HYDRATION_ENABLED
            try:
                cfg_mod.settings.HF_HYDRATION_ENABLED = True
                app.state.hydrator = hydrator
                client = TestClient(app)

                blocked_resp = client.get("/api/v1/routes")
                self.assertEqual(blocked_resp.status_code, 503)
                self.assertEqual(blocked_resp.json()["code"], "RUNTIME_DATA_NOT_READY")

                health_before = client.get("/api/health").json()
                self.assertFalse(health_before["data_ready"])
                self.assertEqual(health_before["hydration_status"], "idle")

                self.assertTrue(hydrator.hydrate_sync())
                snap = hydrator.snapshot()
                self.assertEqual(snap.status, "ready")
                self.assertEqual(snap.verified_files, len(REMOTE_RUNTIME_MANIFEST))
                self.assertEqual(snap.downloaded_files, len(REMOTE_RUNTIME_MANIFEST))
                self.assertTrue(hydrator.is_data_ready())
                self.assertFalse(hydrator.is_blocking_requests())

                unblocked_resp = client.get("/api/v1/routes?limit=5")
                self.assertEqual(unblocked_resp.status_code, 200)
            finally:
                cfg_mod.settings.HF_HYDRATION_ENABLED = orig_enabled
                app.state.hydrator = orig_hydrator

    def test_incomplete_download_retries_and_recovers(self):
        if _get_derived_audit_db() is None:
            self.skipTest("Optional DERIVED_AUDIT_DB env var is not set or file is unavailable.")
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            token = "hf_valid_secret"
            s = self._make_settings(tmp_path, HF_TOKEN=token, HYDRATION_MAX_RETRIES=3)
            calls = {"count": 0}
            base_dl = _local_dataset_downloader(token)

            def flaky_download(**kwargs):
                calls["count"] += 1
                if calls["count"] == 2:
                    raise ConnectionError("Simulated mid-stream network drop")
                return base_dl(**kwargs)

            hydrator = RuntimeDataHydrator(s, download_fn=flaky_download)
            self.assertTrue(hydrator.hydrate_sync())
            snap = hydrator.snapshot()
            self.assertEqual(snap.status, "ready")
            self.assertEqual(snap.attempts, 2)
            self.assertEqual(list(tmp_path.rglob("*.part")), [])

    def test_hash_mismatch_fails_without_exposing_corrupt_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            token = "hf_valid_secret"
            s = self._make_settings(Path(tmp), HF_TOKEN=token, HYDRATION_MAX_RETRIES=1)

            def corrupt_download(*, repo_id, filename, repo_type, revision, token, cache_dir, local_dir):
                dest = Path(local_dir) / filename
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(b"corrupted-payload")
                return str(dest)

            hydrator = RuntimeDataHydrator(s, download_fn=corrupt_download)
            self.assertFalse(hydrator.hydrate_sync())
            snap = hydrator.snapshot()
            self.assertEqual(snap.status, "failed")
            self.assertTrue(
                "Size mismatch" in (snap.last_error or "") or "SHA-256 mismatch" in (snap.last_error or "")
            )
            self.assertFalse(s.DUCKDB_PATH.exists())

    def test_restart_and_rehydration_skips_verified_files(self):
        if _get_derived_audit_db() is None:
            self.skipTest("Optional DERIVED_AUDIT_DB env var is not set or file is unavailable.")
        with tempfile.TemporaryDirectory() as tmp:
            token = "hf_valid_secret"
            s = self._make_settings(Path(tmp), HF_TOKEN=token)
            hydrator1 = RuntimeDataHydrator(s, download_fn=_local_dataset_downloader(token))
            self.assertTrue(hydrator1.hydrate_sync())

            # Simulate container restart with warm /tmp directory
            hydrator2 = RuntimeDataHydrator(s, download_fn=_local_dataset_downloader(token))
            self.assertTrue(hydrator2.hydrate_sync())
            snap2 = hydrator2.snapshot()
            self.assertEqual(snap2.status, "ready")
            self.assertEqual(snap2.skipped_files, len(REMOTE_RUNTIME_MANIFEST))
            self.assertEqual(snap2.downloaded_files, 0)

            # Delete 1 file and verify selective rehydration
            s.EXPLANATIONS_PATH.unlink()
            hydrator3 = RuntimeDataHydrator(s, download_fn=_local_dataset_downloader(token))
            self.assertTrue(hydrator3.hydrate_sync())
            snap3 = hydrator3.snapshot()
            self.assertEqual(snap3.skipped_files, len(REMOTE_RUNTIME_MANIFEST) - 1)
            self.assertEqual(snap3.downloaded_files, 1)


if __name__ == "__main__":
    unittest.main()
