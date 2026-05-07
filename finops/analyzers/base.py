from __future__ import annotations
from abc import ABC, abstractmethod
from finops.config import FinOpsConfig
from finops.models import AzureResource, ResourceCost, Finding


class Analyzer(ABC):
    def __init__(self, config: FinOpsConfig) -> None:
        self.config = config

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def analyze(
        self,
        subscription_id: str,
        resources: list[AzureResource],
        costs: list[ResourceCost],
    ) -> list[Finding]: ...
