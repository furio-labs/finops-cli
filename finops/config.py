from __future__ import annotations
import sys
from pathlib import Path
import yaml
from pydantic import BaseModel, Field, field_validator


class SubscriptionEntry(BaseModel):
    id: str
    name: str
    tags: dict[str, str] = Field(default_factory=dict)


class CostThresholds(BaseModel):
    idle_resource_daily_usd: float = 0.10
    scheduling_hours_per_day: int = 8


class FinOpsConfig(BaseModel):
    subscriptions: list[SubscriptionEntry]
    required_tags: list[str] = Field(default_factory=lambda: ["environment", "client", "service"])
    cost_thresholds: CostThresholds = Field(default_factory=CostThresholds)

    @field_validator("subscriptions", mode="before")
    @classmethod
    def at_least_one(cls, v: list) -> list:
        if not v:
            raise ValueError("At least one subscription must be configured")
        return v

    def with_subscription_override(self, ids: list[str]) -> "FinOpsConfig":
        filtered = [s for s in self.subscriptions if s.id in ids]
        if not filtered:
            raise ValueError(f"No subscriptions matched the provided IDs: {ids}")
        return self.model_copy(update={"subscriptions": filtered})


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
