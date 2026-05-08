# Configuration

The tool reads `subscriptions.yaml` by default. Copy the example and fill in your values:

```bash
cp subscriptions.yaml.example subscriptions.yaml
```

`subscriptions.yaml` is gitignored — it may contain real subscription IDs and client names.

## Full Reference

```yaml
# One entry per Azure subscription to analyze
subscriptions:
  - id: "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"   # Azure Subscription ID (required)
    name: "Acme Corp Production"                     # Human-readable label (required)
    tags:                                          # Optional metadata for this subscription
      environment: production
      client: acme-corp

  - id: "yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy"
    name: "Contoso Staging"
    tags:
      environment: staging
      client: contoso

# Tags every resource should have. Resources missing any of these are flagged by UntaggedAnalyzer.
required_tags:
  - environment
  - client
  - service

# Thresholds used by specific analyzers
cost_thresholds:
  # Resources with avg daily cost <= this value are flagged as idle (USD)
  idle_resource_daily_usd: 0.10

  # Non-prod resources expected to run at most N hours/day.
  # Off-hours savings = avg_daily_cost × (24 - scheduling_hours_per_day)
  scheduling_hours_per_day: 8
```

## Using a Different Config File

```bash
finops run --config /path/to/other-subscriptions.yaml
```

## Overriding Subscriptions at Runtime

Analyze only specific subscriptions without editing the config:

```bash
finops run --subscriptions sub-id-1 --subscriptions sub-id-2
```

The `--subscriptions` flag filters to the given IDs — they must still be listed in the config file.
