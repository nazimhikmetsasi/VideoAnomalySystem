# VideoAnomalySystem - Tum servisleri guvenli baslat
# Kullanim: .\start_all.ps1  veya  .\start_all.bat

$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$EnvFile = Join-Path $Root ".env"
$EnvExample = Join-Path $Root ".env.example"
$VenvPython = Join-Path $Root "venv\Scripts\python.exe"

function Test-PortOpen {
    param([string]$HostName, [int]$Port, [int]$TimeoutMs = 1000)
    try {
        $tcp = New-Object System.Net.Sockets.TcpClient
        $iar = $tcp.BeginConnect($HostName, $Port, $null, $null)
        $ok = $iar.AsyncWaitHandle.WaitOne($TimeoutMs, $false)
        if ($ok -and $tcp.Connected) { $tcp.Close(); return $true }
        $tcp.Close()
    } catch {}
    return $false
}

function Wait-ForPort {
    param(
        [string]$Name,
        [string]$HostName,
        [int]$Port,
        [int]$MaxWaitSec = 60
    )
    Write-Host "      $Name bekleniyor (${HostName}:${Port})..." -ForegroundColor Gray
    $deadline = (Get-Date).AddSeconds($MaxWaitSec)
    while ((Get-Date) -lt $deadline) {
        if (Test-PortOpen -HostName $HostName -Port $Port) {
            Write-Host "      $Name hazir." -ForegroundColor Green
            return $true
        }
        Start-Sleep -Seconds 2
    }
    Write-Host "      UYARI: $Name $MaxWaitSec sn icinde hazir olmadi." -ForegroundColor Yellow
    return $false
}

function Wait-ForApiHealth {
    param([int]$MaxWaitSec = 45)
    $url = "http://127.0.0.1:8000/health"
    Write-Host "      API health bekleniyor..." -ForegroundColor Gray
    $deadline = (Get-Date).AddSeconds($MaxWaitSec)
    while ((Get-Date) -lt $deadline) {
        try {
            $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 3
            if ($r.StatusCode -eq 200) {
                Write-Host "      API hazir." -ForegroundColor Green
                return $true
            }
        } catch {}
        Start-Sleep -Seconds 2
    }
    Write-Host "      UYARI: API health $MaxWaitSec sn icinde yanit vermedi." -ForegroundColor Yellow
    return $false
}

function Start-BatWindow {
    param([string]$BatName)
    $batPath = Join-Path $Root $BatName
    if (-not (Test-Path $batPath)) {
        Write-Host "      HATA: $BatName bulunamadi." -ForegroundColor Red
        return
    }
    Start-Process cmd.exe -ArgumentList @("/k", "`"$batPath`"")
}

Write-Host "=== Video Anomaly System Baslatiliyor ===" -ForegroundColor Cyan

if (-not (Test-Path $EnvFile)) {
    if (Test-Path $EnvExample) {
        Copy-Item $EnvExample $EnvFile
        Write-Host "[!] .env olusturuldu (.env.example kopyalandi). Gerekirse duzenleyin." -ForegroundColor Yellow
    } else {
        Write-Host "[!] .env bulunamadi. Proje kokunde .env olusturun." -ForegroundColor Red
    }
}

if (-not (Test-Path $VenvPython)) {
    Write-Host "[HATA] venv bulunamadi: $VenvPython" -ForegroundColor Red
    Write-Host "       python -m venv venv; venv\Scripts\pip install -r requirements.txt" -ForegroundColor Gray
    exit 1
}

Set-Location $Root

Write-Host "[1/5] Docker konteynerleri..." -ForegroundColor Yellow
$dockerOk = $false
try {
    $null = docker info 2>&1
    if ($LASTEXITCODE -eq 0) {
        docker-compose up -d zookeeper kafka postgres mongodb 2>$null
        $dockerOk = $true
        Wait-ForPort -Name "Kafka" -HostName "127.0.0.1" -Port 9092 -MaxWaitSec 90 | Out-Null
    }
} catch {
    Write-Host "      Docker calismiyor. Kafka/DB atlanacak, API bildirim modu kullanilacak." -ForegroundColor Yellow
}

if (-not $dockerOk) {
    Write-Host "      Kafka kapali: pipeline dogrudan API uzerinden bildirim gonderecek." -ForegroundColor Gray
}

if ($dockerOk) {
    Write-Host "[2/5] Anomali suzgeci (run_stream.bat)..." -ForegroundColor Yellow
    Start-BatWindow "run_stream.bat"
    Start-Sleep -Seconds 2
} else {
    Write-Host "[2/5] Anomali suzgeci atlandi (Kafka yok)." -ForegroundColor Gray
}

Write-Host "[3/5] API + WebSocket (run_api.bat)..." -ForegroundColor Yellow
Start-BatWindow "run_api.bat"
Wait-ForApiHealth -MaxWaitSec 45 | Out-Null

Write-Host "[4/5] React dashboard (run_dashboard.bat)..." -ForegroundColor Yellow
Start-BatWindow "run_dashboard.bat"
Start-Sleep -Seconds 3

Write-Host "[5/5] Kamera pipeline (run_kamera.bat)..." -ForegroundColor Yellow
Start-BatWindow "run_kamera.bat"

Start-Sleep -Seconds 4
Write-Host "      Tarayici aciliyor..." -ForegroundColor Gray
Start-Process "http://localhost:5173"

Write-Host ""
Write-Host "=== Hazir ===" -ForegroundColor Green
Write-Host "Dashboard : http://localhost:5173"
Write-Host "Giris     : admin / admin123  (viewer: viewer123)"
Write-Host "API       : http://localhost:8000/health"
Write-Host "Loglar    : logs\pipeline.log, logs\api.log"
Write-Host ""
Write-Host "Durdurmak : .\stop.bat  veya  .\stop_all.bat"
if ($dockerOk) {
    Write-Host "Docker    : docker-compose down"
}
