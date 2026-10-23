@echo off
pip install -r requirements.txt
if not exist frontend\dist (cd frontend && npm install && npm run build && cd ..)
uvicorn server.main:app --host 0.0.0.0 --port 8000
