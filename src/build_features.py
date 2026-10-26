"""
Milestone 2: Build Modeling Features, Exact Calendar Lags, Splits & Preprocessor (Steps 9–12)

Usage:
    python src/build_features.py
"""

from pathlib import Path
from src.prepare_modeling_features import (
    load_raw_features,
    compute_exact_calendar_lags,
    calculate_classification_target,
    split_datasets,
    build_and_save_pipeline,
    main,
)

if __name__ == "__main__":
    main()
