from datetime import date
from finops.ai.prompt import build_prompt
from finops.models import AiInsight, Severity
from tests.conftest import make_resource, make_cost, make_finding


def _make_sub(resources=None, costs=None, findings=None):
    from finops.models import SubscriptionData
    return SubscriptionData(
        subscription_id="sub1",
        subscription_name="Test Sub",
        resources=resources or [make_resource()],
        costs=costs or [make_cost()],
        invoices=[],
        findings=findings or [],
    )


def test_prompt_contains_subscription_name():
    sub = _make_sub()
    prompt = build_prompt(sub, date(2026, 5, 1), date(2026, 5, 7))
    assert "Test Sub" in prompt


def test_prompt_contains_date_range():
    sub = _make_sub()
    prompt = build_prompt(sub, date(2026, 5, 1), date(2026, 5, 7))
    assert "2026-05-01" in prompt
    assert "2026-05-07" in prompt


def test_prompt_contains_resource_types():
    sub = _make_sub(resources=[make_resource(resource_type="microsoft.compute/virtualmachines")])
    prompt = build_prompt(sub, date(2026, 5, 1), date(2026, 5, 7))
    assert "microsoft.compute/virtualmachines" in prompt


def test_prompt_caps_top_resources_at_15():
    costs = [
        make_cost(
            resource_id=f"/subscriptions/sub1/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/vm{i}",
            daily_costs={"2026-05-01": float(i)},
        )
        for i in range(20)
    ]
    sub = _make_sub(costs=costs)
    prompt = build_prompt(sub, date(2026, 5, 1), date(2026, 5, 7))
    # Only top 15 resources should appear — vm0 (cheapest) should NOT be in the prompt
    # Check the prompt doesn't list all 20
    assert prompt.count("vm") <= 15


def test_prompt_includes_existing_findings_categories():
    findings = [make_finding(category="Idle"), make_finding(category="Untagged")]
    sub = _make_sub(findings=findings)
    prompt = build_prompt(sub, date(2026, 5, 1), date(2026, 5, 7))
    assert "Idle" in prompt
    assert "Untagged" in prompt


def test_prompt_requests_json_output():
    sub = _make_sub()
    prompt = build_prompt(sub, date(2026, 5, 1), date(2026, 5, 7))
    assert "JSON" in prompt or "json" in prompt
