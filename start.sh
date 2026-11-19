#!/usr/bin/env bash
set -e
echo "Running RouteRanker analytics & ML training pipeline..."
python analytics/run_pipeline.py

echo "Starting FastAPI backend on http://localhost:8000 ..."
uvicorn backend.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

echo "Starting React frontend..."
cd frontend && npm install && npm run dev

kill $BACKEND_PID
