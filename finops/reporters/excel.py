from __future__ import annotations
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

from finops.reporters.models import Report
from finops.models import Severity

_SEVERITY_COLORS = {
    "CRITICAL": "FF0000",
    "HIGH": "FF8C00",
    "MEDIUM": "FFD700",
    "INFO": "C0C0C0",
}

_BOLD = Font(bold=True)


def _freeze_and_filter(ws) -> None:
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions


def _header(ws, values: list[str]) -> None:
    ws.append(values)
    for cell in ws[1]:
        cell.font = _BOLD


class ExcelReporter:
    def render(self, report: Report) -> bytes:
        wb = Workbook()
        wb.remove(wb.active)

        self._summary(wb, report)
        self._findings(wb, report)
        self._costs_by_rg(wb, report)
        self._invoices(wb, report)

        buf = BytesIO()
        wb.save(buf)
        return buf.getvalue()

    def _summary(self, wb: Workbook, report: Report) -> None:
        ws = wb.create_sheet("Summary")
        _header(ws, [
            "Subscription", "Total Cost (USD)",
            "CRITICAL", "HIGH", "MEDIUM", "INFO",
            "Est. Savings/mo (USD)", "Skipped",
        ])
        for sub in report.subscriptions:
            by_sev = {s.name: 0 for s in Severity}
            for f in sub.findings:
                by_sev[f.severity.name] += 1
            ws.append([
                sub.subscription_name,
                sub.total_cost,
                by_sev["CRITICAL"],
                by_sev["HIGH"],
                by_sev["MEDIUM"],
                by_sev["INFO"],
                sum(f.estimated_monthly_savings_usd for f in sub.findings),
                sub.skipped,
            ])
        _freeze_and_filter(ws)

    def _findings(self, wb: Workbook, report: Report) -> None:
        ws = wb.create_sheet("Findings")
        _header(ws, [
            "Subscription", "Resource Group", "Resource", "Type",
            "Severity", "Category", "Est. Savings/mo (USD)", "Recommendation",
        ])
        severity_col = 5
        for sub in report.subscriptions:
            if sub.skipped:
                continue
            for f in sorted(sub.findings, key=lambda x: x.severity, reverse=True):
                ws.append([
                    sub.subscription_name,
                    f.resource_group,
                    f.resource_id.split("/")[-1],
                    f.resource_type,
                    f.severity.name,
                    f.category,
                    f.estimated_monthly_savings_usd,
                    f.recommendation,
                ])
                color = _SEVERITY_COLORS.get(f.severity.name, "FFFFFF")
                ws.cell(ws.max_row, severity_col).fill = PatternFill(
                    start_color=color, end_color=color, fill_type="solid"
                )
        _freeze_and_filter(ws)

    def _costs_by_rg(self, wb: Workbook, report: Report) -> None:
        ws = wb.create_sheet("Costs by Resource Group")

        # Collect all months across all subscriptions (union)
        all_months: set[str] = set()
        for sub in report.subscriptions:
            if sub.skipped:
                continue
            for c in sub.costs:
                for day in c.daily_costs:
                    all_months.add(day[:7])
        months = sorted(all_months)

        _header(ws, ["Subscription", "Resource Group"] + months + ["Total (USD)"])

        for sub in report.subscriptions:
            if sub.skipped:
                continue
            rg_map: dict[str, dict[str, float]] = {}
            for c in sub.costs:
                rg = c.resource_group or "(sin grupo)"
                if rg not in rg_map:
                    rg_map[rg] = {}
                for day, amt in c.daily_costs.items():
                    m = day[:7]
                    rg_map[rg][m] = rg_map[rg].get(m, 0.0) + amt
            for rg, monthly in sorted(rg_map.items()):
                month_values = [monthly.get(m, 0.0) for m in months]
                ws.append([sub.subscription_name, rg] + month_values + [sum(month_values)])

        _freeze_and_filter(ws)

    def _invoices(self, wb: Workbook, report: Report) -> None:
        ws = wb.create_sheet("Invoices")
        _header(ws, ["Subscription", "Billing Period", "Amount Due (USD)", "Currency", "Status"])
        for sub in report.subscriptions:
            if sub.skipped:
                continue
            for inv in sub.invoices:
                ws.append([
                    sub.subscription_name,
                    inv.billing_period,
                    inv.amount_due,
                    inv.currency,
                    inv.status,
                ])
        _freeze_and_filter(ws)
