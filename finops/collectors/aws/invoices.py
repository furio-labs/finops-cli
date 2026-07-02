"""AWS invoice collector.

There is no invoice-listing API in the standard AWS SDK comparable to Azure's
BillingManagementClient (AWS invoices/settlements live in the Billing
Console, or the Invoicing API which is a separate opt-in service). So this
collector returns no invoices; AWS spend is still fully captured via Cost
Explorer (see cost.py)."""
from __future__ import annotations

from finops.models import Invoice


class InvoiceCollector:
    def __init__(self, credential) -> None:
        self._credential = credential

    def collect(self, account_id: str) -> list[Invoice]:
        return []
