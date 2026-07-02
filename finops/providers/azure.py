"""Azure provider: wraps the existing auth + collectors and translates Azure
SDK exceptions into the common provider taxonomy so the CLI stays cloud-agnostic."""
from __future__ import annotations
from azure.core.exceptions import HttpResponseError

from finops.auth import get_credential as _azure_get_credential
from finops.collectors.resources import ResourceCollector as _ResourceCollector
from finops.collectors.cost import CostCollector as _CostCollector
from finops.collectors.invoices import InvoiceCollector as _InvoiceCollector
from finops.providers import ProviderPermissionError, ProviderUnavailableError


def _translate(fn):
    try:
        return fn()
    except HttpResponseError as exc:
        status = getattr(exc, "status_code", None)
        if status == 403:
            raise ProviderPermissionError("Insufficient permissions (403)") from exc
        raise ProviderUnavailableError(f"API error: {status}") from exc


class _ResourceCollectorAdapter:
    def __init__(self, credential) -> None:
        self._inner = _ResourceCollector(credential)

    def collect(self, subscription_id):
        return _translate(lambda: self._inner.collect(subscription_id))


class _CostCollectorAdapter:
    def __init__(self, credential) -> None:
        self._inner = _CostCollector(credential)

    def collect(self, subscription_id, start_date, end_date, granularity="Daily"):
        return _translate(
            lambda: self._inner.collect(subscription_id, start_date, end_date, granularity)
        )


class _InvoiceCollectorAdapter:
    def __init__(self, credential) -> None:
        self._inner = _InvoiceCollector(credential)

    def collect(self, subscription_id):
        return _translate(lambda: self._inner.collect(subscription_id))


def build_credential(entry):
    credential, method = _azure_get_credential()
    return credential, method.value


def build_collectors(entry, credential):
    return (
        _ResourceCollectorAdapter(credential),
        _CostCollectorAdapter(credential),
        _InvoiceCollectorAdapter(credential),
    )
