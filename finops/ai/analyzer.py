from __future__ import annotations
import json
import os
from datetime import date

from anthropic import Anthropic

from finops.models import AiInsight, SubscriptionData
from finops.ai.prompt import build_prompt

_DEFAULT_MODEL = "claude-haiku-4-5-20251001"
_DEFAULT_MAX_TOKENS = 4096


class AiAnalyzer:
    def __init__(self, api_key: str | None = None) -> None:
        self._client = Anthropic(api_key=api_key)
        self._model = os.getenv("FINOPS_AI_MODEL", _DEFAULT_MODEL)
        self._max_tokens = int(os.getenv("FINOPS_AI_MAX_TOKENS", _DEFAULT_MAX_TOKENS))

    def analyze(self, sub: SubscriptionData, date_from: date, date_to: date) -> list[AiInsight]:
        prompt = build_prompt(sub, date_from, date_to)
        msg = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text
        if getattr(msg, "stop_reason", None) == "max_tokens":
            raise ValueError(
                f"AI response truncated at {self._max_tokens} tokens; "
                f"raise FINOPS_AI_MAX_TOKENS. Partial: {raw[:200]!r}"
            )
        start = raw.find("[")
        end = raw.rfind("]") + 1
        if start == -1 or end == 0:
            raise ValueError(f"No JSON array in response: {raw[:200]!r}")
        _known = {f.name for f in AiInsight.__dataclass_fields__.values()}
        return [
            AiInsight(**{k: v for k, v in item.items() if k in _known})
            for item in json.loads(raw[start:end])
        ]
