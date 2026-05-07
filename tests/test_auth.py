import os
import pytest
from unittest.mock import patch, MagicMock
from finops.auth import get_credential, AuthMethod


def test_returns_sp_credential_when_env_vars_set(monkeypatch):
    monkeypatch.setenv("AZURE_TENANT_ID", "tenant")
    monkeypatch.setenv("AZURE_CLIENT_ID", "client")
    monkeypatch.setenv("AZURE_CLIENT_SECRET", "secret")
    with patch("finops.auth.ClientSecretCredential") as mock_sp:
        mock_sp.return_value = MagicMock()
        cred, method = get_credential()
        mock_sp.assert_called_once_with(
            tenant_id="tenant", client_id="client", client_secret="secret"
        )
        assert method == AuthMethod.SERVICE_PRINCIPAL


def test_falls_back_to_az_cli_when_no_env_vars(monkeypatch):
    for var in ("AZURE_TENANT_ID", "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET"):
        monkeypatch.delenv(var, raising=False)
    with patch("finops.auth.AzureCliCredential") as mock_cli:
        mock_cli.return_value = MagicMock()
        cred, method = get_credential()
        mock_cli.assert_called_once()
        assert method == AuthMethod.AZURE_CLI
