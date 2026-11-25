"""Comprehensive tests for Milestone 8 Stage 2D Historical Forecasting APIs."""

import json
import os
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

# Ensure backend root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.api.v1.deps import get_forecast_repository
from app.main import app
from app.repositories.forecast_repository import ForecastRepository


class TestCanonicalForecastAPI(unittest.TestCase):
    """Integration tests against the canonical Phase 5 Random Forest evaluation artifacts."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_all_five_valid_tier_period_combinations(self):
        """Verify all 5 valid (tier, period) pairs return expected counts, dates, and scope flags."""
        expected = [
            ("tier1", "validation", 37786, "2025-01-01", "2025-11-22", False),
            ("tier1", "test", 28798, "2025-11-23", "2026-07-31", True),
            ("tier1", "august_holdout", 3566, "2026-08-01", "2026-08-31", True),
            ("tier2", "validation", 4117, "2026-04-24", "2026-05-29", False),
            ("tier2", "test", 7293, "2026-05-30", "2026-07-31", True),
        ]
        for tier, period, total, start_dt, end_dt, has_baseline in expected:
            with self.subTest(tier=tier, period=period):
                resp = self.client.get(
                    f"/api/v1/forecasting/historical?tier={tier}&period={period}&limit=10&offset=0"
                )
                self.assertEqual(resp.status_code, 200, resp.text)
                body = resp.json()
                self.assertEqual(body["forecast_scope"], "historical_evaluation_only")
                self.assertFalse(body["future_forecasting_supported"])
                self.assertEqual(body["tier"], tier)
                self.assertEqual(body["period"], period)
                self.assertEqual(body["evaluation_start"], start_dt)
                self.assertEqual(body["evaluation_end"], end_dt)
                self.assertEqual(body["total_records"], total)
                self.assertEqual(body["returned_records"], 10)
                self.assertEqual(body["pagination"]["total"], total)
                self.assertEqual(len(body["data"]), 10)

                first = body["data"][0]
                if has_baseline:
                    self.assertIsNotNone(first["baseline_seasonal_naive_prediction"])
                else:
                    self.assertIsNone(first["baseline_seasonal_naive_prediction"])

    def test_unsupported_tier2_august_holdout_returns_400(self):
        """Verify tier2 + august_holdout is rejected with HTTP 400."""
        resp = self.client.get(
            "/api/v1/forecasting/historical?tier=tier2&period=august_holdout"
        )
        self.assertEqual(resp.status_code, 400)

        resp_summary = self.client.get(
            "/api/v1/forecasting/historical/summary?tier=tier2&period=august_holdout"
        )
        self.assertEqual(resp_summary.status_code, 400)

    def test_invalid_parameters_and_date_ranges(self):
        """Verify invalid tier, period, date range, and pagination bounds return 400 or 422."""
        self.assertEqual(
            self.client.get("/api/v1/forecasting/historical?tier=tier3").status_code,
            400,
        )
        self.assertEqual(
            self.client.get("/api/v1/forecasting/historical?period=future").status_code,
            400,
        )
        self.assertEqual(
            self.client.get(
                "/api/v1/forecasting/historical?start_date=2026-08-20&end_date=2026-08-10"
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.get("/api/v1/forecasting/historical?limit=151").status_code,
            422,
        )
        self.assertEqual(
            self.client.get("/api/v1/forecasting/historical?offset=-1").status_code,
            422,
        )
        self.assertEqual(
            self.client.get(
                "/api/v1/forecasting/historical?start_date=not-a-date"
            ).status_code,
            422,
        )

    def test_route_and_date_filtering_pagination_and_stable_sort(self):
        """Verify route_id, start_date/end_date, pagination, and deterministic (date, route_id) sort."""
        resp = self.client.get(
            "/api/v1/forecasting/historical"
            "?tier=tier1&period=august_holdout&route_id=79"
            "&start_date=2026-08-01&end_date=2026-08-10&limit=5&offset=2"
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["total_records"], 10)
        self.assertEqual(body["returned_records"], 5)
        self.assertEqual(body["pagination"]["offset"], 2)
        self.assertTrue(body["pagination"]["has_more"])
        dates = [item["date"] for item in body["data"]]
        self.assertEqual(dates, sorted(dates))
        self.assertTrue(all(item["route_id"] == "79" for item in body["data"]))

        # Verify multi-route page deterministic (date, route_id) sort
        resp_multi = self.client.get(
            "/api/v1/forecasting/historical?tier=tier1&period=august_holdout&limit=150&offset=0"
        )
        self.assertEqual(resp_multi.status_code, 200)
        keys = [(item["date"], item["route_id"]) for item in resp_multi.json()["data"]]
        self.assertEqual(keys, sorted(keys))

    def test_empty_result_for_nonexistent_route_or_out_of_range_dates(self):
        """Verify nonexistent route_id or out-of-window date range returns 200 with empty data."""
        resp_route = self.client.get(
            "/api/v1/forecasting/historical?tier=tier1&period=august_holdout&route_id=NONEXISTENT_999"
        )
        self.assertEqual(resp_route.status_code, 200)
        self.assertEqual(resp_route.json()["total_records"], 0)
        self.assertEqual(resp_route.json()["returned_records"], 0)
        self.assertEqual(resp_route.json()["data"], [])

        resp_dates = self.client.get(
            "/api/v1/forecasting/historical"
            "?tier=tier1&period=august_holdout&start_date=2027-01-01&end_date=2027-01-31"
        )
        self.assertEqual(resp_dates.status_code, 200)
        self.assertEqual(resp_dates.json()["total_records"], 0)
        self.assertEqual(resp_dates.json()["data"], [])

    def test_summary_endpoint_and_canonical_metrics(self):
        """Verify /historical/summary returns all 5 summaries and exact canonical metrics."""
        resp = self.client.get("/api/v1/forecasting/historical/summary")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["forecast_scope"], "historical_evaluation_only")
        self.assertFalse(body["future_forecasting_supported"])
        self.assertEqual(len(body["supported_combinations"]), 5)
        self.assertEqual(len(body["summaries"]), 5)

        by_key = {(s["tier"], s["period"]): s for s in body["summaries"]}
        self.assertAlmostEqual(by_key[("tier1", "test")]["wape"], 8.5279, places=3)
        self.assertAlmostEqual(by_key[("tier1", "august_holdout")]["wape"], 8.1985, places=3)
        self.assertAlmostEqual(by_key[("tier2", "test")]["wape"], 8.1013, places=3)
        self.assertAlmostEqual(by_key[("tier1", "validation")]["wape"], 7.2430, places=3)
        self.assertAlmostEqual(by_key[("tier2", "validation")]["wape"], 5.6173, places=3)

        # Filtered summary (Tier 1 August Holdout)
        resp_filt = self.client.get(
            "/api/v1/forecasting/historical/summary?tier=tier1&period=august_holdout"
        )
        self.assertEqual(resp_filt.status_code, 200)
        self.assertEqual(len(resp_filt.json()["summaries"]), 1)
        self.assertEqual(resp_filt.json()["summaries"][0]["rows_evaluated"], 3566)
        self.assertEqual(resp_filt.json()["summaries"][0]["total_prediction_records"], 3566)

    def test_validation_summary_distinguishes_common_rows_and_total_records(self):
        """Verify L-02 fix: Tier 1 & Tier 2 validation summaries distinguish rows_evaluated from total_prediction_records."""
        r_t1 = self.client.get("/api/v1/forecasting/historical/summary?tier=tier1&period=validation")
        self.assertEqual(r_t1.status_code, 200)
        s1 = r_t1.json()["summaries"][0]
        self.assertEqual(s1["rows_evaluated"], 37785)
        self.assertEqual(s1["total_prediction_records"], 37786)
        self.assertIn("N5_2025-01-01", s1["evaluation_population_note"])
        self.assertAlmostEqual(s1["wape"], 7.2430, places=4)

        r_t2 = self.client.get("/api/v1/forecasting/historical/summary?tier=tier2&period=validation")
        self.assertEqual(r_t2.status_code, 200)
        s2 = r_t2.json()["summaries"][0]
        self.assertEqual(s2["rows_evaluated"], 4116)
        self.assertEqual(s2["total_prediction_records"], 4117)
        self.assertIn("10_2026-05-20", s2["evaluation_population_note"])
        self.assertAlmostEqual(s2["wape"], 5.6173, places=4)

    def test_whitespace_route_id_rejected_and_missing_route_id_unfiltered(self):
        """Verify L-01 fix: whitespace/empty route_id returns 400 while omitted route_id is unfiltered."""
        for bad_route in ["", "   ", "\t"]:
            resp = self.client.get(
                "/api/v1/forecasting/historical",
                params={"tier": "tier1", "period": "august_holdout", "route_id": bad_route},
            )
            self.assertEqual(resp.status_code, 400, f"Expected 400 for route_id={bad_route!r}")

        resp_ok = self.client.get(
            "/api/v1/forecasting/historical?tier=tier1&period=august_holdout&limit=10"
        )
        self.assertEqual(resp_ok.status_code, 200)
        self.assertEqual(resp_ok.json()["total_records"], 3566)

    def test_canonical_baseline_b_strategy_mapping(self):
        """Verify M-01 fix: canonical calendar_t7 is False, recent_28d_daytype and historical_mean are True."""
        # Test primary calendar_t7 in canonical August holdout
        resp_primary = self.client.get(
            "/api/v1/forecasting/historical?tier=tier1&period=august_holdout&limit=10&offset=0"
        )
        self.assertEqual(resp_primary.status_code, 200)
        first = resp_primary.json()["data"][0]
        self.assertEqual(first["baseline_b_strategy"], "calendar_t7")
        self.assertFalse(first["fallback_baseline_b"])

        # Verify validation period has null strategy and null fallback flag
        resp_val = self.client.get(
            "/api/v1/forecasting/historical?tier=tier1&period=validation&limit=5&offset=0"
        )
        self.assertEqual(resp_val.status_code, 200)
        self.assertIsNone(resp_val.json()["data"][0]["baseline_b_strategy"])
        self.assertIsNone(resp_val.json()["data"][0]["fallback_baseline_b"])

    def test_concurrent_requests_thread_safety(self):
        """Verify 10 concurrent requests succeed deterministically without race conditions."""
        def fetch(idx: int):
            r = self.client.get(
                f"/api/v1/forecasting/historical?tier=tier1&period=august_holdout&limit=20&offset={idx * 20}"
            )
            return r.status_code, len(r.json()["data"])

        with ThreadPoolExecutor(max_workers=10) as pool:
            results = list(pool.map(fetch, range(10)))

        for status_code, count in results:
            self.assertEqual(status_code, 200)
            self.assertEqual(count, 20)


class TestSyntheticForecastEdgeCases(unittest.TestCase):
    """Unit and edge-case tests with synthetic Parquet/CSV/JSON artifacts."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()

    def _build_synthetic_repo(self, tmp_path: Path, corrupt_parquet: bool = False) -> ForecastRepository:
        df_aug = pd.DataFrame(
            {
                "route": ["10", "20", "30", "40"],
                "date": pd.to_datetime(["2026-08-01", "2026-08-01", "2026-08-02", "2026-08-03"]),
                "daytype": ["A", "A", "U", "W"],
                "target_rides": [0.0, np.nan, 100.0, 200.0],
                "rf_tuned_prediction": [12.5, np.inf, 110.0, 210.0],
                "pred_baseline_b_seasonal_naive": [10.0, 50.0, np.nan, 195.0],
                "fallback_baseline_b": [
                    "calendar_t7",
                    "recent_28d_daytype",
                    "historical_mean",
                    None,
                ],
            }
        )
        aug_path = tmp_path / "tier1_august_predictions_tuned.parquet"
        if corrupt_parquet:
            aug_path.write_bytes(b"NOT_A_PARQUET_FILE")
        else:
            df_aug.to_parquet(aug_path, index=False)

        # Minimal valid other files
        df_val = pd.DataFrame(
            {
                "route": ["10"],
                "date": pd.to_datetime(["2025-01-01"]),
                "daytype": ["U"],
                "target_rides": [100.0],
                "pred_random_forest": [105.0],
            }
        )
        t1_val = tmp_path / "tier1_val.parquet"
        t2_val = tmp_path / "tier2_val.parquet"
        df_val.to_parquet(t1_val, index=False)
        df_val.to_parquet(t2_val, index=False)

        df_test = df_aug.copy()
        t1_test = tmp_path / "tier1_test.parquet"
        t2_test = tmp_path / "tier2_test.parquet"
        df_test.to_parquet(t1_test, index=False)
        df_test.to_parquet(t2_test, index=False)

        metrics_csv = tmp_path / "final_metrics.csv"
        pd.DataFrame(
            [
                {
                    "tier": "Tier 1",
                    "partition": "Test",
                    "date_range": "2025-11-23 to 2026-07-31",
                    "rows_evaluated": 3,
                    "rf_wape": 8.5,
                    "rf_mae": 400.0,
                    "rf_rmse": 700.0,
                    "rf_r2": 0.97,
                    "baseline_b_wape": 12.0,
                    "baseline_b_mae": 500.0,
                    "baseline_b_rmse": 900.0,
                    "baseline_b_r2": 0.95,
                },
                {
                    "tier": "Tier 1",
                    "partition": "August Holdout",
                    "date_range": "2026-08-01 to 2026-08-31",
                    "rows_evaluated": 3,
                    "rf_wape": 8.2,
                    "rf_mae": 399.0,
                    "rf_rmse": 709.0,
                    "rf_r2": 0.97,
                    "baseline_b_wape": 13.0,
                    "baseline_b_mae": 600.0,
                    "baseline_b_rmse": 1000.0,
                    "baseline_b_r2": 0.94,
                },
                {
                    "tier": "Tier 2",
                    "partition": "Test",
                    "date_range": "2026-05-30 to 2026-07-31",
                    "rows_evaluated": 3,
                    "rf_wape": 8.1,
                    "rf_mae": 394.0,
                    "rf_rmse": 671.0,
                    "rf_r2": 0.98,
                    "baseline_b_wape": 11.0,
                    "baseline_b_mae": 500.0,
                    "baseline_b_rmse": 850.0,
                    "baseline_b_r2": 0.96,
                },
            ]
        ).to_csv(metrics_csv, index=False)

        champ_json = tmp_path / "champion.json"
        champ_json.write_text(
            json.dumps(
                {
                    "tier1": {
                        "validation_metrics_tuned": {
                            "wape": 7.2,
                            "mae": 346.0,
                            "rmse": 598.0,
                            "r2": 0.98,
                        }
                    },
                    "tier2": {
                        "validation_metrics_tuned": {
                            "wape": 5.6,
                            "mae": 291.0,
                            "rmse": 472.0,
                            "r2": 0.99,
                        }
                    },
                }
            ),
            encoding="utf-8",
        )

        return ForecastRepository(
            tier1_val_path=t1_val,
            tier1_test_path=t1_test,
            tier1_aug_path=aug_path,
            tier2_val_path=t2_val,
            tier2_test_path=t2_test,
            final_metrics_csv_path=metrics_csv,
            champion_config_path=champ_json,
        )

    def test_zero_actual_and_non_finite_values_serialize_cleanly(self):
        """Verify actual_rides == 0 produces percentage_error=None and NaN/Inf become None."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = self._build_synthetic_repo(Path(tmp))
            app.dependency_overrides[get_forecast_repository] = lambda: repo

            resp = self.client.get(
                "/api/v1/forecasting/historical?tier=tier1&period=august_holdout"
            )
            self.assertEqual(resp.status_code, 200, resp.text)
            rows = resp.json()["data"]
            self.assertEqual(len(rows), 4)

            # Row 0: actual=0.0, pred=12.5 -> absolute_error=12.5, percentage_error=None, calendar_t7 -> False
            self.assertEqual(rows[0]["actual_rides"], 0.0)
            self.assertEqual(rows[0]["absolute_error"], 12.5)
            self.assertIsNone(rows[0]["percentage_error"])
            self.assertEqual(rows[0]["baseline_b_strategy"], "calendar_t7")
            self.assertFalse(rows[0]["fallback_baseline_b"])

            # Row 1: actual=NaN, pred=Inf -> sanitized to None, recent_28d_daytype -> True
            self.assertIsNone(rows[1]["actual_rides"])
            self.assertIsNone(rows[1]["predicted_rides"])
            self.assertIsNone(rows[1]["absolute_error"])
            self.assertIsNone(rows[1]["percentage_error"])
            self.assertEqual(rows[1]["baseline_b_strategy"], "recent_28d_daytype")
            self.assertTrue(rows[1]["fallback_baseline_b"])

            # Row 2: actual=100, pred=110 -> abs_err=10, pct_err=10.0, historical_mean -> True
            self.assertEqual(rows[2]["absolute_error"], 10.0)
            self.assertEqual(rows[2]["percentage_error"], 10.0)
            self.assertIsNone(rows[2]["baseline_seasonal_naive_prediction"])
            self.assertEqual(rows[2]["baseline_b_strategy"], "historical_mean")
            self.assertTrue(rows[2]["fallback_baseline_b"])

            # Row 3: None strategy -> preserved as None
            self.assertIsNone(rows[3]["baseline_b_strategy"])
            self.assertIsNone(rows[3]["fallback_baseline_b"])

            # Cached DataFrame immutability check
            cached_df = repo.get_predictions("tier1", "august_holdout")
            with self.assertRaises((ValueError, TypeError)):
                cached_df.loc[cached_df.index[0], "target_rides"] = 999.0

    def test_missing_or_corrupt_artifacts_return_503(self):
        """Verify missing or corrupt Parquet artifacts raise HTTP 503."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            missing_repo = ForecastRepository(
                tier1_val_path=tmp_path / "missing1.parquet",
                tier1_test_path=tmp_path / "missing2.parquet",
                tier1_aug_path=tmp_path / "missing3.parquet",
                tier2_val_path=tmp_path / "missing4.parquet",
                tier2_test_path=tmp_path / "missing5.parquet",
                final_metrics_csv_path=tmp_path / "missing.csv",
                champion_config_path=tmp_path / "missing.json",
            )
            app.dependency_overrides[get_forecast_repository] = lambda: missing_repo
            self.assertEqual(
                self.client.get(
                    "/api/v1/forecasting/historical?tier=tier1&period=august_holdout"
                ).status_code,
                503,
            )
            self.assertEqual(
                self.client.get("/api/v1/forecasting/historical/summary").status_code,
                503,
            )

            corrupt_repo = self._build_synthetic_repo(tmp_path, corrupt_parquet=True)
            app.dependency_overrides[get_forecast_repository] = lambda: corrupt_repo
            self.assertEqual(
                self.client.get(
                    "/api/v1/forecasting/historical?tier=tier1&period=august_holdout"
                ).status_code,
                503,
            )


if __name__ == "__main__":
    unittest.main()
