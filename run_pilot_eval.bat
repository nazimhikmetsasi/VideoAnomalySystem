@echo off
cd /d "%~dp0"
set PYTHONPATH=backend
"%~dp0venv\Scripts\python.exe" scripts\run_pilot_eval.py %*
if errorlevel 1 pause
