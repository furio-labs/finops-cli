"""GCP branches of the provider-keyed analyzers."""
from finops.analyzers.idle import IdleAnalyzer
from finops.analyzers.untagged import UntaggedAnalyzer
from finops.analyzers.scheduling import SchedulingAnalyzer
from finops.analyzers.wrong_sku import WrongSkuAnalyzer
from finops.analyzers.dev_in_prod import DevInProdAnalyzer
from finops.config import FinOpsConfig
from finops.models import Severity
from tests.conftest import make_gcp_resource, make_gcp_cost


def _config():
    return FinOpsConfig(subscriptions=[
        {"provider": "gcp", "id": "my-gcp-project", "name": "P",
         "billing_account_id": "0123AB-4567CD-89EF01", "billing_export_dataset": "ds"},
    ])


# --- idle (flagship; exercises the //-form resource.id <-> cost.resource_id join) ---

def test_idle_flags_gcp_resource_with_matching_id_join():
    analyzer = IdleAnalyzer(_config())
    resource = make_gcp_resource()
    # Cost keyed by the SAME //-form id the resource carries.
    cost = make_gcp_cost(
        resource_id=resource.id,
        daily_costs={"2026-05-01": 0.01, "2026-05-02": 0.02},
    )
    findings = analyzer.analyze("my-gcp-project", [resource], [cost])
    assert len(findings) == 1
    assert findings[0].category == "Idle"
    assert findings[0].provider == "gcp"


def test_idle_no_finding_when_cost_id_does_not_match_resource():
    analyzer = IdleAnalyzer(_config())
    resource = make_gcp_resource()
    cost = make_gcp_cost(
        resource_id="//billing/my-gcp-project/unattributed/Compute_Engine",
        daily_costs={"2026-05-01": 0.01},
    )
    assert analyzer.analyze("my-gcp-project", [resource], [cost]) == []


# --- untagged ---

def test_untagged_flags_gcp_resource_missing_labels():
    analyzer = UntaggedAnalyzer(_config())
    resource = make_gcp_resource(tags={})  # missing environment/client/service
    findings = analyzer.analyze("my-gcp-project", [resource], [])
    assert len(findings) == 1
    assert findings[0].category == "Untagged"
    assert findings[0].provider == "gcp"


# --- scheduling ---

def test_scheduling_flags_gcp_instance_running_all_week():
    analyzer = SchedulingAnalyzer(_config())
    resource = make_gcp_resource(tags={"environment": "dev"})
    cost = make_gcp_cost(
        resource_id=resource.id,
        daily_costs={f"2026-05-{d:02d}": 5.0 for d in range(1, 8)},
    )
    findings = analyzer.analyze("my-gcp-project", [resource], [cost])
    assert len(findings) == 1
    assert findings[0].category == "Scheduling"
    assert findings[0].provider == "gcp"


def test_scheduling_ignores_gcp_non_schedulable_type():
    analyzer = SchedulingAnalyzer(_config())
    resource = make_gcp_resource(
        resource_type="storage.googleapis.com/bucket", tags={"environment": "dev"})
    cost = make_gcp_cost(
        resource_id=resource.id,
        daily_costs={f"2026-05-{d:02d}": 5.0 for d in range(1, 8)},
    )
    assert analyzer.analyze("my-gcp-project", [resource], [cost]) == []


# --- wrong_sku ---

def test_wrong_sku_flags_gcp_cloud_sql_highmem():
    analyzer = WrongSkuAnalyzer(_config())
    resource = make_gcp_resource(
        resource_type="sqladmin.googleapis.com/instance",
        sku_name="db-n1-highmem-8", sku_tier=None,
    )
    findings = analyzer.analyze("my-gcp-project", [resource], [])
    assert len(findings) == 1
    assert findings[0].severity == Severity.HIGH
    assert findings[0].provider == "gcp"


def test_wrong_sku_flags_gcp_ssd_disk():
    analyzer = WrongSkuAnalyzer(_config())
    resource = make_gcp_resource(
        resource_type="compute.googleapis.com/disk", sku_name="pd-ssd", sku_tier=None)
    findings = analyzer.analyze("my-gcp-project", [resource], [])
    assert len(findings) == 1
    assert findings[0].severity == Severity.MEDIUM


def test_wrong_sku_ignores_standard_gcp_instance():
    analyzer = WrongSkuAnalyzer(_config())
    resource = make_gcp_resource(sku_name="e2-standard-4")
    assert analyzer.analyze("my-gcp-project", [resource], []) == []


# --- dev_in_prod ---

def test_dev_in_prod_flags_micro_in_production():
    analyzer = DevInProdAnalyzer(_config())
    resource = make_gcp_resource(
        tags={"environment": "production"}, sku_name="e2-micro", sku_tier="e2")
    findings = analyzer.analyze("my-gcp-project", [resource], [])
    assert len(findings) == 1
    assert findings[0].severity == Severity.HIGH
    assert findings[0].provider == "gcp"


def test_dev_in_prod_flags_expensive_family_in_dev():
    analyzer = DevInProdAnalyzer(_config())
    resource = make_gcp_resource(
        tags={"environment": "dev"}, sku_name="n2-standard-16", sku_tier="n2")
    findings = analyzer.analyze("my-gcp-project", [resource], [])
    assert len(findings) == 1
    assert findings[0].severity == Severity.MEDIUM


def test_dev_in_prod_no_finding_for_standard_in_prod():
    analyzer = DevInProdAnalyzer(_config())
    resource = make_gcp_resource(
        tags={"environment": "production"}, sku_name="e2-standard-4", sku_tier="e2")
    assert analyzer.analyze("my-gcp-project", [resource], []) == []
