# Analyzers

Each analyzer scans all resources in a subscription and emits `Finding` objects with a severity, category, estimated monthly savings (USD), and a recommendation in Spanish.

## Available Analyzers

| Name | `--analyzers` key | Severity | What it detects |
|---|---|---|---|
| [Untagged](#untagged) | `untagged` | HIGH | Resources missing required tags |
| [Idle](#idle) | `idle` | MEDIUM | Resources with near-zero cost every day |
| [WrongSku](#wrongsku) | `wrong_sku` | MEDIUM / HIGH | Premium tier where standard suffices |
| [DevInProd](#devinprod) | `dev_in_prod` | HIGH / MEDIUM | Dev SKUs in prod, or expensive SKUs in dev |
| [Scheduling](#scheduling) | `scheduling` | MEDIUM | Non-prod resources running 24/7 |

---

## Untagged

**Key:** `untagged` | **Severity:** HIGH | **Savings estimate:** $0 (governance issue)

Flags any resource missing one or more tags from `required_tags` in the config.

```yaml
required_tags:
  - environment
  - client
  - service
```

A resource tagged `{environment: production}` but missing `client` and `service` produces one finding listing both missing tags.

**Recommendation (Spanish):**
> Recurso sin etiquetas requeridas: client, service. Agregue las etiquetas para una correcta asignación de costos.

---

## Idle

**Key:** `idle` | **Severity:** MEDIUM | **Savings estimate:** total observed cost

Flags resources whose daily cost is below `idle_resource_daily_usd` (default: $0.10) on **every single day** of the analyzed period. A resource that spikes even one day is not flagged.

**Recommendation (Spanish):**
> Recurso con costo muy bajo ($0.0300/día). Considere eliminarlo si no está en uso activo.

**Threshold configuration:**
```yaml
cost_thresholds:
  idle_resource_daily_usd: 0.10
```

---

## WrongSku

**Key:** `wrong_sku` | **Severity:** MEDIUM or HIGH | **Savings estimate:** $0 (requires manual assessment)

Detects specific resource types using a more expensive tier than necessary:

| Resource type | Condition | Severity |
|---|---|---|
| `microsoft.storage/storageaccounts` | SKU tier is `Premium` | MEDIUM |
| `microsoft.dbforpostgresql/flexibleservers` | SKU tier is `BusinessCritical` | HIGH |

**Storage recommendation (Spanish):**
> Cuenta de almacenamiento usa SKU Premium. Evalúe migrar a Standard LRS para reducir costos si el rendimiento lo permite.

**PostgreSQL recommendation (Spanish):**
> PostgreSQL Flexible Server usa tier BusinessCritical. Si no requiere alta disponibilidad, considere migrar a GeneralPurpose.

---

## DevInProd

**Key:** `dev_in_prod` | **Severity:** HIGH (dev SKU in prod) or MEDIUM (expensive SKU in dev)

Detects environment/SKU mismatches for VMs, PostgreSQL Flexible Servers, and App Services:

**Prod environment + dev SKU → HIGH**
- Prod environment: `environment` tag is `production` or `prod`, or resource group name contains `prod`
- Dev SKU: tier is `Burstable`, `Basic`, `Free`, or `Shared`; or VM name starts with `Standard_B`

**Dev environment + expensive SKU → MEDIUM**
- Dev environment: `environment` tag is `dev`, `development`, `staging`, `test`, or `qa`; or resource group name contains one of those keywords
- Expensive SKU: VM name starts with `Standard_D`, `E`, `F`, `M`, or `N` series

Only checks: VMs (`microsoft.compute/virtualmachines`), PostgreSQL Flexible Servers (`microsoft.dbforpostgresql/flexibleservers`), App Services (`microsoft.web/sites`).

---

## Scheduling

**Key:** `scheduling` | **Severity:** MEDIUM | **Savings estimate:** `avg_daily_cost × (24 − scheduling_hours_per_day)`

Flags VMs, App Services, and VM Scale Sets in non-production environments that have cost entries for **every calendar day** of the analyzed period (including weekends), indicating they never shut down.

- Non-prod environments: `dev`, `development`, `staging`, `test`, `qa` (from `environment` tag or resource group name)
- Requires at least 7 consecutive days of cost data to flag

**Savings formula:** based on `scheduling_hours_per_day` config (default 8 hours/day). If the resource ran only 8 hours/day instead of 24, you'd save `avg_daily_cost × 16` per day.

**Recommendation (Spanish):**
> Recurso en entorno 'dev' está activo los 7 días de la semana. Configure un horario de apagado fuera de horas de trabajo para reducir costos.

**Threshold configuration:**
```yaml
cost_thresholds:
  scheduling_hours_per_day: 8   # expected daily runtime for non-prod resources
```

---

## Running Specific Analyzers

```bash
# Run only untagged and scheduling
finops run --analyzers untagged --analyzers scheduling

# Run only idle
finops run --analyzers idle
```

Valid keys: `untagged`, `idle`, `wrong_sku`, `dev_in_prod`, `scheduling`

---

## Adding a New Analyzer

1. Create `finops/finops/analyzers/my_analyzer.py`:

```python
from finops.analyzers.base import Analyzer
from finops.models import AzureResource, ResourceCost, Finding, Severity

class MyAnalyzer(Analyzer):
    @property
    def name(self) -> str:
        return "my_analyzer"

    def analyze(self, subscription_id, resources, costs):
        findings = []
        for resource in resources:
            # ... detection logic ...
            findings.append(Finding(
                subscription_id=subscription_id,
                resource_group=resource.resource_group,
                resource_id=resource.id,
                resource_type=resource.type,
                severity=Severity.MEDIUM,
                category="MyCategory",
                estimated_monthly_savings_usd=0.0,
                recommendation="Recomendación en español.",
            ))
        return findings
```

2. Register it in `finops/finops/cli.py`:

```python
from finops.analyzers.my_analyzer import MyAnalyzer

_ALL_ANALYZERS = {
    ...
    "my_analyzer": MyAnalyzer,
}
```

3. Write tests in `finops/tests/analyzers/test_my_analyzer.py`.
