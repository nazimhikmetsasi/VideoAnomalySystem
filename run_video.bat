@echo off
setlocal
REM Video dosyasi ile test
REM   .\run_video.bat
REM   .\run_video.bat datasets\pilot\videos\police_run.mp4

cd /d "%~dp0"
set PYTHONPATH=backend
set CAMERA_INPUT_TYPE=file
set CAMERA_ID=cam_01
set SHOW_CAMERA_WINDOW=true

if "%~1"=="" goto :default_video
set "CAMERA_SOURCE=%~f1"
goto :check

:default_video
set "CAMERA_SOURCE=%~dp0datasets\pilot\videos\run_01.mp4"

:check
echo.
echo === Video dosyasi ile test ===
echo Kaynak: %CAMERA_SOURCE%
echo Panel : http://localhost:5173
echo.

if not exist "%CAMERA_SOURCE%" goto :missing

cd /d "%~dp0backend"
"%~dp0venv\Scripts\python.exe" main_capture.py
goto :end

:missing
echo [HATA] Video bulunamadi: %CAMERA_SOURCE%
echo Ornek: .\run_video.bat datasets\pilot\videos\police_run.mp4

:end
pause
