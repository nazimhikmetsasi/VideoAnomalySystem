# VideoAnomalySystem - Docker durdur
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

Write-Host "=== MCBU Docker Durduruluyor ===" -ForegroundColor Cyan
docker compose --profile full --profile capture down
Write-Host "=== Durduruldu ===" -ForegroundColor Green
