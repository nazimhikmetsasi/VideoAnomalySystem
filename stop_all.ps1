# VideoAnomalySystem - Servisleri durdur
# Sag tik -> "PowerShell ile Calistir" veya: .\stop_all.ps1

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "=== Video Anomaly System Durduruluyor ===" -ForegroundColor Cyan

# Python pipeline / API / stream
Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -match 'main_capture|main_api|main_stream|sliding_window' } |
    ForEach-Object {
        Write-Host "  Python durduruluyor (PID $($_.ProcessId))..." -ForegroundColor Yellow
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }

# Node (Vite dashboard)
Get-CimInstance Win32_Process -Filter "Name='node.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -match 'vite|5173' } |
    ForEach-Object {
        Write-Host "  Dashboard durduruluyor (PID $($_.ProcessId))..." -ForegroundColor Yellow
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }

# Docker (opsiyonel — sadece bu proje konteynerleri)
Set-Location $Root
try {
    $null = docker info 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  Docker konteynerleri durduruluyor..." -ForegroundColor Yellow
        docker-compose down 2>$null
    }
} catch {}

Write-Host ""
Write-Host "=== Durduruldu ===" -ForegroundColor Green
Write-Host "Port 8000 veya 5173 hala aciksa birka saniye bekleyin veya gorev yoneticisinden kontrol edin."
