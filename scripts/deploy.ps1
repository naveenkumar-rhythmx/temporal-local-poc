$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
kubectl apply -f "$Root\namespaces\"
kubectl apply -f "$Root\postgres\"
kubectl apply -f "$Root\temporal-workflows\k8s\"
kubectl apply -f "$Root\temporal-workers\k8s\"
kubectl apply -f "$Root\patient-data-services\k8s\"
Write-Host "Manifests applied."
