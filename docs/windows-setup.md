# Windows Setup — Kind Temporal Local POC

## Recommended stack

| Component | Notes |
|-----------|-------|
| Windows 10/11 | Pro or Home |
| Docker Desktop | **WSL2 backend** required |
| Kind | Creates `temporal-local` cluster |
| kubectl / Helm | Same as Linux |
| PowerShell 5.1+ or PowerShell 7+ | Scripts under `scripts/*.ps1` |

## Install tools

```powershell
winget install Docker.DockerDesktop
winget install Kubernetes.kubectl
winget install Kubernetes.kind
winget install Helm.Helm
winget install Git.Git
```

Restart the terminal after installs. Start **Docker Desktop** and wait until it shows Running.

## Run

```powershell
git clone https://github.com/naveenkumar-rhythmx/temporal-local-poc.git
cd temporal-local-poc
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\setup.ps1
.\scripts\verify.ps1
.\scripts\test-e2e.ps1
```

## Resource guidance

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| RAM for Docker | 6 GB | 8–12 GB |
| Disk | 20 GB free | 40 GB+ |
| CPUs | 2 | 4 |

Edit Docker Desktop → Settings → Resources if pods stay `Pending` or OOMKilled.

## Kind ports on Windows

`kind/cluster.yaml` maps:

| Host port | Service |
|-----------|---------|
| 30080 | Temporal Web UI |
| 30081 | Workflow starter |
| 30082 | Patient ingest API |

Open in browser: `http://127.0.0.1:30080`

## Alternative: WSL2 Ubuntu

If you prefer bash:

```bash
# Inside WSL, with Docker Desktop WSL integration enabled
cd /mnt/c/Users/<you>/path/to/temporal-local-poc
chmod +x scripts/*.sh
./scripts/setup.sh
```

Use the same Docker engine (Docker Desktop) from WSL.

## Common Windows issues

| Symptom | Fix |
|---------|-----|
| `kind: command not found` | Restart terminal; ensure install path is on `PATH` |
| `error during connect: docker` | Start Docker Desktop |
| Image pull timeouts | VPN/proxy; retry `.\scripts\build.ps1` |
| `execution of scripts is disabled` | `Set-ExecutionPolicy -Scope Process Bypass` |
| Port already in use | Stop other apps on 30080–30082 or change `kind/cluster.yaml` + Service `nodePort` |
| kubectl talks to AKS | `kubectl config use-context kind-temporal-local` |

## Cleanup

```powershell
.\scripts\cleanup.ps1
```
