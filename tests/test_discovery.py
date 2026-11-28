"""Tests for dynamic connector discovery."""

from __future__ import annotations

from pathlib import Path
import pytest

from stovo_connector_sdk.discovery import discover_connectors


def test_discover_connectors_from_dir(tmp_path: Path) -> None:
    # Create a plugin directory with sample connector
    plugin_dir = tmp_path / "sample_plugin"
    plugin_dir.mkdir()
    connector_file = plugin_dir / "connector.py"
    connector_file.write_text(
        """
from stovo_connector_sdk import BaseConnector, BackfillResponse, EventsResponse, ResourceSnapshot, AuthorizationDecision

class AutoDiscoveredConnector(BaseConnector):
    kind = "autodiscovered"

    async def get_scopes(self):
        return [("tenant-auto", "conn-auto")]

    async def begin_backfill(self, tenant_id: str, connection_id: str, *, page_size: int = 100):
        return BackfillResponse(snapshots=[], cursor=None)

    async def continue_backfill(self, cursor: str, **kwargs):
        return BackfillResponse(snapshots=[], cursor=None)

    async def list_events(self, cursor: str, **kwargs):
        return EventsResponse(events=[], cursor=cursor, has_more=False)

    async def get_snapshot(self, resource_id: str, revision_id: str, **kwargs):
        raise NotImplementedError

    async def bulk_authorize(self, principal_id: str, operation, resource_ids, **kwargs):
        return []
"""
    )

    connectors = discover_connectors(tmp_path)
    assert "autodiscovered" in connectors
    assert connectors["autodiscovered"].kind == "autodiscovered"


def test_discover_empty_dir(tmp_path: Path) -> None:
    connectors = discover_connectors(tmp_path)
    assert len(connectors) == 0
