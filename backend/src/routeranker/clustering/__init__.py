"""Unsupervised route clustering for scheduled GTFS features."""

def run_route_clustering(*args, **kwargs):
    """Load the route-clustering runner on demand."""
    from .route_clusters import run_route_clustering as _run

    return _run(*args, **kwargs)


__all__ = ["run_route_clustering"]

