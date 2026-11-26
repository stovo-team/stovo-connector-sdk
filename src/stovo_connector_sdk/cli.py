"""CLI utilities for Stovo Connector development and contract validation."""

from __future__ import annotations

import asyncio
import sys
import click
import httpx


@click.group()
def cli() -> None:
    """Stovo Connector SDK development CLI."""


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

    # 5. Exact Snapshot
    if sample_resource_id and sample_revision_id:
        try:
            resp = client.get(
                f"{url}/resources/{sample_resource_id}/snapshot?revision_id={sample_revision_id}",
                headers=scope_headers,
            )
            if resp.status_code == 200 and resp.json().get("resource_id") == sample_resource_id:
                record_step(f"GET /resources/{sample_resource_id}/snapshot", True)
            else:
                record_step(f"GET /resources/{sample_resource_id}/snapshot", False, f"status={resp.status_code}")
        except Exception as err:
            record_step("GET /resources/.../snapshot", False, str(err))
    else:
        click.echo("  [SKIP] GET /resources/.../snapshot (no snapshot discovered during backfill)")

    # 6. Bulk Authorize
    try:
        res_id = sample_resource_id or "test-res-1"
        resp = client.post(
            f"{url}/authorization:check",
            json={
                "schema_version": "v1",
                "principal_id": "test-user",
                "operation": "read",
                "resource_ids": [res_id],
            },
            headers=scope_headers,
        )
        if resp.status_code == 200 and len(resp.json().get("decisions", [])) == 1:
            record_step("POST /authorization:check", True)
        else:
            record_step("POST /authorization:check", False, f"status={resp.status_code}")
    except Exception as err:
        record_step("POST /authorization:check", False, str(err))

    # 7. Citations Resolve
    try:
        res_id = sample_resource_id or "test-res-1"
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
