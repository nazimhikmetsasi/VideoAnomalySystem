@echo off
cd /d "%~dp0backend"
set PYTHONPATH=.
"%~dp0venv\Scripts\python.exe" main_capture.py
pause
