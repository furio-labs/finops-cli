"""AWS cost collector via Cost Explorer (`get_cost_and_usage`).

Unlike Azure Cost Management or the GCP BigQuery billing export, standard
Cost Explorer does not return a per-resource id — `get_cost_and_usage_with_resources`
exists but only covers a 14-day window and a handful of resource types. So
costs here are grouped by SERVICE and bucketed the same way the other
providers bucket their own unattributable rows: as a synthetic
`aws:unattributed/{service}` resource id. idle/scheduling therefore never
match AWS costs to a specific resource (only totals + WrongSku/DevInProd,
which key off resource type + tags, are meaningful for AWS today)."""
from __future__ import annotations

from botocore.exceptions import ClientError, BotoCoreError

from finops.models import ResourceCost
from finops.providers import ProviderPermissionError, ProviderUnavailableError


class CostCollector:
    def __init__(self, credential, entry) -> None:
        self._entry = entry
        self._client = credential.client("ce", region_name="us-east-1")  # CE is a global endpoint

    def collect(self, account_id, start_date, end_date, granularity="Daily") -> list[ResourceCost]:
        granularity_api = "MONTHLY" if granularity.lower() == "monthly" else "DAILY"
        try:
            results_by_time = []
            token = None
            while True:
                kwargs = dict(
                    TimePeriod={"Start": str(start_date), "End": str(end_date)},
                    Granularity=granularity_api,
                    Metrics=["UnblendedCost"],
                    GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
                )
                if token:
                    kwargs["NextPageToken"] = token
                resp = self._client.get_cost_and_usage(**kwargs)
                results_by_time.extend(resp.get("ResultsByTime", []))
                token = resp.get("NextPageToken")
                if not token:
                    break
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code in ("AccessDeniedException", "AccessDenied", "UnauthorizedAccess"):
                raise ProviderPermissionError(str(exc)) from exc
            raise ProviderUnavailableError(f"Cost Explorer error: {exc}") from exc
        except BotoCoreError as exc:
            raise ProviderUnavailableError(f"Cost Explorer error: {exc}") from exc

        by_key: dict[str, ResourceCost] = {}
        for period in results_by_time:
            day = period["TimePeriod"]["Start"]
            for group in period.get("Groups", []):
                service = group["Keys"][0]
                amount = float(group["Metrics"]["UnblendedCost"]["Amount"])
                unit = group["Metrics"]["UnblendedCost"]["Unit"]
                if unit != "USD":
                    raise ProviderUnavailableError(
                        f"Cost Explorer returned unit {unit}; only USD is supported"
                    )
                key = f"aws:unattributed/{service.replace(' ', '_')}"
                rc = by_key.get(key)
                if rc is None:
                    rc = ResourceCost(
                        resource_id=key,
                        resource_group="",
                        subscription_id=account_id,
                        resource_type=service,
                        daily_costs={},
                        publisher_type="AWS",
                        service_name=service,
                        provider="aws",
                    )
                    by_key[key] = rc
                rc.daily_costs[day] = rc.daily_costs.get(day, 0.0) + amount
        return list(by_key.values())
