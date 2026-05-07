from __future__ import annotations
from azure.mgmt.billing import BillingManagementClient
from azure.core.exceptions import HttpResponseError
from finops.models import Invoice
from finops.collectors.base import retry_on_throttle

_NON_RETRIABLE_STATUSES = {403, 404, 422, 500, 501}


class InvoiceCollector:
    def __init__(self, credential) -> None:
        self._credential = credential

    def collect(self, subscription_id: str) -> list[Invoice]:
        try:
            client = BillingManagementClient(credential=self._credential, subscription_id=subscription_id)
            raw = retry_on_throttle(
                lambda: list(client.invoices.list_by_billing_subscription(subscription_id=subscription_id))
            )
        except HttpResponseError as exc:
            if getattr(exc, "status_code", None) in _NON_RETRIABLE_STATUSES:
                return []
            raise

        results = []
        for inv in raw:
            amount = inv.amount_due.amount if inv.amount_due else 0.0
            currency = inv.amount_due.currency if inv.amount_due else "USD"
            pdf_url = inv.invoice_pdf.url if inv.invoice_pdf else None
            results.append(Invoice(
                id=inv.id or "",
                name=inv.name or "",
                subscription_id=subscription_id,
                billing_period=inv.name or "",
                amount_due=amount,
                currency=currency,
                status=inv.status or "Unknown",
                due_date=str(inv.due_date) if inv.due_date else None,
                pdf_url=pdf_url,
            ))
        return results
