"""Exploratory and descriptive GTFS analyses."""

def run_eda(*args, **kwargs):
    """Import the EDA runner on demand for clean ``python -m`` execution."""
    from .eda import run_eda as _run_eda

    return _run_eda(*args, **kwargs)

__all__ = ["run_eda"]

