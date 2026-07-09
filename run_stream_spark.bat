@echo off
cd /d "%~dp0backend"
set PYTHONPATH=.
echo Spark Structured Streaming baslatiliyor (Java + Kafka connector gerekir)...
"%~dp0venv\Scripts\python.exe" main_stream.py spark
pause
