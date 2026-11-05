"""API for the learned model: model card, peer comparison, analyse-a-feed jobs, and (token-protected) learning from new feeds."""
import logging, os, re, secrets, threading, time, uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import numpy as np, pandas as pd
from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from src import learning as L, learn as learn_cli, gtfs_validation as gv
from src.config import ROOT

router = APIRouter(prefix="/api/model")
log = logging.getLogger("routeranker")
UPLOAD_DIR = ROOT / "data" / "uploads"                      # private; never served statically
MAX_UPLOAD = int(os.environ.get("RR_MAX_UPLOAD_MB", "100")) * 2**20
JOBS, POOL, TRAIN_LOCK = {}, ThreadPoolExecutor(2), threading.Lock()
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _-]{1,39}$")

def _clean(o):
    if isinstance(o, dict): return {str(k): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)): return [_clean(v) for v in o]
    if isinstance(o, (np.floating, float)): return None if not np.isfinite(o) else float(o)
    if isinstance(o, (np.integer,)): return int(o)
    if isinstance(o, (np.bool_,)): return bool(o)
    return o
def J(o, code=200): return JSONResponse(_clean(o), status_code=code)

async def _save_upload(up: UploadFile) -> Path:
    if not (up.filename or "").lower().endswith(".zip"): raise HTTPException(400, "Please upload a GTFS .zip file.")
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True); p = UPLOAD_DIR / f"{uuid.uuid4().hex}.zip"; n = 0
    with open(p, "wb") as f:
        while chunk := await up.read(1 << 20):
            n += len(chunk)
            if n > MAX_UPLOAD: f.close(); p.unlink(missing_ok=True); raise HTTPException(413, f"File too large (limit {MAX_UPLOAD // 2**20} MB).")
            f.write(chunk)
    with open(p, "rb") as f:
        if f.read(2) != b"PK": p.unlink(missing_ok=True); raise HTTPException(400, "The file is not a ZIP archive.")
    return p

def _job(kind, fn, *args):
    if len(JOBS) > 60: JOBS.pop(next(iter(JOBS)))
    jid = secrets.token_urlsafe(9); JOBS[jid] = dict(id=jid, kind=kind, status="running", created=time.time(), message="Working…")
    def run():
        try: JOBS[jid].update(result=fn(*args), status="done", message="Finished")
        except (gv.GTFSError, ValueError) as e: JOBS[jid].update(status="failed", message=str(e)[:400], validation=getattr(e, "report", None))
        except Exception:
            log.exception("job %s failed", jid); JOBS[jid].update(status="failed", message="The analysis failed unexpectedly. See the server log.")
    POOL.submit(run); return jid

# ---------------------------------------------------------------- read endpoints
_cache = {}
def _read(path, loader):
    m = path.stat().st_mtime if path.exists() else None
    if _cache.get(path, (None,))[0] != m: _cache[path] = (m, loader(path))
    return _cache[path][1]

@router.get("")
def model_card():
    import json
    if not L.CARD_PATH.exists(): raise HTTPException(404, "No trained model yet. Run: python -m src.learn train")
    card = _read(L.CARD_PATH, lambda p: json.load(open(p)))
    reg = _read(L.REGISTRY_PATH, lambda p: json.load(open(p))) if L.REGISTRY_PATH.exists() else []
    return J(dict(card=card, registry=reg, learning_enabled=bool(os.environ.get("RR_ADMIN_TOKEN"))))

@router.get("/peer-gap")
def peer_gap(city: str = "", flag: str = "", limit: int = 400):
    p = ROOT / "outputs" / "peer_gap.csv"
    if not p.exists(): raise HTTPException(404, "No peer comparison yet. Run: python -m src.learn train")
    d = _read(p, pd.read_csv)
    if city: d = d[d.city == city]
    if flag: d = d[d.flag.str.contains(flag)]
    d = d.assign(dev=np.abs(np.log(d.ratio.clip(lower=1e-3)))).sort_values("dev", ascending=False).head(max(1, min(limit, 1000)))
    cols = ["city", "route_short_name", "route_long_name", "actual_trips", "expected_trips", "ratio", "flag"]
    return J(dict(rows=d[cols].round(2).to_dict("records"), cities=sorted(_read(p, pd.read_csv).city.unique())))

# ---------------------------------------------------------------- analyse a feed with the model
def _analyze(path, city):
    art = L.load_model(); out, val, rep = L.predict_feed(art, gv.read_zip_safely(path), city, "auto")
    out = out.assign(dev=np.abs(np.log(out.ratio.clip(lower=1e-3)))).sort_values("dev", ascending=False)
    lr = rep.get("learning")
    return dict(counts=out.flag.value_counts().to_dict(), n_routes=int(len(out)), mode=str(out["mode"].iloc[0]), model_version=art["version"],
                skill=lr["skill"] if lr else None, reliable=lr["reliable"] if lr else None, cv=lr["cv"] if lr else None,
                validation=dict(status=val["status"], issues=[i for i in val["issues"] if i["severity"] != "info"][:20]), cleaning=dict(rows_after=rep["rows_after"], discard_flags=rep["discard_flags"]),
                rows=out[["route_short_name", "route_long_name", "actual_trips", "expected_trips", "ratio", "flag"]].head(500).round(2).to_dict("records"))

@router.post("/analyze", status_code=202)
async def analyze(city: str = Form("MyCity"), gtfs: UploadFile = File(...)):
    if not NAME_RE.match(city): raise HTTPException(400, "City name: 2-40 letters, digits, spaces, - or _.")
    return J(dict(job=_job("analyze", _analyze, await _save_upload(gtfs), city)), 202)

# ---------------------------------------------------------------- teach the model (protected)
def _learn(path, name):
    if not TRAIN_LOCK.acquire(blocking=False): raise ValueError("Another training run is in progress. Try again in a few minutes.")
    try:
        learn_cli.add_corpus(path, name); card = learn_cli.retrain(fast=True); reg = L._registry()[-1]
        return dict(version=card["version"], promoted=reg["promoted"], reason=reg["reason"], best=card["best_model"], cities=reg["cities"], within_city_skill=reg.get("within_city_skill"))
    finally: TRAIN_LOCK.release()

@router.post("/learn", status_code=202)
async def learn(name: str = Form(...), gtfs: UploadFile = File(...), x_admin_token: str | None = Header(None)):
    tok = os.environ.get("RR_ADMIN_TOKEN")
    if not tok: raise HTTPException(403, "Learning is disabled on this server. Set the RR_ADMIN_TOKEN environment variable to enable it.")
    if not x_admin_token or not secrets.compare_digest(x_admin_token, tok): raise HTTPException(401, "Invalid admin token.")
    if not NAME_RE.match(name): raise HTTPException(400, "Name: 2-40 letters, digits, spaces, - or _.")
    return J(dict(job=_job("learn", _learn, await _save_upload(gtfs), name)), 202)

@router.get("/jobs/{jid}")
def job(jid: str):
    j = JOBS.get(jid)
    if not j: raise HTTPException(404, "Unknown job")
    return J({k: v for k, v in j.items() if k != "created"})
