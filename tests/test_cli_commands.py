"""Tests for CLI init and host commands."""

from __future__ import annotations

from pathlib import Path
from click.testing import CliRunner

from stovo_connector_sdk.cli import cli


def test_cli_init_command(tmp_path: Path) -> None:
    runner = CliRunner()
    target_dir = tmp_path / "my_jira"
    result = runner.invoke(cli, ["init", "jira", "--output-dir", str(target_dir)])
    assert result.exit_code == 0
    assert "Created connector project" in result.output

    assert (target_dir / "connector.py").exists()
    assert (target_dir / "pyproject.toml").exists()
    assert (target_dir / "README.md").exists()
    assert (target_dir / "tests" / "test_connector.py").exists()

    content = (target_dir / "connector.py").read_text()
    assert "class JiraConnector(BaseConnector):" in content
    assert 'kind = "jira"' in content


def test_cli_host_help() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["host", "--help"])
    assert result.exit_code == 0
    assert "Run the Multi-Connector Host" in result.output
    assert "--uds" in result.output
    assert "--dir" in result.output
