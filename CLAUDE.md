# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

A Python CLI tool (`finops`) that queries Azure subscriptions, detects cost leaks, and generates HTML + Markdown reports. Recommendations are written in **Spanish**.

## Setup

```bash
# First time
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Credentials: either .env with service principal, or az login
cp .env.example .env         # set AZURE_TENANT_ID / AZURE_CLIENT_ID / AZURE_CLIENT_SECRET
cp subscriptions.yaml.example subscriptions.yaml
```

## Commands

```bash
# Full run (current month, all subscriptions)
finops run

# Narrow scope
finops run --analyzers idle --analyzers untagged --granularity monthly

# Re-render HTML/MD from cached data without API calls
finops report --from-cache ./reports/2026-05-07/

# List configured subscriptions
finops list-subscriptions
```

## Tests

```bash
# All unit tests
pytest

# Single file
pytest tests/analyzers/test_idle.py -v

# With coverage
pytest --cov=finops --cov-report=term-missing

# Integration tests (real Azure calls — requires AZURE_TEST_SUBSCRIPTION_ID env var)
pytest tests/integration/ -v
```

## Architecture

The pipeline runs per subscription:

```
Config (subscriptions.yaml) + Auth (.env or az login)
    ↓
ResourceCollector  →  list[AzureResource]   ─┐
CostCollector      →  list[ResourceCost]    ─┤→ Analyzers → list[Finding]
InvoiceCollector   →  list[Invoice]         ─┘
                                               ↓
                                        SubscriptionData
                                               ↓ (all subs)
                                           Report
                                               ↓
                            report.html + report.md + data.json
```

**Key invariants:**
- Collectors are stateless and return typed models; they never share state between subscriptions.
- Analyzers never call Azure APIs — they receive `(subscription_id, resources, costs)` and return `list[Finding]`.
- `Severity` is an `IntEnum` (`CRITICAL=4 > HIGH=3 > MEDIUM=2 > INFO=1`), so `sorted(findings, key=lambda f: f.severity, reverse=True)` sorts CRITICAL first.
- `retry_on_throttle()` in `collectors/base.py` retries only HTTP 429 with exponential backoff (5s, 10s, 20s). All other errors propagate immediately.
- Auth resolves automatically: if `AZURE_TENANT_ID/CLIENT_ID/CLIENT_SECRET` are set, uses `ClientSecretCredential`; otherwise falls back to `AzureCliCredential` (az login).

## Adding an Analyzer

1. Create `finops/analyzers/my_analyzer.py` subclassing `Analyzer` (see `analyzers/base.py`).
2. Register it in `_ALL_ANALYZERS` dict in `finops/cli.py`.
3. Write tests in `tests/analyzers/test_my_analyzer.py` using `make_resource` / `make_cost` from `tests/conftest.py`.
4. Recommendations must be written in Spanish.

## HTML Template

The Jinja2 template lives at `finops/reporters/templates/report.html.j2`. After editing it, re-render without API calls:

```bash
finops report --from-cache ./reports/2026-05-07/
```

Key template variables: `report`, `report.subscriptions`, `report.total_cost`, `report.total_estimated_savings`, `report.all_findings`, `report.findings_by_severity()`.

## Configuration Reference (`subscriptions.yaml`)

```yaml
subscriptions:
  - id: "uuid"
    name: "Client Name"
    tags:
      environment: production

required_tags:        # Tags every resource must have (untagged analyzer)
  - environment
  - client
  - service

cost_thresholds:
  idle_resource_daily_usd: 0.10   # Below this every day → idle finding
  scheduling_hours_per_day: 8     # Expected runtime for non-prod (scheduling savings estimate)
```
