$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root

$ClusterName = if ($env:CLUSTER_NAME) { $env:CLUSTER_NAME } else { "temporal-local" }

Write-Host "Building Docker images..."
docker build -t temporal-local/patient-data-services:local patient-data-services/
docker build -t temporal-local/workflow-starter:local temporal-workflows/
docker build -f temporal-workers/Dockerfile -t temporal-local/patient-worker:local .

Write-Host "Loading images into kind cluster $ClusterName..."
kind load docker-image temporal-local/patient-data-services:local --name $ClusterName
kind load docker-image temporal-local/workflow-starter:local --name $ClusterName
kind load docker-image temporal-local/patient-worker:local --name $ClusterName

Write-Host "Build complete."
