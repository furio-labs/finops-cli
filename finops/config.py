from __future__ import annotations
import sys
from pathlib import Path
from typing import Annotated, Literal, Union
import yaml
from pydantic import BaseModel, Field, field_validator, model_validator


class AzureEntry(BaseModel):
    provider: Literal["azure"] = "azure"
    id: str                                    # Azure subscription id
    name: str
    tags: dict[str, str] = Field(default_factory=dict)


class GcpEntry(BaseModel):
    provider: Literal["gcp"]
    id: str                                    # GCP project id (fills the subscription_id slot)
    name: str
    tags: dict[str, str] = Field(default_factory=dict)
    billing_account_id: str                    # e.g. "0123AB-4567CD-89EF01"
    billing_export_dataset: str                # BigQuery dataset holding the detailed export
    billing_export_table: str = ""             # optional explicit table override
    billing_export_project: str = ""           # BigQuery project, if different from `id`

    @property
    def export_table_fqn(self) -> str:
        """Fully-qualified detailed-export table: `project.dataset.table`."""
        proj = self.billing_export_project or self.id
        table = self.billing_export_table or (
            "gcp_billing_export_resource_v1_"
            + self.billing_account_id.replace("-", "_")
        )
        return f"{proj}.{self.billing_export_dataset}.{table}"


class AwsEntry(BaseModel):
    provider: Literal["aws"]
    id: str                                    # AWS account id (fills the subscription_id slot)
    name: str
    tags: dict[str, str] = Field(default_factory=dict)
    region: str = "us-east-1"                  # Cost Explorer is a global endpoint; this is for regional clients (e.g. EC2/tagging)
    role_arn: str = ""                         # optional cross-account role to assume for this account


# Discriminated union; `SubscriptionEntry` name kept for backward compatibility.
SubscriptionEntry = Annotated[Union[AzureEntry, GcpEntry, AwsEntry], Field(discriminator="provider")]


class CostThresholds(BaseModel):
    idle_resource_daily_usd: float = 0.10
    scheduling_hours_per_day: int = 8


class FinOpsConfig(BaseModel):
    subscriptions: list[SubscriptionEntry]
    required_tags: list[str] = Field(default_factory=lambda: ["environment", "client", "service"])
    cost_thresholds: CostThresholds = Field(default_factory=CostThresholds)

    @model_validator(mode="before")
    @classmethod
    def _default_provider(cls, data):
        # Backward compat: entries with no `provider` are Azure. A Pydantic v2
        # discriminated union otherwise rejects a missing discriminator.
        if isinstance(data, dict):
            for entry in data.get("subscriptions", []) or []:
                if isinstance(entry, dict) and "provider" not in entry:
                    entry["provider"] = "azure"
        return data

    @field_validator("subscriptions", mode="before")
    @classmethod
    def at_least_one(cls, v: list) -> list:
        if not v:
            raise ValueError("At least one subscription must be configured")
        return v

    def with_subscription_override(self, ids: list[str]) -> "FinOpsConfig":
        known = {s.id: s for s in self.subscriptions}
        # A bare id override has no GCP billing config, so unknown ids are Azure.
        result = [known.get(id_, AzureEntry(id=id_, name=id_)) for id_ in ids]
        return self.model_copy(update={"subscriptions": result})


def load_config(path: str) -> FinOpsConfig:
    config_path = Path(path)
    if not config_path.exists():
        print(f"[error] Config file not found: {path}", file=sys.stderr)
        sys.exit(1)
    try:
        raw = yaml.safe_load(config_path.read_text())
        return FinOpsConfig.model_validate(raw)
    except Exception as exc:
        print(f"[error] Invalid config: {exc}", file=sys.stderr)
        sys.exit(1)
