@echo off
cd /d "%~dp0"
"%~dp0venv\Scripts\python.exe" scripts\test_stream_filter.py
pause
