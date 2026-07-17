# VideoAnomalySystem - Docker orchestration
# Kullanim: .\docker-up.bat

$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

function Test-PortOpen {
    param([int]$Port)
    try {
        $tcp = New-Object System.Net.Sockets.TcpClient
        $iar = $tcp.BeginConnect("127.0.0.1", $Port, $null, $null)
        $ok = $iar.AsyncWaitHandle.WaitOne(1500, $false)
        if ($ok -and $tcp.Connected) { $tcp.Close(); return $true }
        $tcp.Close()
    } catch {}
    return $false
}

Write-Host "=== MCBU Docker Baslatiliyor ===" -ForegroundColor Cyan

$EnvFile = Join-Path $Root ".env"
$EnvExample = Join-Path $Root ".env.example"
if (-not (Test-Path $EnvFile) -and (Test-Path $EnvExample)) {
    Copy-Item $EnvExample $EnvFile
    Write-Host "[!] .env olusturuldu (.env.example)" -ForegroundColor Yellow
}

try {
    $null = docker info 2>&1
    if ($LASTEXITCODE -ne 0) { throw "Docker calismiyor" }
} catch {
    Write-Host "[HATA] Docker Desktop acik degil." -ForegroundColor Red
    exit 1
}

Write-Host "[1/3] Altyapi (Kafka, Postgres, Mongo)..." -ForegroundColor Yellow
docker compose up -d zookeeper kafka postgres mongodb
if ($LASTEXITCODE -ne 0) { exit 1 }

Write-Host "      Kafka bekleniyor..." -ForegroundColor Gray
$deadline = (Get-Date).AddSeconds(90)
while ((Get-Date) -lt $deadline) {
    if (Test-PortOpen 9092) { break }
    Start-Sleep -Seconds 2
}

Write-Host "[2/3] Uygulama (API, Stream, Frontend)..." -ForegroundColor Yellow
docker compose --profile full up -d --build
if ($LASTEXITCODE -ne 0) { exit 1 }

Write-Host "[3/3] Saglik kontrolu..." -ForegroundColor Yellow
Start-Sleep -Seconds 5
try {
    $h = Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -TimeoutSec 10
    Write-Host "      API: $($h.status)" -ForegroundColor Green
} catch {
    Write-Host "      API henuz hazir degil - birkac saniye bekleyin." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=== Docker Hazir ===" -ForegroundColor Green
Write-Host "Dashboard : http://localhost:3000"
Write-Host "API       : http://localhost:8000/health"
Write-Host "Kafka     : localhost:9092"
Write-Host ""
Write-Host "Kamera (yerel - onerilen): .\run_kamera.bat"
Write-Host "Kamera (Docker - webcam gerekir): docker compose --profile capture up -d capture"
Write-Host "Durdurmak : .\docker-down.bat"
