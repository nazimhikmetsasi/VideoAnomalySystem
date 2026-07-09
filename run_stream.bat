# VideoAnomalySystem - Anomali suzgeci (sliding window — varsayilan)
# Spark icin: .\run_stream_spark.bat
cd /d "%~dp0backend"
set PYTHONPATH=.
"%~dp0venv\Scripts\python.exe" main_stream.py python
pause
