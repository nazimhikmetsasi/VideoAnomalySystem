@echo off
cd /d "%~dp0"
docker compose up -d zookeeper kafka postgres mongodb
echo.
echo Altyapi hazir: Kafka 9092, Postgres 5432, Mongo 27017
echo Uygulama icin: docker-up.bat
pause
