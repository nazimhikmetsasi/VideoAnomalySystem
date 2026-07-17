@echo off
REM Pilot / dosya videosu ile kamera yerine test
REM Kullanim:
REM   run_video.bat
REM   run_video.bat datasets\pilot\videos\run_01.mp4
REM   run_video.bat "C:\yol\video.mp4"

cd /d "%~dp0"
set PYTHONPATH=backend

if "%~1"=="" (
  set "CAMERA_SOURCE=%~dp0datasets\pilot\videos\run_01.mp4"
) else (
  set "CAMERA_SOURCE=%~f1"
)

set CAMERA_INPUT_TYPE=file
set CAMERA_ID=cam_01
set SHOW_CAMERA_WINDOW=true

echo.
echo === Video dosyasi ile test ===
echo Kaynak: %CAMERA_SOURCE%
echo Panel : http://localhost:5173
echo API   : http://127.0.0.1:8000/docs
echo.

if not exist "%CAMERA_SOURCE%" (
  echo [HATA] Video bulunamadi: %CAMERA_SOURCE%
  pause
  exit /b 1
)

cd /d "%~dp0backend"
"%~dp0venv\Scripts\python.exe" main_capture.py
pause
