# CLI Reference

## `finops run`

Analyze subscriptions and generate reports. Makes live Azure API calls.

```
finops run [OPTIONS]
```

| Option | Default | Description |
|---|---|---|
| `--config`, `-c` | `subscriptions.yaml` | Path to config file |
| `--subscriptions`, `-s` | *(all from config)* | Limit to specific subscription IDs (repeatable) |
| `--analyzers`, `-a` | *(all)* | Limit to specific analyzers (repeatable) |
| `--from` | First day of current month | Start date `YYYY-MM-DD` |
| `--to` | Today | End date `YYYY-MM-DD` |
| `--output`, `-o` | `./reports` | Output base directory |

### Examples

```bash
# Analyze all configured subscriptions, current month
finops run

# Analyze a specific subscription for a custom date range
finops run --subscriptions xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx \
           --from 2026-01-01 --to 2026-03-31

# Only run the untagged and idle analyzers
finops run --analyzers untagged --analyzers idle

# Write reports to a custom directory
finops run --output /tmp/finops-reports
```

### Output

Reports are written to `<output>/YYYY-MM-DD/`:

```
reports/
└── 2026-05-07/
    ├── report.html    # Full interactive report
    ├── report.md      # Markdown version
    └── data.json      # Raw data (for re-rendering)
```

Terminal summary after each run:

```
✓ Acme Production  — 142 recursos, $8,432.10, 7 hallazgos
✓ Minera XYZ      —  89 recursos, $3,211.44, 3 hallazgos

──────────────────────────────────
  CRITICAL   2   ~$1,200.00/mes
  HIGH       5   ~$430.00/mes
  MEDIUM     3   ~$90.00/mes
──────────────────────────────────
```

---

## `finops report`

Re-render HTML and Markdown reports from a cached `data.json` without making any Azure API calls.

```
finops report --from-cache <PATH> [--output <PATH>]
```

| Option | Default | Description |
|---|---|---|
| `--from-cache` | *(required)* | Directory containing `data.json` |
| `--output`, `-o` | Same as `--from-cache` | Directory to write `report.html` and `report.md` |

### Examples

```bash
# Re-render from a previous run
finops report --from-cache ./reports/2026-05-07/

# Re-render to a different directory
finops report --from-cache ./reports/2026-05-07/ --output ./reports/regenerated/
```

---

## `finops list-subscriptions`

List all subscriptions defined in the config file.

```
finops list-subscriptions [--config <PATH>]
```

### Example

```bash
finops list-subscriptions

# With a custom config
finops list-subscriptions --config /path/to/subscriptions.yaml
```

Output:

```
         Configured Subscriptions
┌────────────────────────────────────┬──────────────────┬──────────────────────────────────────┐
│ ID                                 │ Name             │ Tags                                 │
├────────────────────────────────────┼──────────────────┼──────────────────────────────────────┤
│ xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxx │ Acme Production   │ environment=production, client=acme   │
│ yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyy │ Minera XYZ       │ environment=production, client=minera│
└────────────────────────────────────┴──────────────────┴──────────────────────────────────────┘
```
