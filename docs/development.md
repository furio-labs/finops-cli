# Development

## Project Structure

```
finops/
├── pyproject.toml                    # Package metadata, dependencies, dev group
├── uv.lock                           # Resolved dependency lock (committed)
├── .python-version                   # Python version pin (3.12.x), read by uv
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

`uv run` executes inside the project's virtualenv — no manual activation needed.

```bash
# All unit tests
uv run pytest

# Specific module
uv run pytest tests/analyzers/test_idle.py -v

# With coverage (pytest-cov is in the dev group)
uv run pytest --cov=finops --cov-report=term-missing
```

## Integration Tests

Integration tests make real Azure API calls. They are skipped by default.

```bash
export AZURE_TEST_SUBSCRIPTION_ID="your-subscription-id"
uv run pytest tests/integration/ -v
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
uv run finops report --from-cache ./reports/2026-05-07/
```

## Dependency Management

Dependencies are declared in `pyproject.toml` (`[project.dependencies]` for runtime,
`[dependency-groups].dev` for tooling). uv manages them:

```bash
# Add a runtime dependency
uv add azure-mgmt-monitor

# Add a dev-only dependency
uv add --dev pytest-cov

# Remove one
uv remove azure-mgmt-monitor
```

`uv.lock` is the resolved lock file and **is committed** — it pins exact versions for
reproducible installs. `uv sync` installs exactly what the lock specifies; `uv sync --upgrade`
re-resolves within the `pyproject.toml` constraints and updates the lock.

## Continuous Integration

`.github/workflows/ci.yml` runs on every pull request to `main`, on pushes to `main`,
and weekly (Mondays 06:00 UTC). Two jobs run in parallel:

- **test** — `uv sync --locked` (fails if `uv.lock` is out of sync with `pyproject.toml`)
  then `uv run pytest`.
- **audit** — `uv sync --locked` then `uv run --with pip-audit pip-audit --skip-editable`,
  which fails the build on any known CVE in the resolved dependency tree.

`.github/dependabot.yml` opens weekly PRs for the `uv` (Python deps) and `github-actions`
ecosystems; each PR re-runs the gate above.

### Silencing an unfixable vulnerability

If `audit` flags a CVE with no available fix (or a reviewed non-issue), append
`--ignore-vuln <GHSA-or-PYSEC-id>` to the `pip-audit` step in `ci.yml`, with a comment
stating the ID, date, and reason. Remove it once a fixed version is available.

### One-time repository settings (required to actually block merges)

The workflow files do not block merges by themselves — these GitHub settings do:

1. **Branch protection on `main`** requiring the `test` and `audit` checks. As a maintainer:
   ```bash
   cat > /tmp/protection.json <<'JSON'
   {
     "required_status_checks": { "strict": true, "contexts": ["test", "audit"] },
     "enforce_admins": true,
     "required_pull_request_reviews": null,
     "restrictions": null
   }
   JSON
   gh api -X PUT repos/furio-labs/finops-cli/branches/main/protection \
     -H "Accept: application/vnd.github+json" --input /tmp/protection.json
   ```
   (Or: Settings → Branches → Add rule → require status checks `test` and `audit`.)

2. **Dependabot alerts + security updates** (proactive fix PRs for vulnerable deps):
   ```bash
   gh api -X PUT repos/furio-labs/finops-cli/vulnerability-alerts
   gh api -X PUT repos/furio-labs/finops-cli/automated-security-fixes
   ```
   (Or: Settings → Code security → enable Dependabot alerts and security updates.)
