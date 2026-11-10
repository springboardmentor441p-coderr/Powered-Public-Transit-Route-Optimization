"""Read GTFS archives and materialize validated analytical tables."""

from .time import parse_gtfs_time


def run_pipeline(*args, **kwargs):
    """Import the pipeline on demand to keep ``python -m`` execution clean."""
    from .pipeline import run_pipeline as _run_pipeline

    return _run_pipeline(*args, **kwargs)


__all__ = ["parse_gtfs_time", "run_pipeline"]

