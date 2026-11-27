@echo off
cd /d "%~dp0.."
python backend\main.py train %*
python eda\main.py
