"""
AI_RouteRanker - Chronological Time-Series Splitters Module
Implements strictly causal, non-overlapping temporal partitioning for
Tier 1 (Post-Pandemic Macro) and Tier 2 (Contemporary Supply-Informed) models.
"""

from dataclasses import dataclass
from typing import Dict, Any, Tuple
import pandas as pd


@dataclass
class Tier1Partitions:
    """Container for Tier 1 chronological partitions."""
    train: pd.DataFrame
    validation: pd.DataFrame
    test: pd.DataFrame
    august_holdout: pd.DataFrame

    def summary(self) -> Dict[str, Any]:
        return {
            "train": {
                "rows": len(self.train),
                "min_date": str(self.train["date"].min().date()),
                "max_date": str(self.train["date"].max().date()),
                "distinct_routes": int(self.train["route"].nunique()),
            },
            "validation": {
                "rows": len(self.validation),
                "min_date": str(self.validation["date"].min().date()),
                "max_date": str(self.validation["date"].max().date()),
                "distinct_routes": int(self.validation["route"].nunique()),
            },
            "test": {
                "rows": len(self.test),
                "min_date": str(self.test["date"].min().date()),
                "max_date": str(self.test["date"].max().date()),
                "distinct_routes": int(self.test["route"].nunique()),
            },
            "august_holdout": {
                "rows": len(self.august_holdout),
                "min_date": str(self.august_holdout["date"].min().date()),
                "max_date": str(self.august_holdout["date"].max().date()),
                "distinct_routes": int(self.august_holdout["route"].nunique()),
            },
        }


@dataclass
class Tier2Partitions:
    """Container for Tier 2 chronological partitions."""
    train: pd.DataFrame
    validation: pd.DataFrame
    test: pd.DataFrame

    def summary(self) -> Dict[str, Any]:
        return {
            "train": {
                "rows": len(self.train),
                "min_date": str(self.train["date"].min().date()),
                "max_date": str(self.train["date"].max().date()),
                "distinct_routes": int(self.train["route"].nunique()),
            },
            "validation": {
                "rows": len(self.validation),
                "min_date": str(self.validation["date"].min().date()),
                "max_date": str(self.validation["date"].max().date()),
                "distinct_routes": int(self.validation["route"].nunique()),
            },
            "test": {
                "rows": len(self.test),
                "min_date": str(self.test["date"].min().date()),
                "max_date": str(self.test["date"].max().date()),
                "distinct_routes": int(self.test["route"].nunique()),
            },
        }


class ChronologicalSplitter:
    """Enforces non-overlapping, chronological train/validation/test partitions."""

    # Tier 1 Date Boundaries (Post-Pandemic Macro)
    T1_TRAIN_START = "2022-01-01"
    T1_TRAIN_END = "2024-12-31"
    T1_VAL_START = "2025-01-01"
    T1_VAL_END = "2025-11-22"
    T1_TEST_START = "2025-11-23"
    T1_TEST_END = "2026-07-31"
    T1_AUG_START = "2026-08-01"
    T1_AUG_END = "2026-08-31"

    # Tier 2 Date Boundaries (Contemporary Supply-Informed)
    T2_TRAIN_START = "2025-11-23"
    T2_TRAIN_END = "2026-04-23"
    T2_VAL_START = "2026-04-24"
    T2_VAL_END = "2026-05-29"
    T2_TEST_START = "2026-05-30"
    T2_TEST_END = "2026-07-31"

    @classmethod
    def split_tier1(cls, df: pd.DataFrame) -> Tier1Partitions:
        """Splits DataFrame into Tier 1 chronological partitions."""
        train_mask = (df["date"] >= cls.T1_TRAIN_START) & (df["date"] <= cls.T1_TRAIN_END)
        val_mask = (df["date"] >= cls.T1_VAL_START) & (df["date"] <= cls.T1_VAL_END)
        test_mask = (df["date"] >= cls.T1_TEST_START) & (df["date"] <= cls.T1_TEST_END)
        aug_mask = (df["date"] >= cls.T1_AUG_START) & (df["date"] <= cls.T1_AUG_END)

        train_df = df[train_mask].copy()
        val_df = df[val_mask].copy()
        test_df = df[test_mask].copy()
        aug_df = df[aug_mask].copy()

        cls.validate_tier1(train_df, val_df, test_df, aug_df)
        return Tier1Partitions(train=train_df, validation=val_df, test=test_df, august_holdout=aug_df)

    @classmethod
    def split_tier2(cls, df: pd.DataFrame) -> Tier2Partitions:
        """Splits DataFrame into Tier 2 chronological partitions."""
        train_mask = (df["date"] >= cls.T2_TRAIN_START) & (df["date"] <= cls.T2_TRAIN_END)
        val_mask = (df["date"] >= cls.T2_VAL_START) & (df["date"] <= cls.T2_VAL_END)
        test_mask = (df["date"] >= cls.T2_TEST_START) & (df["date"] <= cls.T2_TEST_END)

        train_df = df[train_mask].copy()
        val_df = df[val_mask].copy()
        test_df = df[test_mask].copy()

        cls.validate_tier2(train_df, val_df, test_df)
        return Tier2Partitions(train=train_df, validation=val_df, test=test_df)

    @staticmethod
    def validate_tier1(train: pd.DataFrame, val: pd.DataFrame, test: pd.DataFrame, aug: pd.DataFrame):
        """Verifies strict chronological order and mutual exclusivity."""
        assert train["date"].max() < val["date"].min(), "Tier 1: Train overlaps with Validation!"
        assert val["date"].max() < test["date"].min(), "Tier 1: Validation overlaps with Test!"
        assert test["date"].max() < aug["date"].min(), "Tier 1: Test overlaps with August Holdout!"

    @staticmethod
    def validate_tier2(train: pd.DataFrame, val: pd.DataFrame, test: pd.DataFrame):
        """Verifies strict chronological order and mutual exclusivity."""
        assert train["date"].max() < val["date"].min(), "Tier 2: Train overlaps with Validation!"
        assert val["date"].max() < test["date"].min(), "Tier 2: Validation overlaps with Test!"
