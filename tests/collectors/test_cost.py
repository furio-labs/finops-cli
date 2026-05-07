import pytest
from unittest.mock import MagicMock, patch, call
from azure.core.exceptions import HttpResponseError
from finops.collectors.base import retry_on_throttle


def test_retry_on_throttle_succeeds_first_try():
    fn = MagicMock(return_value="ok")
    result = retry_on_throttle(fn)
    assert result == "ok"
    assert fn.call_count == 1


def test_retry_on_throttle_retries_on_429():
    error_429 = HttpResponseError(message="Too Many Requests")
    error_429.status_code = 429
    fn = MagicMock(side_effect=[error_429, error_429, "ok"])
    with patch("finops.collectors.base.time.sleep") as mock_sleep:
        result = retry_on_throttle(fn, max_retries=3)
    assert result == "ok"
    assert fn.call_count == 3
    assert mock_sleep.call_args_list == [call(5), call(10)]


def test_retry_on_throttle_raises_after_max_retries():
    error_429 = HttpResponseError(message="Too Many Requests")
    error_429.status_code = 429
    fn = MagicMock(side_effect=error_429)
    with patch("finops.collectors.base.time.sleep"):
        with pytest.raises(HttpResponseError):
            retry_on_throttle(fn, max_retries=3)
