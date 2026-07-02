import yaml
from pathlib import Path
from click.testing import CliRunner
from unittest.mock import MagicMock, patch
from finops.cli import cli

FIXTURE = Path(__file__).parent / "reporters" / "fixtures" / "data.json"


def test_list_subscriptions_reads_config(tmp_path):
    config_file = tmp_path / "subscriptions.yaml"
    config_file.write_text(yaml.dump({
        "subscriptions": [{"id": "sub-abc", "name": "My Sub"}],
    }))
    runner = CliRunner()
    result = runner.invoke(cli, ["list-subscriptions", "--config", str(config_file)])
    assert result.exit_code == 0
    assert "sub-abc" in result.output
    assert "My Sub" in result.output


def test_report_from_cache_generates_files(tmp_path):
    cache_dir = tmp_path / "2026-05-06"
    cache_dir.mkdir()
    (cache_dir / "data.json").write_text(FIXTURE.read_text())
    runner = CliRunner()
    result = runner.invoke(cli, ["report", "--from-cache", str(cache_dir), "--output", str(tmp_path)])
    assert result.exit_code == 0
    assert (tmp_path / "report.html").exists()
    assert (tmp_path / "report.md").exists()


def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "run" in result.output
    assert "report" in result.output
    assert "list-subscriptions" in result.output


def test_run_help_shows_with_ai_flag():
    runner = CliRunner()
    result = runner.invoke(cli, ["run", "--help"])
    assert result.exit_code == 0
    assert "--with-ai" in result.output
    assert "--api-key" in result.output


def test_with_ai_warns_when_no_api_key(tmp_path, monkeypatch):
    import yaml
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    config_file = tmp_path / "subscriptions.yaml"
    config_file.write_text(yaml.dump({"subscriptions": [{"id": "sub-abc", "name": "My Sub"}]}))
    runner = CliRunner()

    def _empty_collector():
        c = MagicMock()
        c.collect.return_value = []
        return c

    with patch("finops.cli.get_credential") as mock_cred, \
         patch("finops.cli.get_collectors") as mock_get_collectors:
        mock_cred.return_value = (MagicMock(), "AzureCLI")
        mock_get_collectors.return_value = (
            _empty_collector(), _empty_collector(), _empty_collector(),
        )
        result = runner.invoke(cli, [
            "run", "--with-ai", "--config", str(config_file), "--output", str(tmp_path),
        ])
    assert result.exit_code == 0
    assert "ANTHROPIC_API_KEY" in result.output


def test_run_mixed_providers_gcp_skip_does_not_affect_azure(tmp_path):
    from finops.providers import ProviderUnavailableError
    config_file = tmp_path / "subscriptions.yaml"
    config_file.write_text(yaml.dump({"subscriptions": [
        {"id": "azure-sub", "name": "Azure Client"},
        {"provider": "gcp", "id": "gcp-proj", "name": "GCP Client",
         "billing_account_id": "0123AB-4567CD-89EF01", "billing_export_dataset": "ds"},
    ]}))

    def _cred(entry):
        return (MagicMock(), entry.provider)

    def _collectors(entry, credential):
        res, cost, inv = MagicMock(), MagicMock(), MagicMock()
        if entry.provider == "gcp":
            res.collect.side_effect = ProviderUnavailableError("Billing export table not found")
        else:
            res.collect.return_value = []
            cost.collect.return_value = []
            inv.collect.return_value = []
        return (res, cost, inv)

    runner = CliRunner()
    with patch("finops.cli.get_credential", side_effect=_cred), \
         patch("finops.cli.get_collectors", side_effect=_collectors):
        result = runner.invoke(cli, ["run", "--config", str(config_file), "--output", str(tmp_path)])

    assert result.exit_code == 0
    # Azure entry processed successfully; GCP entry skipped but the run completes.
    assert "Azure Client" in result.output
    assert "GCP Client" in result.output
    assert "Billing export table not found" in result.output
