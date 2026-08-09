$ErrorActionPreference = "Continue"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$PatientApi = if ($env:PATIENT_API) { $env:PATIENT_API } else { "http://127.0.0.1:30082" }
$Timeout = if ($env:E2E_TIMEOUT) { [int]$env:E2E_TIMEOUT } else { 120 }
$script:E2EFail = 0

function Pass([string]$Name) { Write-Host "$Name : PASS" }
function FailMsg([string]$Name) { Write-Host "$Name : FAIL"; $script:E2EFail = 1 }

Write-Host "========================================"
Write-Host "Temporal Local E2E Test"
Write-Host "========================================"

$PatientJson = '{"patient_id":"PAT-10001","first_name":"John","last_name":"Example","dob":"1985-04-12","encounter_id":"ENC-10001","diagnosis":"EXAMPLE-DIAGNOSIS","source":"local-demo"}'

if (Test-Path (Join-Path $Root "test-data\patients.json")) { Pass "Patient input" } else { FailMsg "Patient input" }

try {
  Invoke-RestMethod -Uri "$PatientApi/patient-services/health" -Method GET | Out-Null
  Pass "Patient API"
} catch {
  FailMsg "Patient API"
}

kubectl get deploy temporal-frontend -n temporal 2>$null | Out-Null
if ($LASTEXITCODE -eq 0) { Pass "Temporal connection" } else { FailMsg "Temporal connection" }

$WorkflowId = ""
try {
  $start = Invoke-RestMethod -Uri "$PatientApi/patient-services/api/v1/ingest" `
    -Method POST `
    -ContentType "application/json" `
    -Body $PatientJson
  Pass "Workflow started"
  $WorkflowId = $start.workflow_id
} catch {
  FailMsg "Workflow started"
}

$Result = $null
if ($WorkflowId) {
  $elapsed = 0
  while ($elapsed -lt $Timeout) {
    try {
      $Result = Invoke-RestMethod -Uri "$PatientApi/patient-services/api/v1/workflows/$WorkflowId/result" -Method GET
      break
    } catch {
      Start-Sleep -Seconds 3
      $elapsed += 3
    }
  }
  if ($null -ne $Result) {
    Pass "Worker activity"
    Pass "Formatter"
    Pass "Workflow completed"
  } else {
    FailMsg "Worker activity"
    FailMsg "Formatter"
    FailMsg "Workflow completed"
  }
} else {
  FailMsg "Worker activity"
  FailMsg "Formatter"
  FailMsg "Workflow completed"
}

$pgCheck = kubectl exec -n patient-data-services deploy/app-postgres -- `
  psql -U patient_app -d patient_db -tAc "SELECT count(*) FROM formatted_patient_data WHERE patient_id='PAT-10001';" 2>$null
if ([int]("$pgCheck".Trim()) -ge 1) { Pass "PostgreSQL write" } else { FailMsg "PostgreSQL write" }

$expectedObj = Get-Content (Join-Path $Root "test-data\expected-results.json") -Raw | ConvertFrom-Json
$Expected = $expectedObj."PAT-10001".display_name
$rawJson = kubectl exec -n patient-data-services deploy/app-postgres -- `
  psql -U patient_app -d patient_db -tAc "SELECT formatted_json FROM formatted_patient_data WHERE patient_id='PAT-10001' ORDER BY id DESC LIMIT 1;" 2>$null
$Actual = ""
if ($rawJson) {
  $Actual = ($rawJson | ConvertFrom-Json).display_name
}
if ($Actual -eq $Expected) { Pass "Result validation" } else { FailMsg "Result validation (expected=$Expected actual=$Actual)" }

# Dashboard: ingest a clinical patient, then read the chart and RhythmX panel back
$ClinicalId = "PAT-20001"
try {
  $seedBody = Get-Content (Join-Path $Root "test-data\clinical-patients.json") -Raw
  Invoke-RestMethod -Uri "$PatientApi/patient-services/api/v1/ingest/batch" `
    -Method POST -ContentType "application/json" -Body $seedBody | Out-Null
} catch { }

$airCount = 0
$elapsed = 0
while ($elapsed -lt $Timeout) {
  try {
    $air = Invoke-RestMethod -Uri "$PatientApi/patient-services/api/v1/patient/$ClinicalId/air-collections"
    $airCount = $air.conditions.Count + $air.medications.Count + $air.labs.Count
  } catch { $airCount = 0 }
  if ($airCount -gt 0) { break }
  Start-Sleep -Seconds 3
  $elapsed += 3
}
if ($airCount -gt 0) { Pass "AIREADY collections populated" } else { FailMsg "AIREADY collections populated" }

try {
  $plist = Invoke-RestMethod -Uri "$PatientApi/patient-services/api/v1/patients"
  if ($plist.count -gt 0) { Pass "Dashboard patient list" } else { FailMsg "Dashboard patient list" }
} catch { FailMsg "Dashboard patient list" }

try {
  $ai = Invoke-RestMethod -Uri "$PatientApi/patient-services/api/v1/patient/$ClinicalId/rhythmx"
  if ($ai.history_summary -and $ai.recommendations.Count -gt 0) {
    Pass "RhythmX AI recommendations"
  } else {
    FailMsg "RhythmX AI recommendations"
  }
} catch { FailMsg "RhythmX AI recommendations" }

try {
  $page = Invoke-WebRequest -Uri "$PatientApi/patient-services/dashboard" -UseBasicParsing
  if ($page.StatusCode -eq 200) { Pass "Dashboard page" } else { FailMsg "Dashboard page" }
} catch { FailMsg "Dashboard page" }

Write-Host ""
if ($script:E2EFail -eq 0) {
  Write-Host "E2E RESULT: PASS"
} else {
  Write-Host "E2E RESULT: FAIL"
  exit 1
}
Write-Host "========================================"
