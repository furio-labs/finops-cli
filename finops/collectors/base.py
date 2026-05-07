from __future__ import annotations
import time
from typing import Callable, TypeVar
from azure.core.exceptions import HttpResponseError

T = TypeVar("T")


def retry_on_throttle(fn: Callable[[], T], max_retries: int = 3) -> T:
    for attempt in range(max_retries):
        try:
            return fn()
        except HttpResponseError as exc:
            if getattr(exc, "status_code", None) == 429 and attempt < max_retries - 1:
                time.sleep(5 * (2 ** attempt))
                continue
            raise
