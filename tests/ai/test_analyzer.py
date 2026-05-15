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


def _mock_client(text: str, stop_reason: str = "end_turn"):
    client = MagicMock()
    msg = MagicMock()
    msg.content = [MagicMock(text=text)]
    msg.stop_reason = stop_reason
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


def test_analyze_ignores_extra_fields_from_claude():
    """Claude may return extra fields not in AiInsight — they should be silently dropped."""
    extra = '[{"title":"X","category":"Recommendation","detail":"d.","estimated_monthly_savings_usd":0.0,"confidence":"low","extra_field":"ignored"}]'
    with patch("finops.ai.analyzer.Anthropic", return_value=_mock_client(extra)):
        analyzer = AiAnalyzer()
    result = analyzer.analyze(_make_sub(), date(2026, 5, 1), date(2026, 5, 7))
    assert len(result) == 1
    assert result[0].title == "X"


def test_analyze_raises_on_no_json_array():
    """A response with no JSON array should raise ValueError with the raw text."""
    with patch("finops.ai.analyzer.Anthropic", return_value=_mock_client("Sorry, I cannot help.")):
        analyzer = AiAnalyzer()
    with pytest.raises(ValueError, match="No JSON array"):
        analyzer.analyze(_make_sub(), date(2026, 5, 1), date(2026, 5, 7))


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


def test_analyze_raises_on_max_tokens_truncation():
    """When stop_reason is 'max_tokens', raise a clear truncation error instead of generic parse failure."""
    truncated = '```json\n[\n  {\n    "title": "Consumo excesivo",\n    "category": "ResourceAnalysis",\n    "detail": "Texto muy largo'
    client = _mock_client(truncated, stop_reason="max_tokens")
    with patch("finops.ai.analyzer.Anthropic", return_value=client):
        analyzer = AiAnalyzer()
    with pytest.raises(ValueError, match="truncated"):
        analyzer.analyze(_make_sub(), date(2026, 5, 1), date(2026, 5, 7))


def test_analyzer_default_max_tokens_is_4096():
    client = _mock_client(_VALID_JSON)
    with patch("finops.ai.analyzer.Anthropic", return_value=client):
        analyzer = AiAnalyzer()
    analyzer.analyze(_make_sub(), date(2026, 5, 1), date(2026, 5, 7))
    assert client.messages.create.call_args.kwargs["max_tokens"] == 4096


def test_analyzer_max_tokens_env_override(monkeypatch):
    monkeypatch.setenv("FINOPS_AI_MAX_TOKENS", "8192")
    client = _mock_client(_VALID_JSON)
    with patch("finops.ai.analyzer.Anthropic", return_value=client):
        analyzer = AiAnalyzer()
    analyzer.analyze(_make_sub(), date(2026, 5, 1), date(2026, 5, 7))
    assert client.messages.create.call_args.kwargs["max_tokens"] == 8192


def test_analyzer_accepts_explicit_api_key():
    """api_key kwarg must be forwarded to the Anthropic constructor."""
    with patch("finops.ai.analyzer.Anthropic") as mock_cls:
        mock_cls.return_value = _mock_client(_VALID_JSON)
        AiAnalyzer(api_key="sk-test-key")
    mock_cls.assert_called_once_with(api_key="sk-test-key")
