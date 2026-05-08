from __future__ import annotations
from datetime import date
from collections import Counter
from finops.models import SubscriptionData

_SYSTEM = (
    "Eres un experto en FinOps especializado en optimización de costos de Azure. "
    "Analiza los datos de la suscripción y responde ÚNICAMENTE con un array JSON válido. "
    "Todos los campos 'detail' deben estar en español."
)

_OUTPUT_SCHEMA = """
Responde con un array JSON con este esquema exacto (sin texto adicional):
[
  {
    "title": "título corto en español",
    "category": "ResourceAnalysis|CostAnomaly|Recommendation|MoneyLeak",
    "detail": "explicación detallada en español",
    "estimated_monthly_savings_usd": 0.0,
    "confidence": "high|medium|low"
  }
]
"""

_TOP_N = 15


def build_prompt(sub: SubscriptionData, date_from: date, date_to: date) -> str:
    lines: list[str] = []
    lines.append(_SYSTEM)
    lines.append("")
    lines.append(f"Suscripción: {sub.subscription_name}")
    lines.append(f"Período: {date_from} → {date_to}")
    lines.append(f"Costo total: ${sub.total_cost:,.2f} USD")
    lines.append("")

    # Resource inventory by type
    type_counts = Counter(r.type for r in sub.resources)
    lines.append("## Inventario de recursos por tipo")
    for rtype, count in type_counts.most_common():
        lines.append(f"  {count}x {rtype}")
    lines.append("")

    # Top N costliest resources
    top = sorted(sub.costs, key=lambda c: c.total_cost, reverse=True)[:_TOP_N]
    lines.append(f"## Top {len(top)} recursos por costo")
    resource_meta = {r.id.lower(): r for r in sub.resources}
    for c in top:
        res = resource_meta.get(c.resource_id.lower())
        sku = f" [{res.sku_name}/{res.sku_tier}]" if res and (res.sku_name or res.sku_tier) else ""
        env_tag = (res.tags or {}).get("environment", "") if res else ""
        env = f" env={env_tag}" if env_tag else ""
        lines.append(
            f"  ${c.total_cost:,.2f} | {c.resource_id.split('/')[-1]} "
            f"| {c.resource_type.split('/')[-1]}{sku}{env} | RG={c.resource_group}"
        )
    lines.append("")

    # Monthly cost trend
    monthly: dict[str, float] = {}
    for c in sub.costs:
        for day, amt in c.daily_costs.items():
            m = day[:7]
            monthly[m] = monthly.get(m, 0.0) + amt
    if monthly:
        lines.append("## Tendencia mensual de costos")
        for m in sorted(monthly):
            lines.append(f"  {m}: ${monthly[m]:,.2f}")
        lines.append("")

    # Existing rule-based findings (categories only, to avoid duplication)
    if sub.findings:
        cats = sorted({f.category for f in sub.findings})
        lines.append("## Hallazgos existentes (reglas)")
        lines.append(f"  {', '.join(cats)}")
        lines.append("  (No dupliques estos hallazgos en tu respuesta.)")
        lines.append("")

    lines.append(_OUTPUT_SCHEMA)
    return "\n".join(lines)
