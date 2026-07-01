"""GCP provider: Application Default Credentials or a service-account JSON key,
shared by the BigQuery (cost) and Cloud Asset (resource) clients."""
from __future__ import annotations
import os

from finops.providers import ProviderUnavailableError

_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]


def build_credential(entry):
    """Return (credential, auth_method_label). Any auth failure becomes a
    ProviderUnavailableError so a misconfigured GCP entry is skipped, not fatal."""
    try:
        key_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if key_path:
            from google.oauth2 import service_account
            creds = service_account.Credentials.from_service_account_file(
                key_path, scopes=_SCOPES
            )
            return creds, "ServiceAccount"
        import google.auth
        creds, _ = google.auth.default(scopes=_SCOPES)
        return creds, "ADC"
    except Exception as exc:  # DefaultCredentialsError, missing/invalid key file, etc.
        raise ProviderUnavailableError(f"GCP auth failed: {exc}") from exc


def build_collectors(entry, credential):
    """Return (resource_collector, cost_collector, invoice_collector) for GCP."""
    from finops.collectors.gcp.resources import ResourceCollector
    from finops.collectors.gcp.cost import CostCollector
    from finops.collectors.gcp.invoices import InvoiceCollector
    return (
        ResourceCollector(credential),
        CostCollector(credential, entry),
        InvoiceCollector(credential),
    )
