"""Tests for the learning module, GTFS safety and the model API. Synthetic feeds here are TEST FIXTURES, labelled as such; real-data tests are skipped if real_data/ is absent."""
import io, json, os, sys, zipfile
from pathlib import Path
import numpy as np, pandas as pd, pytest
ROOT = Path(__file__).resolve().parent.parent; sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "data"))
import generate_synthetic_gtfs as gen
from src import learning as L, gtfs_validation as gv, learn as learn_cli
from src.provenance import MODES

@pytest.fixture(scope="module")
def fixture_city_tables():
    """TEST DATA: three generated cities (70 routes each)."""
    out = {}
    for c in ("Delhi", "Mumbai", "Chennai"):
        feed, _ = gen.generate_city(c, seed=11, n_routes=70)
        out[c] = (feed, *L.build_city_table(feed, c))
    return out

@pytest.fixture(scope="module")
def big_city():
    """TEST DATA: one generated city with 260 routes (enough to learn from its own network)."""
    feed, _ = gen.generate_city("Delhi", seed=21, n_routes=260); return (feed, *L.build_city_table(feed, "Delhi"))

@pytest.fixture
def sandbox(tmp_path, monkeypatch, fixture_city_tables):
    monkeypatch.setattr(L, "CORPUS_DIR", tmp_path / "corpus"); monkeypatch.setattr(L, "MODEL_DIR", tmp_path / "models")
    monkeypatch.setattr(L, "MODEL_PATH", tmp_path / "models" / "m.joblib"); monkeypatch.setattr(L, "CARD_PATH", tmp_path / "models" / "card.json")
    monkeypatch.setattr(L, "REGISTRY_PATH", tmp_path / "models" / "reg.json")
    for c, (_, T, I, val, rep) in fixture_city_tables.items(): L.corpus_save(c, T, I, val, rep, "test fixture")
    return tmp_path

FAST = ("baseline_mean", "baseline_hour_mean", "poisson_linear", "gradient_boosting")

def test_feature_schema_has_no_target_leakage(fixture_city_tables):
    _, T, *_ = fixture_city_tables["Delhi"]
    banned = {"trips", "trips_per_day", "peak_trips_per_hr", "offpeak_trips_per_hr", "headway_peak_min", "headway_offpeak_min", "city_scale", "weekend_ratio"}
    assert not banned & set(L.FEATURES) and T[L.FEATURES].isna().sum().sum() == 0 and (T.trips >= 0).all()
    assert not any(f.startswith("city_log") for f in L.FEATURES)         # city fingerprints removed

def test_self_learning_beats_baseline(big_city):
    _, T, I, *_ = big_city
    gap, rpt = L.fit_self(T, I)
    assert rpt["skill"] > 0 and rpt["n_routes"] >= 200 and rpt["cv"]["gradient_boosting"]["mae"] < rpt["cv"]["baseline_hour_mean"]["mae"]
    normal = {"relatively under-served vs peers", "relatively over-served vs peers", "in line with peers"}
    if rpt["reliable"]: assert set(gap.flag) <= normal
    else: assert set(gap.flag) == {"unreliable (model learned little from this feed)"}      # the reliability gate must withhold peer flags

def test_too_few_routes_is_refused(fixture_city_tables):
    _, T, I, *_ = fixture_city_tables["Delhi"]                     # 70 routes: measured to be worse than the baseline when learned alone
    with pytest.raises(ValueError, match="too few"): L.fit_self(T, I)

def test_train_save_load_predict_and_registry(sandbox, fixture_city_tables):
    art, card, gap = L.train(names_models=FAST, fast=True, log=lambda *_: None)
    ok, why = L.promote_or_reject(art, card); assert ok and why == "first model"
    assert L.MODEL_PATH.exists() and json.load(open(L.CARD_PATH))["version"] == card["version"]
    art2 = L.load_model(); feed = fixture_city_tables["Delhi"][0]
    out, val, rep = L.predict_feed(art2, feed, "Delhi2", "auto"); assert out["mode"].str.startswith("pooled").all() and len(out) > 50   # small feed -> pooled, labelled weak
    with pytest.raises(ValueError): L.predict_feed(art2, feed, "Delhi2", "self")

def test_training_is_reproducible(sandbox):
    a = L.train(names_models=FAST, fast=True, log=lambda *_: None)[1]; b = L.train(names_models=FAST, fast=True, log=lambda *_: None)[1]
    assert a["cv_grouped"]["gradient_boosting"]["mae"] == b["cv_grouped"]["gradient_boosting"]["mae"] and a["version"] == b["version"]

def test_champion_challenger_rejects_a_worse_model(sandbox):
    art, card, _ = L.train(names_models=FAST, fast=True, log=lambda *_: None); assert L.promote_or_reject(art, card)[0]
    before = L.MODEL_PATH.stat().st_mtime_ns; worse = json.loads(json.dumps(card)); worse["version"] = "worse"
    for v in worse["loco"][worse["best_model"]].values(): v["mae"] *= 1.3
    ok, why = L.promote_or_reject(art, worse); assert not ok and "->" in why
    assert L.MODEL_PATH.stat().st_mtime_ns == before and any(p.name.startswith("challenger_") for p in L.MODEL_DIR.iterdir())

def test_auto_mode_self_learns_on_a_large_feed(sandbox, big_city):
    art, card, _ = L.train(names_models=FAST, fast=True, log=lambda *_: None); L.promote_or_reject(art, card)
    out, val, rep = L.predict_feed(L.load_model(), big_city[0], "BigCity", "auto")
    assert out["mode"].str.startswith("self").all() and out.model_skill.iloc[0] > 0 and "learning" in rep

def test_incompatible_feature_schema_is_rejected(sandbox, fixture_city_tables):
    art, *_ = L.train(names_models=FAST, fast=True, log=lambda *_: None); art["features"] = art["features"] + ["nonexistent_feature"]
    with pytest.raises(ValueError, match="incompatible"): L.predict_feed(art, fixture_city_tables["Delhi"][0], "X", "pooled")

def test_empty_corpus_message(tmp_path, monkeypatch):
    monkeypatch.setattr(L, "CORPUS_DIR", tmp_path / "none")
    with pytest.raises(FileNotFoundError, match="corpus is empty"): L.corpus_load()

# ---------------------------------------------------------------- GTFS safety / validation
def _zip(members):
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w", zipfile.ZIP_DEFLATED) as z:
        for n, d in members.items(): z.writestr(n, d)
    b.seek(0); return b

def test_zip_slip_and_absolute_paths_rejected():
    for bad in ("../evil.txt", "/etc/passwd", "C:/x.txt", "a/../../b.txt"):
        with pytest.raises(gv.GTFSError, match="unsafe"): gv.read_zip_safely(_zip({bad: "x"}))

def test_archive_bomb_and_garbage_rejected():
    with pytest.raises(gv.GTFSError): gv.read_zip_safely(_zip({"stop_times.txt": "a,b\n" + "0,0\n" * 8_000_000}), limits=dict(ratio_min_size=1000, max_ratio=50))
    with pytest.raises(gv.GTFSError, match="too many"): gv.read_zip_safely(_zip({f"f{i}.txt": "a" for i in range(70)}))
    with pytest.raises(gv.GTFSError, match="not a valid ZIP"): gv.read_zip_safely(io.BytesIO(b"not a zip"))

def test_validation_reports_problems():
    feed = {"routes": pd.DataFrame({"route_id": ["1", "1", "<script>"]}), "trips": pd.DataFrame({"route_id": ["1", "9"], "service_id": ["s", "s"], "trip_id": ["t1", "t2"]}),
            "stops": pd.DataFrame({"stop_id": ["a", "b"], "stop_lat": ["0", "19.0"], "stop_lon": ["0", "73.0"]}),
            "stop_times": pd.DataFrame({"trip_id": ["t1", "t1"], "stop_id": ["a", "zzz"], "stop_sequence": ["1", "2"], "arrival_time": ["25:10:00", "bad"], "departure_time": ["25:10:00", "bad"]})}
    codes = {i["code"] for i in gv.validate_feed(feed)["issues"]}
    assert {"duplicate_id", "trip_route_missing", "stop_time_stop_missing", "bad_coordinates", "invalid_time", "after_midnight", "suspicious_markup", "no_calendar"} <= codes
    r = gv.validate_feed({"routes": pd.DataFrame({"route_id": ["1"]})}); assert r["status"] == "fail" and r["n_errors"] >= 3

def test_after_midnight_and_exception_dates():
    assert gv.to_seconds(pd.Series(["25:30:00", "bad", "01:00:05"])).tolist()[0] == 25 * 3600 + 1800
    feed = {"calendar": pd.DataFrame([dict(service_id="S", monday=1, tuesday=1, wednesday=1, thursday=1, friday=1, saturday=0, sunday=0, start_date="20260101", end_date="20261231")]),
            "calendar_dates": pd.DataFrame([dict(service_id="S", date="20260106", exception_type="2"), dict(service_id="X", date="20260106", exception_type="1")])}
    a, known = gv.active_services(feed, "2026-01-06"); assert a == {"X"}                    # S removed by exception, X added
    a2, _ = gv.active_services(feed, "2026-01-07"); assert a2 == {"S"}

def test_modes_are_documented():
    assert set(MODES) == {"A", "B", "C", "S"} and "NOT assessed" in MODES["A"]["note"] and "GENERATED" in MODES["S"]["note"]

# ---------------------------------------------------------------- model API
def test_model_api(monkeypatch):
    from fastapi.testclient import TestClient
    import server.model_api as M
    from server.main import app
    with TestClient(app) as c:
        card = c.get("/api/model").json()["card"]; assert card["within_city"] and card["data_honesty"]["passenger_data"] is False
        g = c.get("/api/model/peer-gap", params=dict(city="Pune", flag="under", limit=5)).json(); assert 0 < len(g["rows"]) <= 5
        z = ROOT / "sample_uploads" / "Pune_gtfs.zip"
        r = c.post("/api/model/analyze", data=dict(city="Test"), files=dict(gtfs=("a.zip", open(z, "rb"), "application/zip"))); assert r.status_code == 202
        import time
        for _ in range(120):
            j = c.get(f"/api/model/jobs/{r.json()['job']}").json()
            if j["status"] != "running": break
            time.sleep(1)
        assert j["status"] == "done" and j["result"]["n_routes"] > 0 and "pooled" in j["result"]["mode"]        # 22 routes -> too few to self-learn -> pooled, labelled weak
        assert c.post("/api/model/analyze", data=dict(city="x"), files=dict(gtfs=("a.zip", b"junk", "application/zip"))).status_code == 400
        assert c.post("/api/model/analyze", data=dict(city="Test"), files=dict(gtfs=("a.txt", b"PK", "text/plain"))).status_code == 400
        monkeypatch.setattr(M, "MAX_UPLOAD", 500)
        assert c.post("/api/model/analyze", data=dict(city="Test"), files=dict(gtfs=("a.zip", open(z, "rb"), "application/zip"))).status_code == 413
        monkeypatch.undo(); monkeypatch.delenv("RR_ADMIN_TOKEN", raising=False)
        f = dict(gtfs=("a.zip", open(z, "rb"), "application/zip"))
        assert c.post("/api/model/learn", data=dict(name="Newcity"), files=f).status_code == 403            # disabled unless an admin token is configured
        monkeypatch.setenv("RR_ADMIN_TOKEN", "secret"); f = dict(gtfs=("a.zip", open(z, "rb"), "application/zip"))
        assert c.post("/api/model/learn", data=dict(name="Newcity"), files=f, headers={"X-Admin-Token": "wrong"}).status_code == 401
        assert c.get("/api/model/jobs/doesnotexist").status_code == 404

@pytest.mark.skipif(not (ROOT / "real_data" / "Pune_PMPML_gtfs.zip").exists(), reason="real_data/ not present")
def test_real_pune_feed_end_to_end():
    feed = gv.read_zip_safely(ROOT / "real_data" / "Pune_PMPML_gtfs.zip"); T, I, val, rep = L.build_city_table(feed, "Pune")
    assert val["status"] in ("pass", "warn") and I.route_uid.nunique() == 315 and rep["discard_flags"] == []
    gap, rpt = L.fit_self(T, I); assert rpt["skill"] > 0.15, rpt["skill"]
