#!/bin/sh
# One-command launcher: builds the React site if needed, then serves site + API on http://localhost:8000
set -e
pip install -r requirements.txt
if [ ! -d frontend/dist ] && command -v npm >/dev/null; then (cd frontend && npm install && npm run build); fi
uvicorn server.main:app --host 0.0.0.0 --port 8000
