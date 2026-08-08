$ErrorActionPreference = "Stop"

$ClusterName = if ($env:CLUSTER_NAME) { $env:CLUSTER_NAME } else { "temporal-local" }
$ans = Read-Host "Delete kind cluster '$ClusterName'? [y/N]"
if ($ans -match '^[Yy]$') {
  kind delete cluster --name $ClusterName
  Write-Host "Cluster deleted."
} else {
  Write-Host "Skipped cluster deletion."
}
