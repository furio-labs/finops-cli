# Installation

## Prerequisites

- [uv](https://docs.astral.sh/uv/) for Python and dependency management (install: `curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Azure CLI (`az`) for interactive login (optional if using a Service Principal)

uv reads `.python-version` and installs the pinned Python 3.12 automatically — no separate Python install step is needed.

## Setup

```bash
# 1. Create the virtualenv and install the project + dev dependencies.
#    uv reads .python-version, fetches Python 3.12 if missing, and writes .venv/.
cd finops
uv sync

# 2. Verify
uv run finops --help
```

## Authentication

The CLI tries credentials in this order:

1. **Service Principal** — if all three env vars are set:
   ```
   AZURE_TENANT_ID
   AZURE_CLIENT_ID
   AZURE_CLIENT_SECRET
   ```
2. **Azure CLI** — falls back to the token from `az login`

### Service Principal (recommended for automation)

```bash
cp .env.example .env
# Edit .env with your SP credentials
```

The `.env` file is gitignored. Never commit it.

### Azure CLI (recommended for local dev)

```bash
az login
# No .env needed — the CLI picks up the session token
```

## Upgrading

```bash
# Upgrade dependencies within the constraints in pyproject.toml and refresh uv.lock
uv sync --upgrade
```
