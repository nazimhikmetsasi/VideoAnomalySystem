# VideoAnomalySystem - Tum servisleri baslat
# Sag tik -> "PowerShell ile Calistir" veya: .\start_all.ps1

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"
$VenvPython = Join-Path $Root "venv\Scripts\python.exe"

Write-Host "=== Video Anomaly System Baslatiliyor ===" -ForegroundColor Cyan

# 1) Docker altyapisi
Write-Host "[1/5] Docker konteynerleri baslatiliyor..." -ForegroundColor Yellow
Set-Location $Root
docker-compose up -d zookeeper kafka postgres mongodb 2>$null
Write-Host "      Kafka icin 20 saniye bekleniyor..." -ForegroundColor Gray
Start-Sleep -Seconds 20

$envBlock = "`$env:PYTHONPATH='.'; Set-Location '$Backend'"

# 2) Anomali suzgeci
Write-Host "[2/5] Anomali suzgeci (main_stream)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "$envBlock; & '$VenvPython' main_stream.py"

Start-Sleep -Seconds 2

# 3) API
Write-Host "[3/5] API + WebSocket (main_api)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "$envBlock; & '$VenvPython' main_api.py"

Start-Sleep -Seconds 3

# 4) Dashboard
Write-Host "[4/5] React dashboard..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$Frontend'; npm run dev"

Start-Sleep -Seconds 3

# 5) Kamera
Write-Host "[5/5] Kamera pipeline (main_capture)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "$envBlock; & '$VenvPython' main_capture.py"

Write-Host ""
Write-Host "=== Hazir ===" -ForegroundColor Green
Write-Host "Dashboard : http://localhost:5173"
Write-Host "API       : http://localhost:8000/health"
Write-Host ""
Write-Host "Durdurmak icin acilan 4 pencereyi Ctrl+C ile kapat."
Write-Host "Docker    : docker-compose down"
