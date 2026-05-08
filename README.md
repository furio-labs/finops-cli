# FinOps CLI

Azure cost analysis and optimization tool built by [Furio Labs](https://furiolabs.com). Queries Azure subscriptions, identifies cost leaks, and generates HTML, Markdown, and Excel reports.

## Quick Start

```bash
# 1. Clone and set up
cd finops
pyenv local 3.12.0
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# 2. Configure credentials
cp .env.example .env          # fill in Azure credentials
cp subscriptions.yaml.example subscriptions.yaml   # fill in subscription IDs

# 3. Run
finops run
```

Reports land in `./reports/YYYY-MM-DD/`.

## Documentation

| Doc | Description |
|---|---|
| [Installation](docs/installation.md) | Setup, credentials, Python version |
| [Configuration](docs/configuration.md) | subscriptions.yaml reference |
| [CLI Reference](docs/cli-reference.md) | All commands and flags |
| [Analyzers](docs/analyzers.md) | What each cost-leak detector checks |
| [Reports](docs/reports.md) | HTML, Markdown, and JSON output format |
| [Azure Permissions](docs/azure-permissions.md) | Required RBAC roles per subscription |
| [Development](docs/development.md) | Running tests, adding analyzers |

## Requirements

- Python 3.12+ (managed with pyenv)
- Azure subscription(s) with Cost Management Reader + Reader roles
- Either a Service Principal or `az login` session
