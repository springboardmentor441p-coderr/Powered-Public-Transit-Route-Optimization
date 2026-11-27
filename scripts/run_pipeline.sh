#!/usr/bin/env bash
cd "$(dirname "$0")/.." && python backend/main.py train "$@" && python eda/main.py
