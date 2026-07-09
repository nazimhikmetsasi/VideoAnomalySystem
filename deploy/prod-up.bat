@echo off
cd /d "%~dp0"
echo Production stack baslatiliyor...
echo ONCE: deploy\certs\ icine fullchain.pem ve privkey.pem koyun
echo.
docker compose -f docker-compose.prod.yml up -d --build
pause
