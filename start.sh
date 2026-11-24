#!/usr/bin/env bash
set -e
echo "Running initial RouteRanker analytics & ML training pipeline..."
python analytics/run_pipeline.py
python train_models.py

echo "Starting Autonomous ML Self-Training Scheduler in background..."
python analytics/scheduler.py &
SCHEDULER_PID=$!

echo "Starting FastAPI backend on http://localhost:8000 ..."
uvicorn backend.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

echo "Starting React frontend..."
cd frontend && npm install && npm run dev

kill $BACKEND_PID $SCHEDULER_PID 2>/dev/null || true
