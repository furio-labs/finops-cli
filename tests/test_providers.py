import pytest
from unittest.mock import MagicMock, patch
from azure.core.exceptions import HttpResponseError
from finops.config import AzureEntry, GcpEntry, AwsEntry
from finops.providers import (
    get_collectors,
    ProviderPermissionError,
    ProviderUnavailableError,
)
from finops.providers import gcp as gcp_provider
from finops.providers import aws as aws_provider


def _gcp_entry():
    return GcpEntry(
        provider="gcp", id="proj", name="Proj",
        billing_account_id="0123AB-4567CD-89EF01",
        billing_export_dataset="billing_export",
    )


def _azure_entry():
    return AzureEntry(id="sub1", name="Sub")


def _aws_entry(role_arn=""):
    return AwsEntry(provider="aws", id="123456789012", name="AWS", role_arn=role_arn)


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


def test_get_collectors_dispatches_to_aws_collectors():
    res, cost, inv = get_collectors(_aws_entry(), MagicMock())
    assert hasattr(res, "collect")
    assert hasattr(cost, "collect")
    assert hasattr(inv, "collect")


def test_aws_build_credential_default_chain_no_env(monkeypatch):
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
    session, label = aws_provider.build_credential(_aws_entry())
    assert label == "DefaultChain"
    assert session.region_name == "us-east-1"


def test_aws_build_credential_access_key(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIA...")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret")
    _, label = aws_provider.build_credential(_aws_entry())
    assert label == "AccessKey"


def test_aws_build_credential_assumes_role():
    fake_session = MagicMock()
    fake_sts = MagicMock()
    fake_sts.assume_role.return_value = {
        "Credentials": {
            "AccessKeyId": "AKIA...",
            "SecretAccessKey": "secret",
            "SessionToken": "token",
        }
    }
    fake_session.client.return_value = fake_sts
    with patch("boto3.Session", return_value=fake_session):
        _, label = aws_provider.build_credential(
            _aws_entry(role_arn="arn:aws:iam::123456789012:role/FinOpsReadOnly")
        )
    assert label == "AssumeRole"
    fake_sts.assume_role.assert_called_once_with(
        RoleArn="arn:aws:iam::123456789012:role/FinOpsReadOnly",
        RoleSessionName="finops-cli",
    )


def test_aws_build_credential_sts_error_raises_unavailable():
    from botocore.exceptions import ClientError
    fake_session = MagicMock()
    fake_sts = MagicMock()
    fake_sts.assume_role.side_effect = ClientError(
        {"Error": {"Code": "AccessDenied", "Message": "nope"}}, "AssumeRole"
    )
    fake_session.client.return_value = fake_sts
    with patch("boto3.Session", return_value=fake_session):
        with pytest.raises(ProviderUnavailableError):
            aws_provider.build_credential(
                _aws_entry(role_arn="arn:aws:iam::123456789012:role/FinOpsReadOnly")
            )
