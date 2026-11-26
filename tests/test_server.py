"""Tests for Stovo Connector SDK FastAPI server mounting."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from examples.minimal_connector import DummyDocsConnector
from stovo_connector_sdk import create_connector_app


@pytest.fixture
def test_client() -> TestClient:
    connector = DummyDocsConnector()
    app = create_connector_app(connector, auth_token="secret-123")
    return TestClient(app)


def test_auth_rejection(test_client: TestClient) -> None:
    resp = test_client.get("/scopes")
    assert resp.status_code == 401

    resp = test_client.get("/scopes", headers={"Authorization": "Bearer wrong-token"})
    assert resp.status_code == 401


def test_scopes(test_client: TestClient) -> None:
    resp = test_client.get("/scopes", headers={"Authorization": "Bearer secret-123"})
    assert resp.status_code == 200
    data = resp.json()
    assert "scopes" in data
    assert len(data["scopes"]) == 1
    assert data["scopes"][0]["tenant_id"] == "tenant-acme"


def test_backfill_begin(test_client: TestClient) -> None:
    headers = {
        "Authorization": "Bearer secret-123",
        "X-Tenant-ID": "tenant-acme",
        "X-Connection-ID": "connection-docs-1",
    }
    resp = test_client.get("/backfill/begin?page_size=10", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["snapshots"]) == 2
    assert data["fence_cursor"] == "fence-1"


def test_bulk_authorize(test_client: TestClient) -> None:
    headers = {
        "Authorization": "Bearer secret-123",
        "X-Tenant-ID": "tenant-acme",
        "X-Connection-ID": "connection-docs-1",
    }
    body = {
        "schema_version": "v1",
        "principal_id": "user-alice",
        "operation": "read",
        "resource_ids": ["doc-1", "secret-doc-99"],
    }
    resp = test_client.post("/authorization:check", json=body, headers=headers)
    assert resp.status_code == 200
    decisions = resp.json()["decisions"]
    assert len(decisions) == 2
    assert decisions[0]["allowed"] is True
    assert decisions[1]["allowed"] is False


def test_citation_resolve(test_client: TestClient) -> None:
    headers = {
        "Authorization": "Bearer secret-123",
        "X-Tenant-ID": "tenant-acme",
        "X-Connection-ID": "connection-docs-1",
    }
    body = {
        "resource_id": "doc-1",
        "revision_id": "rev-1",
        "start": 0,
        "end": 50,
    }
    resp = test_client.post("/citations:resolve", json=body, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["url"] == "https://docs.acme.corp/pages/doc-1#offset=0"
