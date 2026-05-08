# Excel Report Improvements — Design Spec

**Date:** 2026-05-07
**Status:** Approved

## Overview

Improve the existing `report.xlsx` with consistent formatting across all sheets, and add two new sheets: Resource Evolution and Marketplace. Sheet count goes from 4 to 6.

## Sheet Order

1. Summary
2. Findings
3. Resource Evolution *(new)*
4. Costs by Resource Group
5. Marketplace *(new)*
6. Invoices

## Formatting Improvements (all sheets)

Applied uniformly across every sheet:

| Element | Spec |
|---|---|
| Header background | Dark teal `1F5C6B`, white bold text |
| Column widths | Auto-sized from header + data content, capped at 60 chars |
| USD columns | `#,##0.00` number format — enables sorting and pivot |
| Auto-filter | All columns |
| Freeze pane | Below row 1 |

Tab colors:
| Sheet | Color |
|---|---|
| Summary | Blue `2E75B6` |
| Findings | Red `C00000` |
| Resource Evolution | Green `375623` |
| Costs by Resource Group | Olive `4A7B5A` |
| Marketplace | Purple `7030A0` |
| Invoices | Grey `595959` |

## New Sheet: Resource Evolution

One row per Azure resource (marketplace excluded) per subscription, sorted by Total descending within each subscription. Reuses the aggregation logic from `_monthly_evolution()` in `finops/reporters/html.py`.

Month columns are the union of all months across all subscriptions (ascending). A resource with no cost in a given month shows `0`.

| Column | Source |
|---|---|
| Subscription | `sub.subscription_name` |
| Resource Group | `cost.resource_group` |
| Resource | last segment of `cost.resource_id` |
| Type | last segment of `cost.resource_type` |
| 2026-04, 2026-05, … | sum of daily costs for that month |
| Total (USD) | sum across all months |

USD format on all month and Total columns. Skipped subscriptions produce no rows.

## New Sheet: Marketplace

One row per marketplace resource per subscription, sorted by Total descending. Reuses aggregation logic from `_marketplace_section()` in `finops/reporters/html.py`. Sheet always exists with headers; subscriptions with no marketplace resources produce no rows.

| Column | Source |
|---|---|
| Subscription | `sub.subscription_name` |
| Resource Group | `cost.resource_group` |
| Service Name | parsed via `_parse_service_name()` (same logic as html.py) |
| Resource Type | last segment of `cost.resource_type` |
| 2026-04, 2026-05, … | sum of daily costs for that month |
| Total (USD) | sum across all months |
| % of Sub | `resource_total / subscription_total` (ratio 0–1, e.g. `0.15`) |

USD format on cost columns, `0.00%` format on `% of Sub` (Excel multiplies by 100 automatically). Skipped subscriptions produce no rows.

## Implementation Notes

- Extract shared helpers (`_all_months`, `_set_column_widths`, `_style_header`) into `excel.py` to avoid repetition across six sheet methods.
- `_parse_service_name()` is already in `html.py` — copy it into `excel.py` (or move to a shared `reporters/utils.py` if it grows).
- Auto-width measurement: iterate all cells in each column, take `max(len(str(cell.value or "")))`, add 2 padding, cap at 60.

## Testing

Add to `tests/reporters/test_excel.py`:
- Sheet names include `"Resource Evolution"` and `"Marketplace"` in correct order
- Resource Evolution headers include dynamic month column and `"Total (USD)"`
- Resource Evolution has correct row count (one per Azure non-marketplace resource)
- Marketplace headers include `"Service Name"` and `"% of Sub"`
- Marketplace is empty (headers only) when no marketplace resources exist
- Header row cell fill is teal on at least one sheet (spot-check)
- Tab color spot-check on Summary sheet

## Files Changed

| File | Change |
|---|---|
| `finops/reporters/excel.py` | Add 2 new sheet methods, formatting helpers, apply formatting to all sheets |
| `tests/reporters/test_excel.py` | Add tests for new sheets and formatting |
| `tests/reporters/fixtures/data.json` | Add a marketplace cost entry to enable Marketplace sheet tests |
