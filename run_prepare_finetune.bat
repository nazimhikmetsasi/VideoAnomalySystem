@echo off
cd /d "%~dp0backend"
set PYTHONPATH=.
echo === Fine-tune veri hazirligi (kare + otomatik etiket) ===
"%~dp0venv\Scripts\python.exe" training\prepare_finetune_data.py %*
echo.
echo Sonra: .\run_finetune.bat
pause
