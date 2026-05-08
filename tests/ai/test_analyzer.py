from datetime import date
from unittest.mock import MagicMock, patch
import pytest

from finops.models import AiInsight
from finops.ai.analyzer import AiAnalyzer
from tests.conftest import make_resource, make_cost


def _make_sub():
    from finops.models import SubscriptionData
    return SubscriptionData(
        subscription_id="sub1",
        subscription_name="Test Sub",
        resources=[make_resource()],
        costs=[make_cost()],
        invoices=[],
    )


_VALID_JSON = '[{"title":"Idle VM","category":"Recommendation","detail":"El VM está inactivo.","estimated_monthly_savings_usd":50.0,"confidence":"high"}]'
_WRAPPED_JSON = f"```json\n{_VALID_JSON}\n```"


def _mock_client(text: str):
    client = MagicMock()
    msg = MagicMock()
    msg.content = [MagicMock(text=text)]
    client.messages.create.return_value = msg
    return client


def test_analyze_returns_ai_insights():
    with patch("finops.ai.analyzer.Anthropic", return_value=_mock_client(_VALID_JSON)):
        analyzer = AiAnalyzer()
    result = analyzer.analyze(_make_sub(), date(2026, 5, 1), date(2026, 5, 7))
    assert len(result) == 1
    assert isinstance(result[0], AiInsight)
    assert result[0].title == "Idle VM"
    assert result[0].confidence == "high"
    assert result[0].estimated_monthly_savings_usd == 50.0


def test_analyze_handles_markdown_wrapped_json():
    with patch("finops.ai.analyzer.Anthropic", return_value=_mock_client(_WRAPPED_JSON)):
        analyzer = AiAnalyzer()
    result = analyzer.analyze(_make_sub(), date(2026, 5, 1), date(2026, 5, 7))
    assert len(result) == 1
    assert result[0].category == "Recommendation"


def test_analyze_propagates_api_exception():
    client = MagicMock()
    client.messages.create.side_effect = RuntimeError("API error")
    with patch("finops.ai.analyzer.Anthropic", return_value=client):
        analyzer = AiAnalyzer()
    with pytest.raises(RuntimeError, match="API error"):
        analyzer.analyze(_make_sub(), date(2026, 5, 1), date(2026, 5, 7))


def test_analyzer_uses_env_model(monkeypatch):
    monkeypatch.setenv("FINOPS_AI_MODEL", "claude-sonnet-4-6")
    client = _mock_client(_VALID_JSON)
    with patch("finops.ai.analyzer.Anthropic", return_value=client):
        analyzer = AiAnalyzer()
    analyzer.analyze(_make_sub(), date(2026, 5, 1), date(2026, 5, 7))
    call_kwargs = client.messages.create.call_args
    assert call_kwargs.kwargs["model"] == "claude-sonnet-4-6"
