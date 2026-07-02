"""GCP per-resource cost collector via the *detailed* Cloud Billing export in
BigQuery (`gcp_billing_export_resource_v1_*`) — the only source that carries
`resource.name`/`resource.global_name` for per-resource attribution.

Two caveats baked in here (see docs/gcp-billing-export-setup.md):
  - Join key: `resource.global_name` is the `//service/…` full name that matches
    Cloud Asset ids. Rows without it are bucketed as *unattributable* (they count
    in totals but never match a resource in idle/scheduling) — the Azure
    marketplace precedent. Validate `_canonical_id` against a real export.
  - Currency: the model + reporters assume USD. A non-USD export raises
    ProviderUnavailableError so the entry is skipped rather than mis-reported.
"""
from __future__ import annotations

from google.cloud import bigquery
from google.api_core import exceptions as gexc

from finops.models import ResourceCost
from finops.providers import ProviderPermissionError, ProviderUnavailableError

_SQL_TEMPLATE = """
SELECT
  COALESCE(resource.global_name, resource.name) AS resource_key,
  ANY_VALUE(resource.name) AS resource_name,
  ANY_VALUE(service.description) AS service_name,
  ANY_VALUE(currency) AS currency,
  FORMAT_DATE('{date_fmt}', DATE(usage_start_time)) AS day,
  SUM(cost) AS cost
FROM `{table}`
WHERE DATE(usage_start_time) BETWEEN @start AND @end
  AND project.id = @project_id
GROUP BY resource_key, day
"""


def _canonical_id(resource_key, resource_name, project_id, service_name) -> str:
    """Return the join id. A `//service/…` full name matches Cloud Asset ids;
    anything else is bucketed per-service as unattributable."""
    key = resource_key or resource_name
    if key and str(key).startswith("//"):
        return str(key)
    svc = (service_name or "unknown").replace(" ", "_")
    return f"//billing/{project_id}/unattributed/{svc}"


class CostCollector:
    def __init__(self, credential, entry) -> None:
        self._entry = entry
        self._client = bigquery.Client(
            project=entry.billing_export_project or entry.id,
            credentials=credential,
        )

    def collect(self, project_id, start_date, end_date, granularity="Daily") -> list[ResourceCost]:
        date_fmt = "%Y-%m-01" if granularity.lower() == "monthly" else "%Y-%m-%d"
        sql = _SQL_TEMPLATE.format(table=self._entry.export_table_fqn, date_fmt=date_fmt)
        job_config = bigquery.QueryJobConfig(query_parameters=[
            bigquery.ScalarQueryParameter("start", "DATE", start_date),
            bigquery.ScalarQueryParameter("end", "DATE", end_date),
            bigquery.ScalarQueryParameter("project_id", "STRING", project_id),
        ])
        try:
            rows = self._client.query_and_wait(sql, job_config=job_config)
        except gexc.NotFound as exc:
            raise ProviderUnavailableError(
                f"Billing export table not found: {self._entry.export_table_fqn}"
            ) from exc
        except (gexc.PermissionDenied, gexc.Forbidden) as exc:
            raise ProviderPermissionError(str(exc)) from exc
        except gexc.GoogleAPICallError as exc:
            raise ProviderUnavailableError(f"BigQuery error: {exc}") from exc

        by_key: dict[str, ResourceCost] = {}
        for row in rows:
            currency = getattr(row, "currency", None) or "USD"
            if currency != "USD":
                raise ProviderUnavailableError(
                    f"Billing export currency is {currency}; only USD is supported"
                )
            service_name = getattr(row, "service_name", None) or ""
            key = _canonical_id(
                getattr(row, "resource_key", None),
                getattr(row, "resource_name", None),
                project_id,
                service_name,
            )
            rc = by_key.get(key)
            if rc is None:
                rc = ResourceCost(
                    resource_id=key,
                    resource_group="",
                    subscription_id=project_id,
                    resource_type=service_name,
                    daily_costs={},
                    publisher_type="GCP",
                    service_name=service_name,
                    provider="gcp",
                )
                by_key[key] = rc
            rc.daily_costs[row.day] = rc.daily_costs.get(row.day, 0.0) + float(row.cost)
        return list(by_key.values())
