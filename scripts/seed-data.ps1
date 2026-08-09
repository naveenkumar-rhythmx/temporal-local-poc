param(
  [string]$DataFile
)

$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$BaseUrl = if ($env:PATIENT_API_URL) { $env:PATIENT_API_URL } else { "http://127.0.0.1:30082" }
if (-not $DataFile) { $DataFile = Join-Path $Root "test-data\clinical-patients.json" }

Write-Host "Seeding $(Split-Path $DataFile -Leaf) via $BaseUrl ..."
$body = Get-Content $DataFile -Raw
$response = Invoke-RestMethod -Method Post -Uri "$BaseUrl/patient-services/api/v1/ingest/batch" `
  -ContentType "application/json" -Body $body

Write-Host "Workflows started: $($response.count) (failed to start: $($response.failed.Count))"

$expected = (Get-Content $DataFile -Raw | ConvertFrom-Json).Count

Write-Host "Waiting for workflows to finish processing..."
for ($i = 0; $i -lt 40; $i++) {
  $patients = Invoke-RestMethod -Uri "$BaseUrl/patient-services/api/v1/patients"
  $processed = @($patients.patients | Where-Object { $_.status -eq "processed" }).Count
  if ($processed -ge $expected) {
    Write-Host "Processed patients in AIREADY tables: $processed"
    Write-Host "Dashboard: $BaseUrl/patient-services/dashboard"
    exit 0
  }
  Start-Sleep -Seconds 3
}

Write-Host "Timed out waiting for all workflows. Check: kubectl logs -n temporal-workers deploy/patient-data-worker"
exit 1
