# API entegrasyon testi — run_api.bat calisirken
$base = "http://127.0.0.1:8000"
$ErrorActionPreference = "Stop"

try {
    $h = Invoke-RestMethod -Uri "$base/health" -TimeoutSec 5
    Write-Host "[OK] Health:" $h.status "auth:" $h.auth_enabled
} catch {
    Write-Host "[FAIL] API yanit vermiyor — run_api.bat calistirin"
    exit 1
}

$login = Invoke-RestMethod -Uri "$base/api/auth/login" -Method POST -ContentType "application/json" `
    -Body '{"username":"admin","password":"admin123"}'
if (-not $login.ok) { Write-Host "[FAIL] Login"; exit 1 }
Write-Host "[OK] Login admin"

$headers = @{ Authorization = "Bearer $($login.token)" }
$me = Invoke-RestMethod -Uri "$base/api/auth/me" -Headers $headers
Write-Host "[OK] Auth me:" $me.username

$alert = Invoke-RestMethod -Uri "$base/api/test-alert" -Method POST -Headers $headers
Write-Host "[OK] Test alert:" $alert.alert.anomaly_type

$eval = Invoke-RestMethod -Uri "$base/api/evaluation/latest" -Headers $headers
Write-Host "[OK] Evaluation available:" $eval.available

Write-Host ""
Write-Host "API testleri basarili"
exit 0
