"""Hourly demand profile + stop attraction (shared by generator and proxy model)."""
import numpy as np

def hour_profile(day_type: str = "weekday") -> np.ndarray:
    """Share of daily boardings per hour (sums to 1). Bi-modal on weekdays."""
    h = np.arange(24)
    g = lambda mu, s: np.exp(-0.5 * ((h - mu) / s) ** 2)
    if day_type == "weekday":
        p = 0.12 + 1.0 * g(8.5, 1.4) + 1.15 * g(18.5, 1.8) + 0.45 * g(13, 2.5)
    else:
        p = 0.10 + 0.55 * g(11, 3.0) + 0.65 * g(17.5, 3.0)
    p[(h < 5) | (h > 23)] = 0
    p[(h >= 23) | (h < 5)] = 0.02 * p.max()
    return p / p.sum()

def stop_attraction(dist_to_center_km, scale_km):
    """Attractiveness of a stop: decays with distance from the city core."""
    return np.exp(-np.asarray(dist_to_center_km) / scale_km) + 0.05
