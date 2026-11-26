"""Minimal working example of a custom Stovo Connector."""

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


class DummyDocsConnector(BaseConnector):
    """Simple in-memory docs connector serving synthetic documents."""

    def __init__(self):
        now = datetime.now(timezone.utc)
        self.docs = {
            "doc-1": {
                "title": "Getting Started with Our Team",
                "content": "Welcome to our engineering handbook! All technical decisions follow RFCs.",
                "revision": "rev-1",
            },
            "doc-2": {
                "title": "Architecture Overview",
                "content": "Our services communicate via asynchronous events and strict hexagonal boundaries.",
                "revision": "rev-1",
            },
        }

    async def get_scopes(self) -> list[tuple[str, str]]:
        return [("tenant-acme", "connection-docs-1")]

    async def begin_backfill(
        self, tenant_id: str, connection_id: str, *, page_size: int = 100
    ) -> BackfillResponse:
        now = datetime.now(timezone.utc)
        snapshots = []
        for doc_id, doc in self.docs.items():
            snapshots.append(
                ResourceSnapshot(
                    tenant_id=tenant_id,
                    connection_id=connection_id,
                    resource_id=doc_id,
                    revision_id=doc["revision"],
                    content_revision_id=doc["revision"],
                    metadata_revision_id=doc["revision"],
                    observed_at=now,
                    content=doc["content"],
                    metadata={"title": doc["title"], "container_id": "handbook"},
                )
            )
        return BackfillResponse(
            snapshots=snapshots[:page_size],
            cursor="done",
            fence_cursor="fence-1",
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
        doc = self.docs[resource_id]
        return ResourceSnapshot(
            tenant_id=tenant_id or "tenant-acme",
            connection_id=connection_id or "connection-docs-1",
            resource_id=resource_id,
            revision_id=doc["revision"],
            content_revision_id=doc["revision"],
            metadata_revision_id=doc["revision"],
            observed_at=datetime.now(timezone.utc),
            content=doc["content"],
            metadata={"title": doc["title"]},
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
        # Source-authoritative check: all docs readable except secret ones
        return [
            AuthorizationDecision(
                resource_id=r_id,
                allowed=not r_id.startswith("secret-"),
                reason="public_in_org",
            )
            for r_id in resource_ids
        ]

    async def resolve_citation(
        self,
        resource_id: str,
        revision_id: str,
        locator: TextLocator,
        *,
        tenant_id: str | None = None,
        connection_id: str | None = None,
    ) -> CitationResolution:
        doc = self.docs.get(resource_id, {"title": resource_id})
        return CitationResolution(
            resource_id=resource_id,
            revision_id=revision_id,
            url=f"https://docs.acme.corp/pages/{resource_id}#offset={locator.start}",
            title=doc.get("title", resource_id),
            snippet="",
        )


if __name__ == "__main__":
    # Start the connector HTTP server
    DummyDocsConnector.serve(host="0.0.0.0", port=8080, auth_token="test-secret")
