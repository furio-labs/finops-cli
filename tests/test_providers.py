import pytest
from unittest.mock import MagicMock, patch
from azure.core.exceptions import HttpResponseError
from finops.config import AzureEntry, GcpEntry
from finops.providers import (
    get_collectors,
    ProviderPermissionError,
    ProviderUnavailableError,
)
from finops.providers import gcp as gcp_provider


def _gcp_entry():
    return GcpEntry(
        provider="gcp", id="proj", name="Proj",
        billing_account_id="0123AB-4567CD-89EF01",
        billing_export_dataset="billing_export",
    )


def _azure_entry():
    return AzureEntry(id="sub1", name="Sub")


def test_get_collectors_dispatches_to_azure_adapters():
    res, cost, inv = get_collectors(_azure_entry(), MagicMock())
    assert hasattr(res, "collect")
    assert hasattr(cost, "collect")
    assert hasattr(inv, "collect")


def test_azure_adapter_translates_403_to_permission_error():
    res, _, _ = get_collectors(_azure_entry(), MagicMock())
    err = HttpResponseError()
    err.status_code = 403
    with patch.object(res, "_inner") as inner:
        inner.collect.side_effect = err
        with pytest.raises(ProviderPermissionError):
            res.collect("sub1")


def test_azure_adapter_translates_other_http_error_to_unavailable():
    res, _, _ = get_collectors(_azure_entry(), MagicMock())
    err = HttpResponseError()
    err.status_code = 500
    with patch.object(res, "_inner") as inner:
        inner.collect.side_effect = err
        with pytest.raises(ProviderUnavailableError):
            res.collect("sub1")


def test_gcp_build_credential_bad_key_path_raises_unavailable(monkeypatch):
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/nonexistent/key.json")
    with pytest.raises(ProviderUnavailableError):
        gcp_provider.build_credential(_gcp_entry())


def test_gcp_build_credential_service_account(monkeypatch):
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/some/key.json")
    fake_creds = object()
    with patch(
        "google.oauth2.service_account.Credentials.from_service_account_file",
        return_value=fake_creds,
    ):
        creds, label = gcp_provider.build_credential(_gcp_entry())
    assert creds is fake_creds
    assert label == "ServiceAccount"
