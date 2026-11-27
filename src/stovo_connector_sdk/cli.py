"""CLI utilities for Stovo Connector development, project scaffolding, and hosting."""

from __future__ import annotations

import asyncio
from pathlib import Path
import sys
import click
import httpx
import uvicorn

from .discovery import discover_connectors
from .server import create_multi_connector_app


@click.group()
def cli() -> None:
    """Stovo Connector SDK development CLI."""


@cli.command("init")
@click.argument("name")
@click.option("--output-dir", "-o", default=None, help="Directory to create the project in")
def init_connector(name: str, output_dir: str | None) -> None:
    """Scaffold a new connector project with starter code and tests."""
    clean_name = name.strip().lower().replace("-", "_")
    class_name = f"{''.join(part.capitalize() for part in clean_name.split('_'))}Connector"
    project_dir = Path(output_dir) if output_dir else Path(f"stovo-connector-{clean_name}")

    if project_dir.exists() and any(project_dir.iterdir()):
        click.echo(f"Error: Directory '{project_dir}' already exists and is not empty.", err=True)
        sys.exit(1)

    project_dir.mkdir(parents=True, exist_ok=True)
    tests_dir = project_dir / "tests"
    tests_dir.mkdir(exist_ok=True)

    # 1. connector.py
    connector_code = f'''"""Stovo Connector implementation for {clean_name}."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence

from stovo_connector_sdk import (
    AuthorizationDecision,
    AuthorizationOperation,
    BackfillResponse,
    BaseConnector,
    CitationResolution,
    EventsResponse,
    ResourceSnapshot,
    SourceEvent,
    SourceEventKind,
    TextLocator,
)


class {class_name}(BaseConnector):
    """Data connector for {clean_name} integrating with Stovo Insight."""

    kind = "{clean_name}"

    def __init__(self) -> None:
        # TODO: Initialize external client/credentials
        pass

    async def get_scopes(self) -> list[tuple[str, str]]:
        """Return active (tenant_id, connection_id) pairs."""
        # TODO: Return actual tenant and connection scopes
        return [("tenant-default", "conn-{clean_name}-1")]

    async def begin_backfill(
        self, tenant_id: str, connection_id: str, *, page_size: int = 100
    ) -> BackfillResponse:
        """Fetch the first batch of documents/records."""
        # TODO: Query external API
        now = datetime.now(timezone.utc)
        snapshots = [
            ResourceSnapshot(
                tenant_id=tenant_id,
                connection_id=connection_id,
                resource_id="sample-1",
                revision_id="v1",
                content_revision_id="v1",
                metadata_revision_id="v1",
                observed_at=now,
                content="Sample document indexed from {clean_name}.",
                metadata={{"title": "Sample 1", "container_id": "general"}},
            )
        ]
        return BackfillResponse(snapshots=snapshots[:page_size], cursor=None)

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
            tenant_id=tenant_id or "tenant-default",
            connection_id=connection_id or "conn-{clean_name}-1",
            resource_id=resource_id,
            revision_id=revision_id,
            content_revision_id=revision_id,
            metadata_revision_id=revision_id,
            observed_at=now,
            content="Document content",
            metadata={{"title": resource_id}},
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
        # TODO: Check source ACL
        return [
            AuthorizationDecision(resource_id=r_id, allowed=True, policy_revision="1")
            for r_id in resource_ids
        ]
'''
    (project_dir / "connector.py").write_text(connector_code)

    # 2. pyproject.toml
    pyproject_code = f'''[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "stovo-connector-{clean_name}"
version = "0.1.0"
description = "Stovo Insight connector for {clean_name}"
readme = "README.md"
requires-python = ">=3.10"
dependencies = [
    "stovo-connector-sdk>=0.1.0",
]

[project.entry-points."stovo.connectors"]
{clean_name} = "connector:{class_name}"

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
]
'''
    (project_dir / "pyproject.toml").write_text(pyproject_code)

    # 3. tests/test_connector.py
    test_code = f'''import pytest
from connector import {class_name}

@pytest.mark.asyncio
async def test_scopes():
    conn = {class_name}()
    scopes = await conn.get_scopes()
    assert len(scopes) > 0

@pytest.mark.asyncio
async def test_backfill():
    conn = {class_name}()
    resp = await conn.begin_backfill("tenant-1", "conn-1", page_size=10)
    assert len(resp.snapshots) >= 1
'''
    (tests_dir / "test_connector.py").write_text(test_code)

    # 4. README.md
    readme_code = f'''# Stovo Connector: {clean_name.capitalize()}

Connector integrating {clean_name.capitalize()} with Stovo Insight.

## Development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## Running with Multi-Connector Host

Mount this directory into the Stovo Connector Host, or register entry point in `pyproject.toml`.
'''
    (project_dir / "README.md").write_text(readme_code)

    click.echo(f"Created connector project at: {project_dir}")


@cli.command("host")
@click.option("--dir", "connectors_dir", default="./connectors", help="Directory containing connector plugins")
@click.option("--host", default="0.0.0.0", help="HTTP bind host")
@click.option("--port", default=8080, type=int, help="HTTP bind port")
@click.option("--uds", default=None, help="Unix domain socket path")
@click.option("--token", default=None, help="Bearer authorization token")
@click.option("--reload", is_flag=True, default=False, help="Enable auto-reload for development")
def host_connectors(
    connectors_dir: str,
    host: str,
    port: int,
    uds: str | None,
    token: str | None,
    reload: bool,
) -> None:
    """Run the Multi-Connector Host serving discovered connectors."""
    connectors = discover_connectors(directory=connectors_dir)
    click.echo(f"Discovered {len(connectors)} connector(s): {', '.join(connectors.keys()) or 'none'}")

    app = create_multi_connector_app(connectors, auth_token=token)

    if uds:
        click.echo(f"Starting Multi-Connector Host on Unix Domain Socket: {uds}")
        uvicorn.run(app, uds=uds)
    else:
        click.echo(f"Starting Multi-Connector Host on http://{host}:{port}")
        uvicorn.run(app, host=host, port=port, reload=reload)


@cli.command("test")
@click.argument("endpoint_url")
@click.option("--token", default=None, help="Bearer authorization token")
def test_connector(endpoint_url: str, token: str | None) -> None:
    """Validate a running connector service against the Stovo Connector Protocol."""
    url = endpoint_url.rstrip("/")
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    passed = 0
    failed = 0

    def record_step(name: str, success: bool, message: str = "") -> None:
        nonlocal passed, failed
        if success:
            passed += 1
            click.echo(f"  [PASS] {name} {message}")
        else:
            failed += 1
            click.echo(f"  [FAIL] {name} - {message}", err=True)

    click.echo(f"\nValidating connector at: {url}\n")
    client = httpx.Client(headers=headers, timeout=10.0)

    # 1. Scopes
    tenant_id = "test-tenant"
    connection_id = "test-connection"
    try:
        resp = client.get(f"{url}/scopes")
        if resp.status_code == 200 and "scopes" in resp.json():
            scopes = resp.json()["scopes"]
            record_step("GET /scopes", True, f"({len(scopes)} scopes discovered)")
            if scopes:
                tenant_id = scopes[0].get("tenant_id", tenant_id)
                connection_id = scopes[0].get("connection_id", connection_id)
        else:
            record_step("GET /scopes", False, f"status={resp.status_code}, body={resp.text[:100]}")
    except Exception as err:
        record_step("GET /scopes", False, str(err))

    scope_headers = {"X-Tenant-ID": tenant_id, "X-Connection-ID": connection_id}

    # 2. Backfill begin
    cursor = None
    sample_resource_id = None
    sample_revision_id = None
    try:
        resp = client.get(f"{url}/backfill/begin?page_size=2", headers=scope_headers)
        if resp.status_code == 200:
            data = resp.json()
            snaps = data.get("snapshots", [])
            cursor = data.get("cursor")
            record_step("GET /backfill/begin", True, f"({len(snaps)} snapshots returned)")
            if snaps:
                sample_resource_id = snaps[0].get("resource_id")
                sample_revision_id = snaps[0].get("revision_id")
        else:
            record_step("GET /backfill/begin", False, f"status={resp.status_code}")
    except Exception as err:
        record_step("GET /backfill/begin", False, str(err))

    # 3. Backfill continue
    if cursor:
        try:
            resp = client.get(f"{url}/backfill/continue?cursor={cursor}&page_size=2", headers=scope_headers)
            if resp.status_code == 200:
                record_step("GET /backfill/continue", True)
            else:
                record_step("GET /backfill/continue", False, f"status={resp.status_code}")
        except Exception as err:
            record_step("GET /backfill/continue", False, str(err))
    else:
        click.echo("  [SKIP] GET /backfill/continue (no pagination cursor returned)")

    # 4. Events
    try:
        resp = client.get(f"{url}/events?cursor=init_cursor&limit=10", headers=scope_headers)
        if resp.status_code == 200 and "events" in resp.json():
            record_step("GET /events", True)
        else:
            record_step("GET /events", False, f"status={resp.status_code}")
    except Exception as err:
        record_step("GET /events", False, str(err))

    # 5. Snapshot retrieval
    if sample_resource_id and sample_revision_id:
        try:
            resp = client.get(
                f"{url}/resources/{sample_resource_id}/snapshot?revision_id={sample_revision_id}",
                headers=scope_headers,
            )
            if resp.status_code == 200 and resp.json().get("resource_id") == sample_resource_id:
                record_step("GET /resources/{resource_id}/snapshot", True)
            else:
                record_step("GET /resources/{resource_id}/snapshot", False, f"status={resp.status_code}")
        except Exception as err:
            record_step("GET /resources/{resource_id}/snapshot", False, str(err))
    else:
        click.echo("  [SKIP] GET /resources/{id}/snapshot (no snapshot returned in backfill)")

    # 6. Bulk authorization check
    try:
        res_ids = [sample_resource_id] if sample_resource_id else ["sample-item-1"]
        resp = client.post(
            f"{url}/authorization:check",
            json={
                "schema_version": "v1",
                "principal_id": "test-user-id",
                "operation": "read",
                "resource_ids": res_ids,
            },
            headers=scope_headers,
        )
        if resp.status_code == 200 and "decisions" in resp.json():
            record_step("POST /authorization:check", True)
        else:
            record_step("POST /authorization:check", False, f"status={resp.status_code}")
    except Exception as err:
        record_step("POST /authorization:check", False, str(err))

    # 7. Citation resolution
    try:
        res_id = sample_resource_id or "sample-item-1"
        rev_id = sample_revision_id or "test-rev-1"
        resp = client.post(
            f"{url}/citations:resolve",
            json={
                "resource_id": res_id,
                "revision_id": rev_id,
                "start": 0,
                "end": 100,
            },
            headers=scope_headers,
        )
        if resp.status_code == 200 and "url" in resp.json():
            record_step("POST /citations:resolve", True)
        else:
            record_step("POST /citations:resolve", False, f"status={resp.status_code}")
    except Exception as err:
        record_step("POST /citations:resolve", False, str(err))

    click.echo(f"\nSummary: {passed} passed, {failed} failed\n")
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    cli()
