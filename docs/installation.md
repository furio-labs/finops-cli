# Installation

## Prerequisites

- [pyenv](https://github.com/pyenv/pyenv) for Python version management
- Python 3.12 installed via pyenv
- Azure CLI (`az`) for interactive login (optional if using a Service Principal)

## Setup

```bash
# 1. Set Python version (pyenv reads .python-version automatically)
cd finops
pyenv install 3.12.12   # if not already installed
pyenv local 3.12.12

# 2. Create virtualenv and install
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 3. Verify
finops --help
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
source .venv/bin/activate
pip install -e ".[dev]" --upgrade
```
