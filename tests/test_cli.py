"""Tests for Stovo Connector SDK CLI validator."""

from __future__ import annotations

from click.testing import CliRunner
import httpx

from examples.minimal_connector import DummyDocsConnector
from stovo_connector_sdk import create_connector_app
from stovo_connector_sdk.cli import cli


def test_cli_help() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Stovo Connector SDK" in result.output
    assert "test" in result.output
