import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fastapi.testclient import TestClient
from server.main import app

def test_api_end_to_end():
    with TestClient(app) as c:
        assert c.get("/api/health").json()["ready"]
        m = c.get("/api/meta").json(); assert len(m["cities"]) == 23 and m["has_forecast"]
        assert c.get("/api/overview").json()["kpis"]["routes"] > 400
        for sc in ("today", "avg", "peak"):
            r = c.get("/api/recommendations", params=dict(scenario=sc, cities="Pune,Kochi")).json(); assert r["recs"] and {x["city"] for x in r["recs"]} <= {"Pune", "Kochi"}
        assert c.get("/api/eda", params=dict(city="Pune")).json()["stops"]
        assert c.get("/api/clusters").json()["points"] and c.get("/api/predictions").json()["routes"]
        f = c.get("/api/forecast", params=dict(city="Pune")).json(); assert f["available"] and len(f["route_fc"]) == 12 and f["backtest"]
        uid = c.get("/api/recommendations").json()["recs"][0]["route_uid"]
        d = c.get("/api/route", params=dict(uid=uid)).json(); assert d["hourly"] and d["stops"]
        i = c.get("/api/impact").json(); assert any(x["key"] == "n_routes_overcrowded" for x in i["rows"])
        assert c.get("/api/download/recommendations.csv").text.startswith("route_uid")
        assert c.get("/api/meta", params=dict(dataset="nope")).status_code == 404
        g = c.post("/api/generate", json=dict(city="Kochi", seed=5)).json(); assert g["has_forecast"]
        assert c.get("/api/overview", params=dict(dataset=g["dataset"])).json()["kpis"]["cities"] == 1
        z = open(Path(__file__).resolve().parent.parent / "sample_uploads" / "Pune_gtfs.zip", "rb")
        u = c.post("/api/upload", data=dict(city="Pune"), files=dict(gtfs=("p.zip", z, "application/zip"))); assert u.status_code == 200 and not u.json()["has_forecast"]
        assert c.post("/api/upload", data=dict(city="X"), files=dict(gtfs=("p.zip", b"junk"))).status_code == 400
