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
