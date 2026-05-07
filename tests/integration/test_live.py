"""
Live integration tests — require real Azure credentials and a test subscription.
Skipped unless AZURE_TEST_SUBSCRIPTION_ID env var is set.
"""
import os
import pytest
from datetime import date

SUBSCRIPTION_ID = os.getenv("AZURE_TEST_SUBSCRIPTION_ID")
skip_if_no_subscription = pytest.mark.skipif(
    not SUBSCRIPTION_ID,
    reason="Set AZURE_TEST_SUBSCRIPTION_ID to run integration tests",
)


@skip_if_no_subscription
def test_resource_collector_returns_results():
    from finops.auth import get_credential
    from finops.collectors.resources import ResourceCollector
    credential, _ = get_credential()
    collector = ResourceCollector(credential)
    resources = collector.collect(SUBSCRIPTION_ID)
    assert isinstance(resources, list)


@skip_if_no_subscription
def test_cost_collector_returns_results():
    from finops.auth import get_credential
    from finops.collectors.cost import CostCollector
    credential, _ = get_credential()
    collector = CostCollector(credential)
    today = date.today()
    start = today.replace(day=1)
    costs = collector.collect(SUBSCRIPTION_ID, start, today)
    assert isinstance(costs, list)


@skip_if_no_subscription
def test_full_run_produces_report(tmp_path):
    from click.testing import CliRunner
    from finops.cli import cli
    runner = CliRunner()
    result = runner.invoke(cli, [
        "run",
        "--subscriptions", SUBSCRIPTION_ID,
        "--output", str(tmp_path),
    ])
    assert result.exit_code == 0
    assert (tmp_path / date.today().isoformat() / "report.html").exists()
