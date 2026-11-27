"""Unit tests for cleaning, feature engineering, optimisation, clustering helpers and GTFS parsing.

Run:  pytest -q
"""
import io
import zipfile

import numpy as np
import pandas as pd
import pytest

from routeranker import config as C
from routeranker.cleaning import borough_of, clean_ridership, normalize_route_id
from routeranker.clustering import stop_overlap
from routeranker.feature_engineering import add_performance_metrics, add_time_features, classify_occupancy, day_type_of
from routeranker.gtfs import analyse_gtfs, gtfs_time_to_hours
from routeranker.inference import ist_to_transit
from routeranker.optimization import optimize_frequencies, simulate_scenario
from routeranker.preprocessing import time_split


@pytest.fixture(autouse=True)
def fixed_thresholds():
    """Use the documented absolute thresholds regardless of any calibrated file on disk."""
    C.set_thresholds(0.25, 0.85)


def test_route_id_normalisation():
    assert normalize_route_id(" bx12-sbs ") == "BX12+"
    assert normalize_route_id("m15+") == "M15+"
    assert normalize_route_id(None) is None


@pytest.mark.parametrize("rid,boro", [("BX12", "Bronx"), ("B46", "Brooklyn"), ("QM2", "Queens (Express)"),
                                      ("SIM1C", "Staten Island (Express)"), ("M15+", "Manhattan"), ("S79+", "Staten Island")])
def test_borough(rid, boro):
    assert borough_of(rid) == boro


def test_day_type_and_holidays():
    assert day_type_of("2026-11-26") == "Sunday"   # Thanksgiving -> Sunday schedule
    assert day_type_of("2026-11-28") == "Saturday"
    assert day_type_of("2026-11-24") == "Weekday"


def test_ist_conversion():
    from datetime import datetime
    local = ist_to_transit(datetime(2026, 11, 27, 20, 30, tzinfo=C.IST))
    assert (local.hour, local.minute) == (10, 0)  # IST is UTC+5:30, NY is UTC-5 in November


def _raw():
    ts = pd.date_range("2026-01-05", periods=24 * 14, freq="h")
    rows = [{"transit_timestamp": t, "bus_route": "b1", "ridership": 50 + 40 * (t.hour in (8, 17)), "transfers": 5}
            for t in ts if t.hour != 3]  # hour 3 missing -> imputed
    rows.append({"transit_timestamp": ts[10], "bus_route": "B1", "ridership": 10, "transfers": 0})  # duplicate
    return pd.DataFrame(rows)


def test_clean_ridership_fills_grid_and_merges_duplicates():
    df, rep = clean_ridership(_raw())
    assert rep["duplicates_merged"] == 1
    assert rep["imputed_hours"] == 14
    assert df["route_id"].unique().tolist() == ["B1"]
    assert (df["ridership"] >= 0).all()


def _frame():
    f = pd.DataFrame({"route_id": ["A"] * 4, "hour": [7, 8, 13, 23], "ridership": [400, 900, 30, 0],
                      "trips": [6, 6, 6, 0], "capacity": [65] * 4, "trip_minutes": [40] * 4, "transfers": [0] * 4})
    return add_performance_metrics(f)


def test_performance_metrics_and_classes():
    f = _frame()
    assert f.loc[0, "load_per_trip"] == pytest.approx(400 / 6)
    assert f.loc[1, "perf_class"] == "Overcrowded"
    assert f.loc[2, "perf_class"] == "Underutilized"
    assert pd.isna(f.loc[3, "perf_class"])  # no service
    assert classify_occupancy(pd.Series([0.5])).iat[0] == "Balanced"


def test_optimizer_respects_floor_and_fixes_crowding():
    o = optimize_frequencies(_frame())
    assert o.loc[1, "trips_opt"] > 6 and o.loc[1, "occupancy_opt"] <= C.OVERCROWDED_MIN
    assert o.loc[2, "trips_opt"] >= C.MIN_TRIPS_PER_HOUR
    assert o.loc[3, "trips_opt"] == 0


def test_simulator_more_buses_lowers_occupancy():
    s = simulate_scenario(_frame(), frequency_multiplier=2.0)
    assert (s.loc[s["trips"] > 0, "occupancy_sim"] < s.loc[s["trips"] > 0, "occupancy"]).all()


def test_time_split_is_chronological():
    df = pd.DataFrame({"date": pd.date_range("2026-01-01", periods=60, freq="D")})
    tr, va, cut = time_split(df, 28)
    assert tr["date"].max() < va["date"].min() and len(va) == 28


def test_stop_overlap():
    s = pd.DataFrame({"route_id": ["A"] * 4 + ["B"] * 4, "latitude": [40.1, 40.2, 40.3, 40.4] * 2,
                      "longitude": [-73.1, -73.2, -73.3, -73.4, -73.1, -73.2, -73.5, -73.6]})
    ov = stop_overlap(s, ["A", "B"], 0.1)
    assert ov.iloc[0]["shared_stops"] == 2


def test_gtfs_time():
    assert gtfs_time_to_hours(pd.Series(["25:30:00"])).iat[0] == pytest.approx(25.5)


def _gtfs_zip():
    rng = np.random.default_rng(0)
    stops = pd.DataFrame({"stop_id": [f"S{i}" for i in range(30)], "stop_name": [f"Stop {i}" for i in range(30)],
                          "stop_lat": 12.9 + rng.random(30) / 10, "stop_lon": 77.5 + rng.random(30) / 10})
    routes = pd.DataFrame({"route_id": [f"R{i}" for i in range(8)], "route_short_name": [f"{i}" for i in range(8)],
                           "route_long_name": [f"Route {i}" for i in range(8)], "route_type": 3})
    trips, st = [], []
    for r in range(8):
        for k in range(5 + 4 * r):
            tid = f"T{r}_{k}"
            trips.append({"route_id": f"R{r}", "service_id": "WK", "trip_id": tid})
            for j in range(6 + r):
                h = 6 + k * 0.5 + j * 0.05
                t = f"{int(h):02d}:{int(h % 1 * 60):02d}:00"
                st.append({"trip_id": tid, "arrival_time": t, "departure_time": t,
                           "stop_id": f"S{(r * 3 + j) % 30}", "stop_sequence": j + 1})
    cal = pd.DataFrame([{"service_id": "WK", "monday": 1, "tuesday": 1, "wednesday": 1, "thursday": 1, "friday": 1,
                         "saturday": 0, "sunday": 0, "start_date": 20260101, "end_date": 20261231}])
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, df in {"stops": stops, "routes": routes, "trips": pd.DataFrame(trips),
                         "stop_times": pd.DataFrame(st), "calendar": cal}.items():
            z.writestr(f"{name}.txt", df.to_csv(index=False))
    return buf.getvalue()


def test_gtfs_analysis_end_to_end():
    res = analyse_gtfs(_gtfs_zip())
    p = res["profiles"]
    assert len(p) == 8 and {"kmeans_cluster", "flags", "trips_per_day"} <= set(p.columns)
    assert p.set_index("route_id").loc["R7", "trips_per_day"] > p.set_index("route_id").loc["R0", "trips_per_day"]


def test_time_features():
    df = add_time_features(pd.DataFrame({"ts": pd.to_datetime(["2026-11-26 08:00", "2026-11-27 17:00"])}))
    assert df["is_holiday"].tolist() == [1, 0]
    assert df["is_peak"].tolist() == [0, 1]
