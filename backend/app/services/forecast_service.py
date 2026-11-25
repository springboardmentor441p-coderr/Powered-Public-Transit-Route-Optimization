"""Domain service for verified historical Random Forest evaluation predictions."""

import re
from datetime import date
from typing import Any, Dict, List, Optional

import pandas as pd

from app.core.config import settings
from app.core.exceptions import InvalidParameterError
from app.repositories.forecast_repository import ForecastRepository
from app.schemas.common import PaginationMeta, to_optional_float
from app.schemas.forecast import (
    HistoricalForecastResponse,
    HistoricalForecastSummaryResponse,
    HistoricalPredictionItem,
    TierPeriodEvaluationSummary,
)


class ForecastService:
    """Service serving historical evaluation predictions only (no future forecasting)."""

    VALID_TIERS = {"tier1", "tier2"}
    VALID_PERIODS = {"validation", "test", "august_holdout"}

    MODEL_IDENTIFIERS = {
        "tier1": "tier1_random_forest_tuned (Candidate 3 Champion)",
        "tier2": "tier2_random_forest_tuned (Candidate 3 Champion)",
    }

    # Canonical Baseline B priority hierarchy (reports/modeling/baselines/baseline_methodology.md):
    # - 'calendar_t7': Priority 1 primary lag (not a fallback -> False)
    # - 'recent_28d_daytype': Priority 2 fallback when t-7d is absent (True)
    # - 'historical_mean': Priority 3 fallback expanding mean (True)
    # - 'unavailable': Priority 4 no eligible history (None)
    BASELINE_B_STRATEGY_FALLBACK_MAP: Dict[str, Optional[bool]] = {
        "calendar_t7": False,
        "recent_28d_daytype": True,
        "historical_mean": True,
        "unavailable": None,
    }

    @classmethod
    def _interpret_baseline_b_strategy(cls, raw_value: Any) -> tuple[Optional[str], Optional[bool]]:
        """Map canonical Baseline B strategy string without relying on Python truthiness."""
        if raw_value is None or pd.isna(raw_value):
            return None, None
        if isinstance(raw_value, bool):
            return ("fallback" if raw_value else "calendar_t7"), raw_value
        norm = str(raw_value).strip().lower()
        if not norm:
            return None, None
        return norm, cls.BASELINE_B_STRATEGY_FALLBACK_MAP.get(norm)

    PERIOD_BOUNDS = {
        ("tier1", "validation"): (date(2025, 1, 1), date(2025, 11, 22)),
        ("tier1", "test"): (date(2025, 11, 23), date(2026, 7, 31)),
        ("tier1", "august_holdout"): (date(2026, 8, 1), date(2026, 8, 31)),
        ("tier2", "validation"): (date(2026, 4, 24), date(2026, 5, 29)),
        ("tier2", "test"): (date(2026, 5, 30), date(2026, 7, 31)),
    }

    def __init__(self, forecast_repo: ForecastRepository) -> None:
        self._forecast_repo = forecast_repo
        self._route_id_regex = re.compile(settings.ROUTE_ID_PATTERN)

    def _validate_tier_period(self, tier: str, period: str) -> tuple[str, str]:
        t = tier.strip().lower()
        p = period.strip().lower()
        if t not in self.VALID_TIERS:
            raise InvalidParameterError(
                code="INVALID_TIER",
                message="Tier must be 'tier1' or 'tier2'.",
            )
        if p not in self.VALID_PERIODS:
            raise InvalidParameterError(
                code="INVALID_PERIOD",
                message="Period must be 'validation', 'test', or 'august_holdout'.",
            )
        if (t, p) not in ForecastRepository.SUPPORTED_COMBINATIONS:
            raise InvalidParameterError(
                code="UNSUPPORTED_TIER_PERIOD",
                message=f"Period '{p}' is not supported for '{t}' in the approved evaluation design.",
            )
        return t, p

    def get_historical_predictions(
        self,
        tier: str = "tier1",
        period: str = "august_holdout",
        route_id: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = settings.DEFAULT_PAGE_LIMIT,
        offset: int = 0,
    ) -> HistoricalForecastResponse:
        """Return paginated historical evaluation predictions for a valid (tier, period)."""
        t, p = self._validate_tier_period(tier, period)

        cleaned_route: Optional[str] = None
        if route_id is not None:
            cleaned_route = route_id.strip()
            if not cleaned_route or not self._route_id_regex.match(cleaned_route):
                raise InvalidParameterError(
                    code="INVALID_ROUTE_ID",
                    message="Invalid route identifier format.",
                )

        if start_date is not None and end_date is not None and start_date > end_date:
            raise InvalidParameterError(
                code="INVALID_DATE_RANGE",
                message="start_date cannot be later than end_date.",
            )

        df = self._forecast_repo.get_predictions(t, p)
        eval_start, eval_end = self.PERIOD_BOUNDS[(t, p)]

        mask = pd.Series(True, index=df.index)
        if cleaned_route is not None:
            mask &= df["route"] == cleaned_route
        if start_date is not None:
            mask &= df["date"] >= start_date
        if end_date is not None:
            mask &= df["date"] <= end_date

        filtered = df.loc[mask]
        total = len(filtered)
        page_df = filtered.iloc[offset : offset + limit]

        pred_col = "pred_random_forest" if p == "validation" else "rf_tuned_prediction"
        has_baseline = p != "validation"

        items: List[HistoricalPredictionItem] = []
        for _, row in page_df.iterrows():
            actual = to_optional_float(row["target_rides"])
            pred = to_optional_float(row[pred_col])
            abs_err: Optional[float] = None
            pct_err: Optional[float] = None

            if actual is not None and pred is not None:
                abs_err = round(abs(pred - actual), 4)
                if actual > 0.0:
                    pct_err = round((abs_err / actual) * 100.0, 4)

            strategy_str: Optional[str] = None
            fallback_flag: Optional[bool] = None
            if has_baseline:
                strategy_str, fallback_flag = self._interpret_baseline_b_strategy(
                    row["fallback_baseline_b"]
                )

            items.append(
                HistoricalPredictionItem(
                    route_id=str(row["route"]),
                    date=row["date"],
                    daytype=str(row["daytype"]),
                    actual_rides=actual,
                    predicted_rides=pred,
                    absolute_error=abs_err,
                    percentage_error=pct_err,
                    baseline_seasonal_naive_prediction=(
                        to_optional_float(row["pred_baseline_b_seasonal_naive"])
                        if has_baseline
                        else None
                    ),
                    baseline_b_strategy=strategy_str,
                    fallback_baseline_b=fallback_flag,
                )
            )

        filters: Dict[str, Any] = {}
        if cleaned_route is not None:
            filters["route_id"] = cleaned_route
        if start_date is not None:
            filters["start_date"] = start_date.isoformat()
        if end_date is not None:
            filters["end_date"] = end_date.isoformat()

        return HistoricalForecastResponse(
            tier=t,  # type: ignore[arg-type]
            period=p,  # type: ignore[arg-type]
            model_identifier=self.MODEL_IDENTIFIERS[t],
            evaluation_start=eval_start,
            evaluation_end=eval_end,
            total_records=total,
            returned_records=len(items),
            pagination=PaginationMeta(
                total=total,
                offset=offset,
                limit=limit,
                returned=len(items),
                has_more=(offset + len(items)) < total,
            ),
            filters=filters,
            data=items,
        )

    def get_historical_summary(
        self,
        tier: Optional[str] = None,
        period: Optional[str] = None,
    ) -> HistoricalForecastSummaryResponse:
        """Return aggregate historical evaluation metrics across supported (tier, period) pairs."""
        if tier is not None and tier.strip().lower() not in self.VALID_TIERS:
            raise InvalidParameterError(
                code="INVALID_TIER",
                message="Tier must be 'tier1' or 'tier2'.",
            )
        if period is not None and period.strip().lower() not in self.VALID_PERIODS:
            raise InvalidParameterError(
                code="INVALID_PERIOD",
                message="Period must be 'validation', 'test', or 'august_holdout'.",
            )
        if tier is not None and period is not None:
            self._validate_tier_period(tier, period)

        metrics_df = self._forecast_repo.get_final_evaluation_metrics()
        champ_cfg = self._forecast_repo.get_champion_config()

        all_summaries: List[TierPeriodEvaluationSummary] = []

        # Validation summaries from random_forest_champion_config.json
        for t_key, cfg_key in [("tier1", "tier1_champion"), ("tier2", "tier2_champion")]:
            m = champ_cfg[cfg_key]["metrics"]
            s_date, e_date = self.PERIOD_BOUNDS[(t_key, "validation")]
            common_rows = int(m["common_rows"])
            total_val_rows = len(self._forecast_repo.get_predictions(t_key, "validation"))
            add_key = m.get("additional_row_key")
            pop_note: Optional[str] = None
            if total_val_rows != common_rows:
                pop_note = (
                    f"Aggregate metrics were computed over {common_rows} common keys "
                    f"(excluding debut row '{add_key}'); {total_val_rows} total prediction records exist."
                )
            all_summaries.append(
                TierPeriodEvaluationSummary(
                    tier=t_key,  # type: ignore[arg-type]
                    period="validation",
                    model_identifier=self.MODEL_IDENTIFIERS[t_key],
                    evaluation_start=s_date,
                    evaluation_end=e_date,
                    rows_evaluated=common_rows,
                    total_prediction_records=total_val_rows,
                    evaluation_population_note=pop_note,
                    wape=float(m["wape"]),
                    mae=float(m["mae"]),
                    rmse=float(m["rmse"]),
                    r2=float(m["r2"]),
                )
            )

        # Test & Holdout summaries from final_model_evaluation_metrics.csv
        part_map = {
            "Test (GTFS Era)": "test",
            "August Holdout": "august_holdout",
            "Test": "test",
        }
        for _, row in metrics_df.iterrows():
            t_key = f"tier{int(row['tier'])}"
            p_key = part_map[str(row["partition"])]
            s_date, e_date = self.PERIOD_BOUNDS[(t_key, p_key)]
            eval_rows = int(row["rows_evaluated"])
            all_summaries.append(
                TierPeriodEvaluationSummary(
                    tier=t_key,  # type: ignore[arg-type]
                    period=p_key,  # type: ignore[arg-type]
                    model_identifier=self.MODEL_IDENTIFIERS[t_key],
                    evaluation_start=s_date,
                    evaluation_end=e_date,
                    rows_evaluated=eval_rows,
                    total_prediction_records=eval_rows,
                    wape=float(row["rf_wape"]),
                    mae=float(row["rf_mae"]),
                    rmse=float(row["rf_rmse"]),
                    r2=float(row["rf_r2"]),
                    baseline_b_wape=float(row["baseline_b_wape"]),
                    baseline_b_mae=float(row["baseline_b_mae"]),
                    baseline_b_rmse=float(row["baseline_b_rmse"]),
                    baseline_b_r2=float(row["baseline_b_r2"]),
                )
            )

        t_filter = tier.strip().lower() if tier is not None else None
        p_filter = period.strip().lower() if period is not None else None
        filtered = [
            s
            for s in all_summaries
            if (t_filter is None or s.tier == t_filter)
            and (p_filter is None or s.period == p_filter)
        ]
        filtered.sort(key=lambda s: (s.tier, s.evaluation_start))

        return HistoricalForecastSummaryResponse(
            supported_combinations=sorted(f"{t}:{p}" for t, p in ForecastRepository.SUPPORTED_COMBINATIONS),
            summaries=filtered,
        )
