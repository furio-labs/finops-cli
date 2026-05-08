# Excel Export — Design Spec

**Date:** 2026-05-07
**Status:** Approved

## Overview

Add an Excel (`.xlsx`) export to the finops report pipeline. The workbook is generated alongside the existing `report.html`, `report.md`, and `data.json` outputs. It serves two audiences: finance/management (executive summary) and engineers (filterable findings triage).

## Architecture

A new `ExcelReporter` class in `finops/reporters/excel.py` follows the existing reporter pattern. It returns `bytes` instead of `str` because Excel is a binary format.

```python
class ExcelReporter:
    def render(self, report: Report) -> bytes: ...
```

`_write_reports()` in `finops/cli.py` gets one new line:

```python
(out_dir / "report.xlsx").write_bytes(ExcelReporter().render(report))
```

The `finops report` re-render command picks this up automatically since it already calls `_write_reports()`.

`openpyxl` is added to `dependencies` in `pyproject.toml`.

## Sheets

Four sheets, in this order:

### 1. Summary

One row per subscription.

| Column | Source |
|---|---|
| Subscription | `sub.subscription_name` |
| Total Cost (USD) | `sub.total_cost` |
| CRITICAL | count of findings with `severity == CRITICAL` |
| HIGH | count |
| MEDIUM | count |
| INFO | count |
| Est. Savings/mo (USD) | sum of `finding.estimated_monthly_savings_usd` |
| Skipped | `sub.skipped` |

### 2. Findings

One row per finding, sorted CRITICAL → INFO. Skipped subscriptions produce no rows.

| Column | Source |
|---|---|
| Subscription | `sub.subscription_name` |
| Resource Group | `finding.resource_group` |
| Resource | last segment of `finding.resource_id` |
| Type | `finding.resource_type` |
| Severity | `finding.severity.name` |
| Category | `finding.category` |
| Est. Savings/mo (USD) | `finding.estimated_monthly_savings_usd` |
| Recommendation | `finding.recommendation` |

Severity cell fill colors:
- CRITICAL → red (`FF0000`)
- HIGH → orange (`FF8C00`)
- MEDIUM → yellow (`FFD700`)
- INFO → grey (`C0C0C0`)

### 3. Costs by Resource Group

One row per resource group per subscription. Month columns are dynamic — one column per calendar month present across **all subscriptions** (union), in ascending order. Skipped subscriptions produce no rows. A RG with no cost for a given month shows `0`.

| Column | Source |
|---|---|
| Subscription | `sub.subscription_name` |
| Resource Group | resource group name |
| 2026-04, 2026-05, … | sum of daily costs for that month |
| Total (USD) | sum across all months |

### 4. Invoices

One row per invoice. Skipped subscriptions produce no rows.

| Column | Source |
|---|---|
| Subscription | `sub.subscription_name` |
| Billing Period | `invoice.billing_period` |
| Amount Due (USD) | `invoice.amount_due` |
| Currency | `invoice.currency` |
| Status | `invoice.status` |

## Formatting (all sheets)

- Header row: bold, frozen (freeze pane below row 1)
- Auto-filter on all columns
- Findings sheet: `PatternFill` on the Severity cell per row

## Testing

`tests/reporters/test_excel.py` using `openpyxl.load_workbook(BytesIO(bytes_output))`.

Coverage:
- Correct sheet names and order
- Header rows match expected columns exactly
- Correct row count per sheet
- Severity cell fill colors on Findings sheet
- Skipped subscriptions: appear in Summary (`Skipped=True`), absent from Findings / Costs / Invoices

Uses `make_resource`, `make_cost`, `make_finding` fixtures from `tests/conftest.py`.

## Files Changed

| File | Change |
|---|---|
| `pyproject.toml` | add `openpyxl>=3.1` to `dependencies` |
| `finops/reporters/excel.py` | new — `ExcelReporter` |
| `finops/reporters/__init__.py` | no change needed |
| `finops/cli.py` | add `write_bytes` call in `_write_reports()` |
| `tests/reporters/test_excel.py` | new — unit tests |
| `CLAUDE.md` | note `report.xlsx` in output list |
