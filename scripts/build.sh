#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "Building Docker images..."
docker build -t temporal-local/patient-data-services:local patient-data-services/
docker build -t temporal-local/workflow-starter:local temporal-workflows/
docker build -f temporal-workers/Dockerfile -t temporal-local/patient-worker:local .

echo "Loading images into kind cluster temporal-local..."
kind load docker-image temporal-local/patient-data-services:local --name temporal-local
kind load docker-image temporal-local/workflow-starter:local --name temporal-local
kind load docker-image temporal-local/patient-worker:local --name temporal-local

echo "Build complete."
