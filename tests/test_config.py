import pytest
import yaml
from pathlib import Path
from finops.config import load_config, FinOpsConfig, AzureEntry, GcpEntry, AwsEntry


def test_load_valid_config(tmp_path):
    config_file = tmp_path / "subscriptions.yaml"
    config_file.write_text(yaml.dump({
        "subscriptions": [
            {"id": "sub-001", "name": "Test Sub", "tags": {"environment": "production"}}
        ],
        "required_tags": ["environment", "client"],
        "cost_thresholds": {
            "idle_resource_daily_usd": 0.05,
            "scheduling_hours_per_day": 10,
        },
    }))
    config = load_config(str(config_file))
    assert len(config.subscriptions) == 1
    assert config.subscriptions[0].id == "sub-001"
    assert config.required_tags == ["environment", "client"]
    assert config.cost_thresholds.idle_resource_daily_usd == 0.05


def test_load_config_defaults(tmp_path):
    config_file = tmp_path / "subscriptions.yaml"
    config_file.write_text(yaml.dump({
        "subscriptions": [{"id": "sub-001", "name": "Test"}],
    }))
    config = load_config(str(config_file))
    assert config.cost_thresholds.idle_resource_daily_usd == 0.10
    assert config.cost_thresholds.scheduling_hours_per_day == 8
    assert config.required_tags == ["environment", "client", "service"]


def test_load_config_empty_subscriptions_raises(tmp_path):
    config_file = tmp_path / "subscriptions.yaml"
    config_file.write_text(yaml.dump({"subscriptions": []}))
    with pytest.raises(SystemExit):
        load_config(str(config_file))


def test_load_config_missing_file_raises():
    with pytest.raises(SystemExit):
        load_config("/nonexistent/subscriptions.yaml")


def test_override_subscriptions_known_id():
    config = FinOpsConfig(subscriptions=[
        {"id": "sub-001", "name": "A"},
        {"id": "sub-002", "name": "B"},
    ])
    overridden = config.with_subscription_override(["sub-001"])
    assert len(overridden.subscriptions) == 1
    assert overridden.subscriptions[0].id == "sub-001"
    assert overridden.subscriptions[0].name == "A"


def test_override_subscriptions_unknown_id_creates_minimal_entry():
    config = FinOpsConfig(subscriptions=[{"id": "sub-001", "name": "A"}])
    overridden = config.with_subscription_override(["7c5d79ec-458a-4a17-86f8-d2c7fa31cf8e"])
    assert len(overridden.subscriptions) == 1
    assert overridden.subscriptions[0].id == "7c5d79ec-458a-4a17-86f8-d2c7fa31cf8e"
    assert overridden.subscriptions[0].name == "7c5d79ec-458a-4a17-86f8-d2c7fa31cf8e"


def test_entry_without_provider_defaults_to_azure(tmp_path):
    config_file = tmp_path / "subscriptions.yaml"
    config_file.write_text(yaml.dump({
        "subscriptions": [{"id": "sub-001", "name": "Legacy Azure"}],
    }))
    config = load_config(str(config_file))
    assert isinstance(config.subscriptions[0], AzureEntry)
    assert config.subscriptions[0].provider == "azure"


def test_gcp_entry_validates_and_derives_export_table(tmp_path):
    config_file = tmp_path / "subscriptions.yaml"
    config_file.write_text(yaml.dump({
        "subscriptions": [{
            "provider": "gcp",
            "id": "my-gcp-project-123",
            "name": "Prod GCP",
            "billing_account_id": "0123AB-4567CD-89EF01",
            "billing_export_dataset": "billing_export",
            "tags": {"client": "acme"},
        }],
    }))
    config = load_config(str(config_file))
    entry = config.subscriptions[0]
    assert isinstance(entry, GcpEntry)
    assert entry.export_table_fqn == (
        "my-gcp-project-123.billing_export."
        "gcp_billing_export_resource_v1_0123AB_4567CD_89EF01"
    )


def test_gcp_entry_export_table_honors_overrides():
    entry = GcpEntry(
        provider="gcp", id="proj-a", name="A",
        billing_account_id="0123AB-4567CD-89EF01",
        billing_export_dataset="ds",
        billing_export_table="custom_table",
        billing_export_project="billing-proj",
    )
    assert entry.export_table_fqn == "billing-proj.ds.custom_table"


def test_mixed_azure_and_gcp_entries_load(tmp_path):
    config_file = tmp_path / "subscriptions.yaml"
    config_file.write_text(yaml.dump({
        "subscriptions": [
            {"id": "azure-sub", "name": "Azure"},
            {"provider": "gcp", "id": "gcp-proj", "name": "GCP",
             "billing_account_id": "0123AB-4567CD-89EF01",
             "billing_export_dataset": "billing_export"},
        ],
    }))
    config = load_config(str(config_file))
    assert isinstance(config.subscriptions[0], AzureEntry)
    assert isinstance(config.subscriptions[1], GcpEntry)


def test_gcp_entry_missing_billing_fields_raises(tmp_path):
    config_file = tmp_path / "subscriptions.yaml"
    config_file.write_text(yaml.dump({
        "subscriptions": [{"provider": "gcp", "id": "gcp-proj", "name": "GCP"}],
    }))
    with pytest.raises(SystemExit):
        load_config(str(config_file))


def test_aws_entry_loads_with_defaults(tmp_path):
    config_file = tmp_path / "subscriptions.yaml"
    config_file.write_text(yaml.dump({
        "subscriptions": [{
            "provider": "aws", "id": "123456789012", "name": "Prod AWS",
            "tags": {"client": "acme"},
        }],
    }))
    config = load_config(str(config_file))
    entry = config.subscriptions[0]
    assert isinstance(entry, AwsEntry)
    assert entry.region == "us-east-1"
    assert entry.role_arn == ""


def test_aws_entry_honors_region_and_role_arn():
    entry = AwsEntry(
        provider="aws", id="123456789012", name="Prod AWS",
        region="eu-west-1", role_arn="arn:aws:iam::123456789012:role/FinOpsReadOnly",
    )
    assert entry.region == "eu-west-1"
    assert entry.role_arn == "arn:aws:iam::123456789012:role/FinOpsReadOnly"


def test_mixed_azure_gcp_aws_entries_load(tmp_path):
    config_file = tmp_path / "subscriptions.yaml"
    config_file.write_text(yaml.dump({
        "subscriptions": [
            {"id": "azure-sub", "name": "Azure"},
            {"provider": "gcp", "id": "gcp-proj", "name": "GCP",
             "billing_account_id": "0123AB-4567CD-89EF01",
             "billing_export_dataset": "billing_export"},
            {"provider": "aws", "id": "123456789012", "name": "AWS"},
        ],
    }))
    config = load_config(str(config_file))
    assert isinstance(config.subscriptions[0], AzureEntry)
    assert isinstance(config.subscriptions[1], GcpEntry)
    assert isinstance(config.subscriptions[2], AwsEntry)
