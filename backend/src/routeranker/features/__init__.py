"""GTFS feature engineering and validation."""

def run_feature_engineering(*args, **kwargs):
    """Import feature generation on demand for clean ``python -m`` execution."""
    from .engineering import run_feature_engineering as _run_feature_engineering

    return _run_feature_engineering(*args, **kwargs)

__all__ = ["run_feature_engineering"]

