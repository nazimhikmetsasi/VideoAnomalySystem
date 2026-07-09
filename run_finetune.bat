@echo off
cd /d "%~dp0backend"
set PYTHONPATH=.
echo === YOLO Fine-tune ===
echo datasets/pilot/detection/images ve labels dolu olmali.
echo.
"%~dp0venv\Scripts\python.exe" training\finetune_yolo.py
pause
