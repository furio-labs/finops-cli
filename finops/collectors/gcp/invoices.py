"""GCP invoice collector.

GCP has no programmatic invoice API comparable to Azure's BillingManagementClient:
the Cloud Billing API exposes budgets and cost data, but issued invoices live only
in the Console / are emailed. So this collector returns no invoices; GCP spend is
still fully captured via the BigQuery cost export (see cost.py)."""
from __future__ import annotations

from finops.models import Invoice


class InvoiceCollector:
    def __init__(self, credential) -> None:
        self._credential = credential

    def collect(self, project_id: str) -> list[Invoice]:
        return []
