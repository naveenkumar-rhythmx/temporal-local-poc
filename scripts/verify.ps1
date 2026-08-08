$ErrorActionPreference = "Stop"

function Pass([string]$Name) { Write-Host "$Name : PASS" }
function Fail([string]$Name) { Write-Host "$Name : FAIL"; exit 1 }

Write-Host "========================================"
Write-Host "Temporal Local Verification"
Write-Host "========================================"

$namespaces = @(
  "patient-data-services",
  "temporal",
  "temporal-workers",
  "temporal-workflows"
)

foreach ($ns in $namespaces) {
  kubectl get ns $ns 2>$null | Out-Null
  if ($LASTEXITCODE -eq 0) { Pass "Namespace $ns" } else { Fail "Namespace $ns" }
}

kubectl get deploy app-postgres -n patient-data-services 2>$null | Out-Null
if ($LASTEXITCODE -eq 0) { Pass "Application PostgreSQL" } else { Fail "Application PostgreSQL" }

kubectl get deploy temporal-frontend -n temporal 2>$null | Out-Null
if ($LASTEXITCODE -eq 0) { Pass "Temporal frontend" } else { Fail "Temporal frontend" }

kubectl get deploy patient-data-worker -n temporal-workers 2>$null | Out-Null
if ($LASTEXITCODE -eq 0) { Pass "Temporal worker" } else { Fail "Temporal worker" }

kubectl get deploy orchestration-core-services -n temporal-workflows 2>$null | Out-Null
if ($LASTEXITCODE -eq 0) { Pass "Workflow starter" } else { Fail "Workflow starter" }

kubectl get deploy patient-data-services -n patient-data-services 2>$null | Out-Null
if ($LASTEXITCODE -eq 0) { Pass "Patient API" } else { Fail "Patient API" }

Write-Host "========================================"
Write-Host "VERIFY RESULT: PASS"
Write-Host "========================================"
