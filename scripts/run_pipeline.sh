#!/usr/bin/env bash
cd "$(dirname "$0")/.." && PYTHONPATH=src python -m routeranker.pipeline "$@"
