$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")

kubectl apply -f "$Root\namespaces\"
& "$Root\scripts\apply-schema.ps1"
kubectl apply -f "$Root\postgres\pvc.yaml"
kubectl apply -f "$Root\postgres\deployment.yaml"
kubectl apply -f "$Root\postgres\service.yaml"
kubectl apply -f "$Root\temporal-workflows\k8s\"
kubectl apply -f "$Root\temporal-workers\k8s\"
kubectl apply -f "$Root\patient-data-services\k8s\"
Write-Host "Manifests applied."
