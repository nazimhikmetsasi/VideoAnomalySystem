# Hizli sistem saglik kontrolu
# Kullanim: .\scripts\check_system.ps1

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$VenvPython = Join-Path $Root "venv\Scripts\python.exe"

function Test-Port {
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

Write-Host "=== Sistem Kontrolu ===" -ForegroundColor Cyan

$checks = @(
    @{ Name = "venv";           Ok = (Test-Path $VenvPython) },
    @{ Name = ".env";           Ok = (Test-Path (Join-Path $Root ".env")) },
    @{ Name = "API :8000";      Ok = (Test-Port 8000) },
    @{ Name = "Dashboard :5173"; Ok = (Test-Port 5173) },
    @{ Name = "Kafka :9092";    Ok = (Test-Port 9092) },
    @{ Name = "Postgres :5432"; Ok = (Test-Port 5432) },
    @{ Name = "Mongo :27017";   Ok = (Test-Port 27017) }
)

foreach ($c in $checks) {
    $icon = if ($c.Ok) { "[OK]" } else { "[--]" }
    $color = if ($c.Ok) { "Green" } else { "Gray" }
    Write-Host "  $icon $($c.Name)" -ForegroundColor $color
}

try {
    $health = Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -TimeoutSec 3
    Write-Host "  [OK] API health: $($health | ConvertTo-Json -Compress)" -ForegroundColor Green
} catch {
    Write-Host "  [--] API health yanit vermiyor" -ForegroundColor Gray
}

Write-Host ""
Write-Host "Log dosyalari:" -ForegroundColor Cyan
$logDir = Join-Path $Root "logs"
if (Test-Path $logDir) {
    Get-ChildItem $logDir -Filter "*.log" | ForEach-Object {
        $mb = [math]::Round($_.Length / 1MB, 2)
        Write-Host "  $($_.Name) — ${mb} MB" -ForegroundColor Gray
    }
} else {
    Write-Host "  logs/ klasoru henuz yok" -ForegroundColor Gray
}
