@echo off
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File "%~dp0docker-down.ps1"
pause
