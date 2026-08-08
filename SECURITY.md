# Security

This repository is a **public educational prototype**.

## What is included on purpose

- Local-only placeholder passwords (`temporal`, `local-only-change-me`)
- Synthetic patient JSON (no real PHI)
- Sanitized architecture notes from AKS discovery (no production connection strings)

## What is NOT included

- Azure credentials / Key Vault secrets
- Production Postgres passwords
- App Configuration connection strings
- ACR pull credentials
- Real patient data

## Guidance

1. Never commit `.env` files with real secrets.
2. Never run these scripts against AKS contexts (`qademo-platform-aks`, `qa-platform-rx-aks`).
3. Rotate any credential that was ever pasted into a private notes file before opening a public fork.

If you discover a sensitive value in this public repo, open an issue and rotate the credential immediately.
