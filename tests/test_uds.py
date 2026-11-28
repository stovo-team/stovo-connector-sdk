"""Tests for MultiConnectorHost over Unix Domain Socket."""

from __future__ import annotations

import asyncio
from pathlib import Path
import threading
import time
import httpx
import pytest
import uvicorn

from examples.minimal_connector import DummyDocsConnector
from stovo_connector_sdk.server import create_multi_connector_app


def _run_server_on_uds(app, sock_path: str, shutdown_event: threading.Event) -> None:
    config = uvicorn.Config(app, uds=sock_path, log_level="warning")
    server = uvicorn.Server(config)

    # Run loop in thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def serve():
        srv_task = asyncio.create_task(server.serve())
        while not shutdown_event.is_set():
            await asyncio.sleep(0.05)
        server.should_exit = True
        await srv_task

    loop.run_until_complete(serve())
    loop.close()


def test_uds_multi_host(tmp_path: Path) -> None:
    sock_path = tmp_path / "connectors.sock"
    docs_conn = DummyDocsConnector()
    docs_conn.kind = "docs"

    app = create_multi_connector_app([docs_conn], auth_token="uds-secret")

    shutdown_event = threading.Event()
    server_thread = threading.Thread(
        target=_run_server_on_uds,
        args=(app, str(sock_path), shutdown_event),
        daemon=True,
    )
    server_thread.start()

    # Wait for socket file to appear
    for _ in range(50):
        if sock_path.exists():
            break
        time.sleep(0.05)

    assert sock_path.exists(), "UDS socket was not created"

    try:
        transport = httpx.HTTPTransport(uds=str(sock_path))
        with httpx.Client(transport=transport, base_url="http://localhost") as client:
            resp = client.get("/health")
            assert resp.status_code == 200
            assert resp.json()["status"] == "ok"
            assert "docs" in resp.json()["connectors"]

            # Test scopes
            resp = client.get(
                "/connectors/docs/scopes",
                headers={"Authorization": "Bearer uds-secret"},
            )
            assert resp.status_code == 200
            assert len(resp.json()["scopes"]) == 1
    finally:
        shutdown_event.set()
        server_thread.join(timeout=3.0)
