#!/usr/bin/env bash
cd "$(dirname "$0")/.." && python -m uvicorn api.main:app --reload --port 8000
