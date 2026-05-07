import pytest
import yaml
from pathlib import Path
from finops.config import load_config, FinOpsConfig


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
