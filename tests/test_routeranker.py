import sys, zipfile, io
from pathlib import Path
import numpy as np, pandas as pd, pytest
ROOT = Path(__file__).resolve().parent.parent; sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "data"))
import generate_synthetic_gtfs as gen
from src import pipeline, data_loader
from src.cleaning import clean_feed, to_seconds
from src.config import CLASSES

CITIES = ["Pune", "Kochi", "Jaipur", "Indore", "Patna", "Surat", "Bhopal", "Nagpur"]

@pytest.fixture(scope="module")
def datasets():
    return {c: gen.generate_city(c, seed=3, n_routes=14) for c in CITIES}

@pytest.fixture(scope="module")
def bundle(datasets): return pipeline.build_bundle(datasets)

def test_time_parsing_handles_over_24h():
    assert to_seconds(pd.Series(["25:30:00", "bad", "01:00:05"])).tolist()[0] == 25 * 3600 + 1800
    assert np.isnan(to_seconds(pd.Series(["bad"])).iloc[0])

def test_cleaning_repairs_dirty_feed(datasets):
    feed = {k: v.copy() for k, v in datasets["Pune"][0].items()}
    feed = {k: v.astype(str) if k != "calendar" else v for k, v in feed.items()}
    feed["stops"].loc[0, "stop_lat"] = "0"; feed["stops"].loc[1, "stop_lon"] = "nan"           # invalid coords
    feed["stops"] = pd.concat([feed["stops"], feed["stops"].iloc[[5]]])                          # duplicate stop
    feed["stop_times"].loc[3, "arrival_time"] = ""; feed["stop_times"].loc[3, "departure_time"] = ""   # missing time
    clean, rep = clean_feed(feed)
    assert rep["stops_removed_invalid_or_duplicate"] >= 3 and rep["stop_times_missing_time_interpolated"] >= 1
    assert clean["stop_times"].arr_sec.notna().all() and clean["stops"].stop_id.is_unique

def test_zip_loader_roundtrip(datasets):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for k, v in datasets["Pune"][0].items(): z.writestr(f"feed/{k}.txt", v.to_csv(index=False))
    buf.seek(0); feed = data_loader.read_feed_zip(buf)
    assert set(data_loader.REQUIRED) <= set(feed)
    with pytest.raises(FileNotFoundError):
        b2 = io.BytesIO(); zipfile.ZipFile(b2, "w").writestr("routes.txt", "route_id\nR1"); b2.seek(0); data_loader.read_feed_zip(b2)

def test_feature_tables(bundle):
    r = bundle["routes"]
    assert r.route_uid.is_unique and len(r) >= 8 * 10
    assert set(r.label) <= set(CLASSES)
    assert (r.route_length_km > 0).all() and (r.trips_per_day > 0).all() and r.headway_peak_min.between(0, 120).all()
    assert {"route_idx", "city_idx", "label_idx"} <= set(r.columns)
    h = bundle["hourly"]; assert (h.trips > 0).all() and h.load_factor.notna().all()

def test_proxy_mode_without_ridership(datasets):
    feed, _ = datasets["Pune"]; b = pipeline.build_bundle({"Pune": (feed, None)})
    assert (b["routes"].ridership_source == "estimated").all() and b["routes"].daily_boardings.gt(0).all()

def test_train_infer_optimise(bundle):
    art = pipeline.train(bundle, holdout_cities=("Kochi", "Indore"))
    m = art["classifier"]["metrics"][art["classifier"]["best"]]
    assert m["grouped_cv"]["accuracy"] > 0.5            # far better than 33 % chance
    assert "unseen_cities" in m
    res = pipeline.analyze(bundle, art, honest_pred=art["classifier"]["oof_pred"])
    assert {"pred_class", "kmeans_cluster", "dbscan_cluster", "confidence"} <= set(res["routes"].columns)
    b, a = res["impact"]["before"], res["impact"]["after"]
    assert a["n_routes_overcrowded"] <= b["n_routes_overcrowded"]
    assert a["mean_peak_lf"] <= b["mean_peak_lf"] + 1e-9
    assert a["trip_share_nearly_empty"] <= b["trip_share_nearly_empty"] + 1e-9
    recs = res["recs"]; assert set(recs.action) <= {"Increase frequency", "Reduce frequency", "Merge (absorb)", "Merge (retire)", "No change"}
    assert (recs[recs.action == "Increase frequency"].delta_trips > 0).all()
    assert (recs[recs.action == "Reduce frequency"].delta_trips < 0).all()
    assert (recs[recs.action == "Merge (retire)"].trips_day_after == 0).all()

def test_inference_on_unseen_feed_with_saved_models(bundle, datasets):
    art = pipeline.train(bundle, holdout_cities=())
    new = pipeline.build_bundle({"Lucknow": gen.generate_city("Lucknow", seed=99, n_routes=12)})
    res = pipeline.analyze(new, art)
    assert len(res["recs"]) == len(new["routes"]) and set(res["routes"].pred_class) <= set(CLASSES)


def test_forecasting_learns_from_past_and_beats_naive():
    from src import forecast
    ds = {c: gen.generate_city(c, seed=5, n_routes=14) for c in CITIES}
    hist = pd.concat([gen.generate_history(rid, c, 5).assign(city=c) for c, (_, rid) in ds.items()])
    b = pipeline.build_bundle(ds, hist); art = pipeline.train(b, holdout_cities=())
    fm = art["forecaster"]["metrics"]
    assert fm["model"]["wape"] < fm["naive_last3"]["wape"] and fm["model"]["wape"] < 0.15
    res = pipeline.analyze(b, art)
    f = res["forecast"]; assert f.groupby("route_uid").size().eq(12).all() and (f.lo <= f.forecast).all() and (f.forecast <= f.hi).all()
    assert {"fc_mult_avg", "fc_mult_peak", "class_avg", "class_peak"} <= set(res["routes"].columns)
    r2, h2 = forecast.apply_scenario(res["routes"], res["hourly"], "peak")
    assert h2.boardings.sum() > 0 and set(r2.pred_class) <= set(CLASSES)
