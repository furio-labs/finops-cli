# Development

## Project Structure

```
finops/
├── pyproject.toml                    # Package metadata and dependencies
├── .python-version                   # pyenv version pin (3.12.x)
├── subscriptions.yaml.example        # Config template (copy → subscriptions.yaml)
├── .env.example                      # Credentials template (copy → .env)
├── finops/                           # Main package
│   ├── models.py                     # Shared data models (Severity, Finding, etc.)
│   ├── config.py                     # Config loading and validation
│   ├── auth.py                       # Azure credential resolution
│   ├── cli.py                        # Click CLI entrypoint
│   ├── collectors/                   # Azure API wrappers
│   │   ├── base.py                   # retry_on_throttle() helper
│   │   ├── cost.py                   # Azure Cost Management API
│   │   ├── resources.py              # Azure Resource Manager API
│   │   └── invoices.py               # Azure Billing API
│   ├── analyzers/                    # Cost-leak detectors
│   │   ├── base.py                   # Analyzer ABC
│   │   ├── untagged.py
│   │   ├── idle.py
│   │   ├── wrong_sku.py
│   │   ├── dev_in_prod.py
│   │   └── scheduling.py
│   └── reporters/                    # Output generators
│       ├── models.py                 # Report dataclass + JSON serialization
│       ├── html.py                   # Jinja2 HTML renderer
│       ├── markdown.py               # Markdown renderer
│       └── templates/report.html.j2 # HTML template
└── tests/
    ├── conftest.py                   # Shared fixtures (make_resource, make_cost, etc.)
    ├── collectors/                   # Unit tests with mocked Azure SDK
    ├── analyzers/                    # Unit tests with fixture data
    ├── reporters/                    # Snapshot tests + fixtures/data.json
    └── integration/                  # Live API tests (skipped by default)
```

## Running Tests

```bash
source .venv/bin/activate

# All unit tests
pytest

# Specific module
pytest tests/analyzers/test_idle.py -v

# With coverage
pip install pytest-cov
pytest --cov=finops --cov-report=term-missing
```

## Integration Tests

Integration tests make real Azure API calls. They are skipped by default.

```bash
export AZURE_TEST_SUBSCRIPTION_ID="your-subscription-id"
pytest tests/integration/ -v
```

Requires valid Azure credentials in `.env` or an active `az login` session.

## Architecture

The pipeline runs per subscription:

```
Config + Auth
    ↓
[ResourceCollector]  →  list[AzureResource]   ─┐
[CostCollector]      →  list[ResourceCost]     ─┤→ Analyzers → list[Finding]
[InvoiceCollector]   →  list[Invoice]          ─┘
                                                  ↓
                                           SubscriptionData
                                                  ↓
                                          Report (all subs)
                                                  ↓
                             report.html + report.md + data.json
```

## Key Design Decisions

**Collectors are stateless.** Each collector is called once per subscription and returns typed models. Results are held in memory for the run duration.

**Analyzers receive the same data.** Every analyzer gets `(subscription_id, resources, costs)`. They never call Azure APIs directly.

**Severity is an IntEnum.** `Severity.CRITICAL (4) > HIGH (3) > MEDIUM (2) > INFO (1)` — so `sorted(findings, key=lambda f: f.severity, reverse=True)` sorts CRITICAL first.

**JSON serialization handles Severity.** `report_to_json` converts `Severity` IntEnum instances to their name string (`"HIGH"`). `report_from_json` restores via `Severity["HIGH"]`.

**Retry on throttle only.** `retry_on_throttle()` in `collectors/base.py` retries only HTTP 429 responses with exponential backoff (5s, 10s, 20s). All other errors propagate.

## Adding a New Analyzer

See [analyzers.md](analyzers.md#adding-a-new-analyzer).

## Modifying the HTML Template

The template is at `finops/reporters/templates/report.html.j2`. It uses Jinja2 with `autoescape=True`.

Key variables available in the template:
- `report` — `Report` dataclass instance
- `report.subscriptions` — list of `SubscriptionData`
- `report.total_cost`, `report.total_estimated_savings`, `report.all_findings`
- `report.findings_by_severity()` — dict mapping severity name → list of findings
- Per subscription: `sub.resources`, `sub.costs`, `sub.invoices`, `sub.findings`, `sub.skipped`

After editing the template, re-render existing data without API calls:
```bash
finops report --from-cache ./reports/2026-05-07/
```

## Dependency Management

Dependencies are declared in `pyproject.toml`. To add a new one:

```bash
# Edit pyproject.toml, then reinstall
pip install -e ".[dev]"
```

There is no lock file — `pip install` resolves at install time. If you need reproducible builds, generate one:

```bash
pip freeze > requirements-lock.txt
```
