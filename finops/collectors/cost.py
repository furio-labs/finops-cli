from __future__ import annotations
from datetime import date
from azure.mgmt.costmanagement import CostManagementClient
from azure.mgmt.costmanagement.models import (
    QueryDefinition, QueryTimePeriod, QueryDataset,
    QueryAggregation, QueryGrouping,
)
from finops.models import ResourceCost
from finops.collectors.base import retry_on_throttle


def _parse_date(usage_date_int: int) -> str:
    s = str(usage_date_int)
    return f"{s[:4]}-{s[4:6]}-{s[6:8]}"


class CostCollector:
    def __init__(self, credential) -> None:
        self._credential = credential

    def collect(self, subscription_id: str, start_date: date, end_date: date) -> list[ResourceCost]:
        client = CostManagementClient(self._credential)
        scope = f"/subscriptions/{subscription_id}"

        query = QueryDefinition(
            type="ActualCost",
            timeframe="Custom",
            time_period=QueryTimePeriod(
                from_property=start_date,
                to=end_date,
            ),
            dataset=QueryDataset(
                granularity="Daily",
                aggregation={"totalCost": QueryAggregation(name="Cost", function="Sum")},
                grouping=[
                    QueryGrouping(type="Dimension", name="ResourceId"),
                    QueryGrouping(type="Dimension", name="ResourceGroupName"),
                    QueryGrouping(type="Dimension", name="ResourceType"),
                ],
            ),
        )

        result = retry_on_throttle(lambda: client.query.usage(scope=scope, parameters=query))

        col_index = {col.name: i for i, col in enumerate(result.columns)}
        required = {"Cost", "UsageDate", "ResourceId", "ResourceGroupName", "ResourceType"}
        missing = required - col_index.keys()
        if missing:
            actual = list(col_index.keys())
            raise RuntimeError(
                f"Azure Cost Management returned unexpected columns. "
                f"Missing: {missing}. Got: {actual}"
            )
        cost_idx = col_index["Cost"]
        date_idx = col_index["UsageDate"]
        rid_idx = col_index["ResourceId"]
        rg_idx = col_index["ResourceGroupName"]
        rtype_idx = col_index["ResourceType"]

        costs: dict[str, ResourceCost] = {}
        for row in result.rows:
            rid = row[rid_idx]
            day = _parse_date(int(row[date_idx]))
            cost = float(row[cost_idx])
            if rid not in costs:
                costs[rid] = ResourceCost(
                    resource_id=rid,
                    resource_group=row[rg_idx],
                    subscription_id=subscription_id,
                    resource_type=row[rtype_idx],
                    daily_costs={},
                )
            costs[rid].daily_costs[day] = costs[rid].daily_costs.get(day, 0.0) + cost

        return list(costs.values())
