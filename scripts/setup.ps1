$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root

$ClusterName = if ($env:CLUSTER_NAME) { $env:CLUSTER_NAME } else { "temporal-local" }
$KubeContext = "kind-$ClusterName"

# Prefer the local kind context (never touch AKS by accident)
$contexts = kubectl config get-contexts -o name 2>$null
if ($contexts -contains $KubeContext) {
  kubectl config use-context $KubeContext | Out-Null
}

$existing = kind get clusters 2>$null
if ($existing -notcontains $ClusterName) {
  Write-Host "Creating kind cluster $ClusterName..."
  kind create cluster --name $ClusterName --config kind/cluster.yaml
} else {
  Write-Host "Kind cluster $ClusterName already exists (idempotent)."
  kubectl config use-context $KubeContext | Out-Null
}

Write-Host "Creating namespaces..."
kubectl apply -f namespaces/

Write-Host "Building and loading images..."
& "$Root\scripts\build.ps1"

Write-Host "Deploying application PostgreSQL..."
kubectl create configmap app-postgres-init `
  --from-file=init.sql=postgres/init.sql `
  -n patient-data-services --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f postgres/pvc.yaml
kubectl apply -f postgres/deployment.yaml
kubectl apply -f postgres/service.yaml

Write-Host "Deploying Temporal PostgreSQL (Bitnami)..."
helm repo add bitnami https://charts.bitnami.com/bitnami 2>$null
helm repo update bitnami
helm upgrade --install temporal-postgresql bitnami/postgresql `
  -n temporal `
  -f temporal/postgres.yaml `
  --wait --timeout 5m

Write-Host "Creating temporal_visibility database if missing..."
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=postgresql -n temporal --timeout=300s
$pgPod = kubectl get pod -n temporal -l app.kubernetes.io/name=postgresql -o jsonpath='{.items[0].metadata.name}'
$createSql = @'
SELECT 1 FROM pg_database WHERE datname = 'temporal_visibility'
'@
$exists = kubectl exec -n temporal $pgPod -- bash -c "PGPASSWORD=temporal psql -U temporal -tc `"$createSql`""
if ($exists -notmatch "1") {
  kubectl exec -n temporal $pgPod -- bash -c "PGPASSWORD=temporal psql -U temporal -c `"CREATE DATABASE temporal_visibility;`""
}

Write-Host "Deploying Temporal server (Helm)..."
helm repo add temporal https://go.temporal.io/helm-charts 2>$null
helm repo update temporal
kubectl apply -f temporal/namespace.yaml
helm upgrade --install temporal temporal/temporal `
  --version 1.6.0 `
  -n temporal `
  -f temporal/values.yaml `
  --wait --timeout 10m

Write-Host "Waiting for Temporal frontend..."
kubectl wait --for=condition=available deployment/temporal-frontend -n temporal --timeout=300s

Write-Host "Deploying workflow starter, worker, patient-data-services..."
kubectl apply -f temporal-workflows/k8s/deployment.yaml
kubectl apply -f temporal-workers/k8s/deployment.yaml
kubectl apply -f patient-data-services/k8s/deployment.yaml

Write-Host "Waiting for application deployments..."
kubectl wait --for=condition=available deployment/app-postgres -n patient-data-services --timeout=300s
kubectl wait --for=condition=available deployment/orchestration-core-services -n temporal-workflows --timeout=300s
kubectl wait --for=condition=available deployment/patient-data-worker -n temporal-workers --timeout=300s
kubectl wait --for=condition=available deployment/patient-data-services -n patient-data-services --timeout=300s

Write-Host "Applying application schema (idempotent, also upgrades existing volumes)..."
& "$Root\scripts\apply-schema.ps1"

Write-Host "Restarting services so they pick up config/schema changes..."
kubectl rollout restart deployment/patient-data-services -n patient-data-services
kubectl rollout restart deployment/patient-data-worker -n temporal-workers
kubectl rollout status deployment/patient-data-services -n patient-data-services --timeout=300s
kubectl rollout status deployment/patient-data-worker -n temporal-workers --timeout=300s

Write-Host "Seeding synthetic patients through the Temporal pipeline..."
try { & "$Root\scripts\seed-data.ps1" } catch { Write-Host "Seeding skipped/failed - run .\scripts\seed-data.ps1 manually." }

Write-Host "Running verification..."
& "$Root\scripts\verify.ps1"

Write-Host ""
Write-Host "Setup complete."
Write-Host "  Dashboard    : http://127.0.0.1:30082/patient-services/dashboard"
Write-Host "  Temporal UI  : http://127.0.0.1:30080"
