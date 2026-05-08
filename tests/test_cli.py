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


def test_with_ai_warns_when_no_api_key(tmp_path, monkeypatch):
    import yaml
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    config_file = tmp_path / "subscriptions.yaml"
    config_file.write_text(yaml.dump({"subscriptions": [{"id": "sub-abc", "name": "My Sub"}]}))
    runner = CliRunner()
    with patch("finops.cli.get_credential") as mock_cred, \
         patch("finops.cli.ResourceCollector") as mock_res, \
         patch("finops.cli.CostCollector") as mock_cost, \
         patch("finops.cli.InvoiceCollector") as mock_inv:
        mock_cred.return_value = (MagicMock(), MagicMock(value="AzureCLI"))
        mock_res.return_value.collect.return_value = []
        mock_cost.return_value.collect.return_value = []
        mock_inv.return_value.collect.return_value = []
        result = runner.invoke(cli, [
            "run", "--with-ai", "--config", str(config_file), "--output", str(tmp_path),
        ])
    assert result.exit_code == 0
    assert "ANTHROPIC_API_KEY" in result.output
