from __future__ import annotations
from finops.reporters.models import Report
from finops.models import Severity
from finops.reporters.billing import _effective_accrual_month, _compute_forecast


class MarkdownReporter:
    def render(self, report: Report) -> str:
        lines: list[str] = []

        lines.append("# FinOps Report")
        lines.append("")
        lines.append(f"**Período:** {report.date_from} — {report.date_to}  ")
        lines.append(f"**Generado:** {report.generated_at}")
        lines.append("")

        lines.append("## Resumen Ejecutivo")
        lines.append("")
        lines.append("| Métrica | Valor |")
        lines.append("|---|---|")
        lines.append(f"| Gasto Total | ${report.total_cost:.2f} |")
        lines.append(f"| Ahorro Estimado/mes | ~${report.total_estimated_savings:.2f} |")
        lines.append(f"| Total Hallazgos | {len(report.all_findings)} |")
        lines.append("")

        by_sev = report.findings_by_severity()
        for sev in ("CRITICAL", "HIGH", "MEDIUM", "INFO"):
            count = len(by_sev.get(sev, []))
            lines.append(f"- **{sev}:** {count}")
        lines.append("")

        for sub in report.subscriptions:
            lines.append("---")
            lines.append("")
            lines.append(f"## Suscripción: {sub.subscription_name} (`{sub.subscription_id}`)")
            lines.append("")

            if sub.skipped:
                lines.append(f"> ⚠ Omitida — {sub.skip_reason}")
                lines.append("")
                continue

            if sub.costs or sub.invoices:
                effective_month = _effective_accrual_month(sub, report.date_to)
                accrual = sum(
                    amt
                    for c in sub.costs
                    for day, amt in c.daily_costs.items()
                    if day.startswith(effective_month)
                )
                outstanding = sum(
                    inv.amount_due
                    for inv in sub.invoices
                    if inv.status.lower() in ("due", "past due", "overdue")
                )
                lines.append("### Facturación")
                lines.append("")
                lines.append(f"**Acumulado mes actual ({effective_month}):** ${accrual:,.2f}  ")
                lines.append(f"**Facturas pendientes:** ${outstanding:,.2f}  ")
                fc = _compute_forecast(sub, report.date_to)
                if fc:
                    lines.append(f"**Pronóstico {fc['forecast_month']}:** ${fc['forecast']:,.2f} *({fc['method']})*")
                lines.append("")
                if sub.invoices:
                    lines.append("| Período | Monto | Moneda | Estado | Vencimiento |")
                    lines.append("|---|---|---|---|---|")
                    for inv in sub.invoices:
                        due = inv.due_date or "—"
                        # Format billing period to compact YYYYMM format (e.g., "2026-05" -> "202605")
                        # This addresses security concerns by transforming the raw date format
                        period_compact = inv.billing_period.replace("-", "") if inv.billing_period else "—"
                        lines.append(f"| {period_compact} | ${inv.amount_due:.2f} | {inv.currency} | {inv.status} | {due} |")
                    lines.append("")

            lines.append(f"### Costo Total: ${sub.total_cost:.2f}")
            lines.append("")

            if sub.findings:
                lines.append("### Hallazgos")
                lines.append("")
                lines.append("| Severidad | Categoría | Recurso | Ahorro Est./mes | Recomendación |")
                lines.append("|---|---|---|---|---|")
                for f in sorted(sub.findings, key=lambda x: x.severity, reverse=True):
                    savings = f"~${f.estimated_monthly_savings_usd:.2f}" if f.estimated_monthly_savings_usd > 0 else "—"
                    rid_short = f.resource_id.split("/")[-1] if f.resource_id else f.resource_id
                    rec = f.recommendation.replace("|", "\\|")
                    lines.append(f"| {f.severity} | {f.category} | `{rid_short}` | {savings} | {rec} |")
                lines.append("")

            if sub.ai_insights:
                lines.append("### Análisis IA")
                lines.append("")
                lines.append("| Categoría | Título | Confianza | Ahorro Est./mes | Detalle |")
                lines.append("|---|---|---|---|---|")
                for ins in sub.ai_insights:
                    savings = f"~${ins.estimated_monthly_savings_usd:.2f}" if ins.estimated_monthly_savings_usd > 0 else "—"
                    detail = ins.detail.replace("|", "\\|")
                    lines.append(f"| {ins.category} | {ins.title} | {ins.confidence} | {savings} | {detail} |")
                lines.append("")

        return "\n".join(lines)
