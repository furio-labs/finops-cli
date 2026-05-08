# Reports

Each `finops run` writes three files to `<output>/YYYY-MM-DD/`:

```
reports/
└── 2026-05-07/
    ├── report.html    # Interactive HTML report
    ├── report.md      # Flat Markdown (for Jira, Confluence, GitHub Issues)
    └── data.json      # Raw structured data (enables re-rendering)
```

---

## HTML Report

Open `report.html` in any browser. No server required — fully self-contained with inline CSS and JavaScript.

### Sections (top → bottom)

**Executive Summary**
- Total spend for the period
- Total estimated monthly savings identified
- Finding counts by severity (CRITICAL / HIGH / MEDIUM / INFO)
- Date range analyzed

**Facturas (Invoices)**
Table of billing invoices with period, amount, currency, status, and PDF download link.

**Costos por Resource Group**
Per-subscription breakdown: resource group name, total cost, resource count.

**Hallazgos (Findings)**
Filterable, sortable table of all findings:
- Filter by free text (resource name, recommendation)
- Filter by severity
- Shows: severity badge, category, resource ID, estimated savings, Spanish recommendation

**Detalle por Recurso (Per-Resource Detail)**
Per resource group: each resource with its individual cost and any attached finding badges.

---

## Markdown Report

Same structure as HTML, rendered as flat Markdown. Paste directly into:
- Jira issue descriptions
- Confluence pages
- GitHub issues or PRs
- Slack (with Markdown rendering enabled)

---

## data.json

Machine-readable cache of the full run. Schema:

```json
{
  "generated_at": "2026-05-07T10:00:00Z",
  "date_from": "2026-05-01",
  "date_to": "2026-05-07",
  "subscriptions": [
    {
      "subscription_id": "xxxxxxxx-...",
      "subscription_name": "Acme Corp Production",
      "skipped": false,
      "skip_reason": null,
      "resources": [ { "id": "...", "name": "...", "type": "...", ... } ],
      "costs": [ { "resource_id": "...", "daily_costs": {"2026-05-01": 5.0, ...}, ... } ],
      "invoices": [ { "billing_period": "202605", "amount_due": 1500.0, ... } ],
      "findings": [
        {
          "severity": "HIGH",
          "category": "Untagged",
          "resource_id": "...",
          "estimated_monthly_savings_usd": 0.0,
          "recommendation": "Recurso sin etiquetas requeridas...",
          "metadata": { "missing_tags": ["service"] }
        }
      ]
    }
  ]
}
```

### Re-rendering from cache

Re-generate HTML and Markdown from a previous run without any Azure API calls:

```bash
finops report --from-cache ./reports/2026-05-07/
```

Useful when:
- You want to share a report after changing the template
- You want to regenerate Markdown only
- Azure API is temporarily unavailable

---

## Skipped Subscriptions

If a subscription returns 403 (insufficient permissions) or another API error, it appears in the report as:

```
⚠ Omitida — Insufficient permissions (403)
```

The subscription is still included in `data.json` with `"skipped": true`.
