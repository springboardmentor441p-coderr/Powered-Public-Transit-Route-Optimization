"""Stage 6b: RouteRanker API (spec 9.17.3). Historical-analysis mode only; every request uses a read-only session.

Run from the repo root (CMD):
  .venv\\Scripts\\uvicorn backend.app.main:app
then open http://127.0.0.1:8000/docs
"""
from fastapi import FastAPI

from backend.app.routers import compare, data, groups, history, maps, rankings, routes

app = FastAPI(title="RouteRanker API", version="0.6.0",
              description="Historical analysis of CTA bus routes (spec 3.8, section 9). Read-only in Stage 6.")
app.include_router(data.router)
app.include_router(compare.router)  # before routes/history, so /api/routes/compare is never read as a route id
app.include_router(routes.router)
app.include_router(history.router)
app.include_router(rankings.router)
app.include_router(groups.router)
app.include_router(maps.router)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
