$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Ns = "patient-data-services"
$InitSql = Join-Path $Root "postgres\init.sql"

Write-Host "Publishing schema ConfigMap from postgres/init.sql..."
kubectl create configmap app-postgres-init `
  --from-file=init.sql=$InitSql `
  -n $Ns --dry-run=client -o yaml | kubectl apply -f -

kubectl get deploy app-postgres -n $Ns 2>$null | Out-Null
if ($LASTEXITCODE -eq 0) {
  Write-Host "Waiting for app-postgres to be ready..."
  kubectl wait --for=condition=available deployment/app-postgres -n $Ns --timeout=300s

  Write-Host "Applying schema to patient_db..."
  Get-Content $InitSql -Raw | kubectl exec -i -n $Ns deploy/app-postgres -- `
    psql -U patient_app -d patient_db -v ON_ERROR_STOP=1 -q -f -
  Write-Host "Schema applied."
}
