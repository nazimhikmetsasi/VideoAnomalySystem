@echo off
cd /d "%~dp0"
echo === MCBU Sistem Testi ===
echo.

set PYTHONPATH=backend
set PY=%~dp0venv\Scripts\python.exe

echo [1/4] Backend unit testleri...
"%PY%" -m pytest backend\tests\ -q
if errorlevel 1 goto fail

echo.
echo [2/4] Sliding window testi...
"%PY%" scripts\test_stream_filter.py
if errorlevel 1 goto fail

echo.
echo [3/4] API testi (run_api.bat acik olmali)...
powershell -ExecutionPolicy Bypass -File "%~dp0scripts\test_api.ps1"
if errorlevel 1 (
  echo UYARI: API kapali — once .\run_api.bat calistirin
)

echo.
echo [4/4] Frontend build...
cd frontend
call npm run build
if errorlevel 1 goto fail

echo.
echo === TUM TESTLER OK ===
pause
exit /b 0

:fail
echo.
echo === TEST BASARISIZ ===
pause
exit /b 1
