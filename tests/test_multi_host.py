"""Tests for Multi-Connector Host mounting and routing."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence
import pytest
from fastapi.testclient import TestClient

from examples.minimal_connector import DummyDocsConnector
from stovo_connector_sdk.base import BaseConnector
from stovo_connector_sdk.models import (
    AuthorizationDecision,
    AuthorizationOperation,
    BackfillResponse,
    CitationResolution,
    EventsResponse,
    ResourceSnapshot,
    TextLocator,
)
from stovo_connector_sdk.server import create_multi_connector_app


class DummyIssuesConnector(BaseConnector):
    kind = "issues"

    async def get_scopes(self) -> list[tuple[str, str]]:
        return [("tenant-acme", "connection-issues-1")]

    async def begin_backfill(
        self, tenant_id: str, connection_id: str, *, page_size: int = 100
    ) -> BackfillResponse:
        now = datetime.now(timezone.utc)
        return BackfillResponse(
            snapshots=[
                ResourceSnapshot(
                    tenant_id=tenant_id,
                    connection_id=connection_id,
                    resource_id="issue-101",
                    revision_id="r1",
                    content_revision_id="r1",
                    metadata_revision_id="r1",
                    observed_at=now,
                    content="Bug report: crash on startup",
                    metadata={"title": "Issue #101", "container_id": "bugs"},
                )
            ],
            cursor=None,
        )

    async def continue_backfill(
        self,
        cursor: str,
        *,
        page_size: int = 100,
        backfill_id: str | None = None,
        tenant_id: str | None = None,
        connection_id: str | None = None,
    ) -> BackfillResponse:
        return BackfillResponse(snapshots=[], cursor=None)

    async def list_events(
        self,
        cursor: str,
        *,
        limit: int = 100,
        tenant_id: str | None = None,
        connection_id: str | None = None,
    ) -> EventsResponse:
        return EventsResponse(events=[], cursor=cursor, has_more=False)

    async def get_snapshot(
        self,
        resource_id: str,
        revision_id: str,
        *,
        tenant_id: str | None = None,
        connection_id: str | None = None,
    ) -> ResourceSnapshot:
        now = datetime.now(timezone.utc)
        return ResourceSnapshot(
            tenant_id=tenant_id or "tenant-acme",
            connection_id=connection_id or "connection-issues-1",
            resource_id=resource_id,
            revision_id=revision_id,
            content_revision_id=revision_id,
            metadata_revision_id=revision_id,
            observed_at=now,
            content="Issue content",
            metadata={"container_id": "bugs"},
        )

    async def bulk_authorize(
        self,
        principal_id: str,
        operation: AuthorizationOperation,
        resource_ids: Sequence[str],
        *,
        tenant_id: str | None = None,
        connection_id: str | None = None,
    ) -> list[AuthorizationDecision]:
        return [
            AuthorizationDecision(resource_id=r_id, allowed=True, policy_revision="1")
            for r_id in resource_ids
        ]


@pytest.fixture
def multi_client() -> TestClient:
    docs_conn = DummyDocsConnector()
    docs_conn.kind = "docs"
    issues_conn = DummyIssuesConnector()

    app = create_multi_connector_app(
        connectors=[docs_conn, issues_conn],
        auth_token="multi-secret-999",
    )
    return TestClient(app)


def test_multi_host_health(multi_client: TestClient) -> None:
    resp = multi_client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert set(data["connectors"]) == {"docs", "issues"}


def test_multi_host_auth_rejection(multi_client: TestClient) -> None:
    resp = multi_client.get("/connectors/docs/scopes")
    assert resp.status_code == 401

    resp = multi_client.get(
        "/connectors/docs/scopes", headers={"Authorization": "Bearer wrong-token"}
    )
    assert resp.status_code == 401


def test_multi_host_routing(multi_client: TestClient) -> None:
    auth_header = {"Authorization": "Bearer multi-secret-999"}

    # Scopes for docs
    resp = multi_client.get("/connectors/docs/scopes", headers=auth_header)
    assert resp.status_code == 200
    docs_scopes = resp.json()["scopes"]
    assert len(docs_scopes) == 1
    assert docs_scopes[0]["connection_id"] == "connection-docs-1"

    # Scopes for issues
    resp = multi_client.get("/connectors/issues/scopes", headers=auth_header)
    assert resp.status_code == 200
    issues_scopes = resp.json()["scopes"]
    assert len(issues_scopes) == 1
    assert issues_scopes[0]["connection_id"] == "connection-issues-1"

    # Unknown connector 404
    resp = multi_client.get("/connectors/unknown_xyz/scopes", headers=auth_header)
    assert resp.status_code == 404


def test_multi_host_backfill(multi_client: TestClient) -> None:
    headers = {
        "Authorization": "Bearer multi-secret-999",
        "X-Tenant-ID": "tenant-acme",
        "X-Connection-ID": "connection-issues-1",
    }
    resp = multi_client.get("/connectors/issues/backfill/begin?page_size=10", headers=headers)
    assert resp.status_code == 200
    snaps = resp.json()["snapshots"]
    assert len(snaps) == 1
    assert snaps[0]["resource_id"] == "issue-101"


def test_multi_host_header_routing(multi_client: TestClient) -> None:
    """Clients sending X-Connector-Kind header can hit root endpoints."""
    headers = {
        "Authorization": "Bearer multi-secret-999",
        "X-Connector-Kind": "issues",
        "X-Tenant-ID": "tenant-acme",
        "X-Connection-ID": "connection-issues-1",
    }
    resp = multi_client.get("/scopes", headers=headers)
    assert resp.status_code == 200
    scopes = resp.json()["scopes"]
    assert scopes[0]["connection_id"] == "connection-issues-1"
