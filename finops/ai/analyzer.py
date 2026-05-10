from __future__ import annotations
import json
import os
from datetime import date

from anthropic import Anthropic

from finops.models import AiInsight, SubscriptionData
from finops.ai.prompt import build_prompt

_DEFAULT_MODEL = "claude-haiku-4-5-20251001"


class AiAnalyzer:
    def __init__(self, api_key: str | None = None) -> None:
        self._client = Anthropic(api_key=api_key)
        self._model = os.getenv("FINOPS_AI_MODEL", _DEFAULT_MODEL)

    def analyze(self, sub: SubscriptionData, date_from: date, date_to: date) -> list[AiInsight]:
        prompt = build_prompt(sub, date_from, date_to)
        msg = self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text
        start = raw.find("[")
        end = raw.rfind("]") + 1
        return [AiInsight(**item) for item in json.loads(raw[start:end])]
